from __future__ import annotations

from dataclasses import dataclass
import threading
from functools import lru_cache, wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol, TypeVar

import numpy as np
import spiceypy as spice


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPICE_DIR = PROJECT_ROOT / "data" / "spice"

KERNELS = [
    SPICE_DIR / "naif0012.tls",
    SPICE_DIR / "pck00010.tpc",
    SPICE_DIR / "moon_080317.tf",
    SPICE_DIR / "moon_pa_de421_1900-2050.bpc",
    SPICE_DIR / "de430.bsp",
]
_ENGINE_KERNELS_LOADED: set[Path] = set()

# CSPICE keeps global state and is not thread-safe: concurrent calls from a
# web server's thread pool fail (e.g. SpiceINVALIDDIVISOR) or corrupt results.
# Every public entry point holds this re-entrant lock; callers composing
# several calls atomically may also hold it (``with SPICE_LOCK: ...``).
SPICE_LOCK = threading.RLock()
_F = TypeVar("_F", bound=Callable[..., object])


def spice_serialized(*, ensure_kernels: bool) -> Callable[[_F], _F]:
    """Run under ``SPICE_LOCK``; compute entry points also (re)load kernels.

    Re-loading inside the lock means one caller's ``unload_kernels()`` can
    never pull kernels out from under another caller's computation.
    """
    def decorate(function: _F) -> _F:
        @wraps(function)
        def wrapper(*args: object, **kwargs: object) -> object:
            with SPICE_LOCK:
                if ensure_kernels:
                    load_kernels()
                return function(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorate


@dataclass
class HourlyGeometry:
    utc: str
    earth_elevation_deg: float
    earth_azimuth_deg: float
    sun_elevation_deg: float
    sun_azimuth_deg: float
    earth_visible: bool


@dataclass
class CommunicationsSummary:
    uptime_percent: float
    longest_blackout_hours: float
    total_hours: int
    visible_hours: int
    blackout_intervals: list[tuple[str, str]]

    @property
    def communications_uptime_percent(self) -> float:
        """Compatibility-friendly explicit name for geometric LOS uptime."""
        return self.uptime_percent

    def to_dict(self) -> dict[str, object]:
        """Return the stable downstream schema; intervals are UTC [start, end)."""
        return {
            "visibility_model": "spherical_horizon_geometric_los",
            "communications_uptime_percent": self.uptime_percent,
            "longest_blackout_hours": self.longest_blackout_hours,
            "total_hours": self.total_hours,
            "visible_hours": self.visible_hours,
            "blackout_intervals": [
                {"start_utc": start, "end_utc": end}
                for start, end in self.blackout_intervals
            ],
        }


@spice_serialized(ensure_kernels=False)
def load_kernels() -> None:
    """Load required kernels once, preserving kernels loaded by other callers."""
    loaded = {
        Path(spice.kdata(i, "ALL", 256, 256, 256)[0]).resolve()
        for i in range(spice.ktotal("ALL"))
    }
    for kernel in KERNELS:
        if not kernel.exists():
            raise FileNotFoundError(
                f"Required SPICE kernel not found: {kernel}"
            )
        if kernel.resolve() not in loaded:
            spice.furnsh(str(kernel))
            _ENGINE_KERNELS_LOADED.add(kernel.resolve())


@spice_serialized(ensure_kernels=False)
def unload_kernels() -> None:
    """Unload only this engine's kernels, leaving unrelated SPICE state intact."""
    for resolved in tuple(_ENGINE_KERNELS_LOADED):
        for index in reversed(range(spice.ktotal("ALL"))):
            loaded_path = Path(spice.kdata(index, "ALL", 256, 256, 256)[0])
            if loaded_path.resolve() == resolved:
                spice.unload(str(loaded_path))
        _ENGINE_KERNELS_LOADED.discard(resolved)


def _observer_position(
    latitude_deg: float,
    longitude_deg: float,
    et: float,
) -> np.ndarray:
    """
    Return lunar surface observer position in MOON_PA coordinates.

    Latitude:
        Positive north, negative south.

    Longitude:
        Positive east, negative west.
    """
    # Mission coordinates are planetocentric. Intersect the radial direction
    # with the Moon's reference ellipsoid instead of treating them as geodetic.
    position_me = _observer_position_me(latitude_deg, longitude_deg)
    # Mission coordinates are mean-Earth (ME); SPK geometry below is PA.
    return spice.mxv(spice.pxform("MOON_ME", "MOON_PA", et), position_me)


def _local_basis(
    latitude_deg: float,
    longitude_deg: float,
    et: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Construct local East-North-Up basis in MOON_PA coordinates.
    """
    lat = np.radians(latitude_deg)
    lon = np.radians(longitude_deg)

    east = np.array(
        [
            -np.sin(lon),
            np.cos(lon),
            0.0,
        ],
        dtype=float,
    )

    position_me = _observer_position_me(latitude_deg, longitude_deg)
    radii = spice.bodvrd("MOON", "RADII", 3)[1]
    up_me = np.asarray(spice.surfnm(
        *radii,
        position_me,
    ), dtype=float)
    up_me /= np.linalg.norm(up_me)
    north_me = np.cross(up_me, east)
    north_me /= np.linalg.norm(north_me)

    me_to_pa = spice.pxform("MOON_ME", "MOON_PA", et)
    return tuple(np.asarray(spice.mxv(me_to_pa, axis))
                 for axis in (east, north_me, up_me))


def _observer_position_me(latitude_deg: float, longitude_deg: float) -> np.ndarray:
    radii = spice.bodvrd("MOON", "RADII", 3)[1]
    lat, lon = np.radians(latitude_deg), np.radians(longitude_deg)
    distance = 1.0 / np.sqrt(np.cos(lat) ** 2 / radii[0] ** 2 +
                              np.sin(lat) ** 2 / radii[2] ** 2)
    return np.array([distance * np.cos(lat) * np.cos(lon),
                     distance * np.cos(lat) * np.sin(lon),
                     distance * np.sin(lat)], dtype=float)


def _validate_coordinates(latitude_deg: float, longitude_deg: float) -> None:
    if not np.isfinite(latitude_deg) or not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg) or not -180.0 <= longitude_deg <= 180.0:
        raise ValueError("longitude_deg must be finite and between -180 and 180")


def _parse_utc(utc: str) -> tuple[datetime, str]:
    try:
        timestamp = datetime.fromisoformat(utc.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("utc must be a valid timezone-aware ISO 8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("utc must include Z or an explicit UTC offset")
    timestamp = timestamp.astimezone(timezone.utc)
    return timestamp, timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _elevation_azimuth(
    target_vector: np.ndarray,
    east: np.ndarray,
    north: np.ndarray,
    up: np.ndarray,
) -> tuple[float, float]:
    """
    Calculate local elevation and azimuth.

    Azimuth convention:
        0°   = North
        90°  = East
        180° = South
        270° = West
    """
    direction = target_vector / np.linalg.norm(target_vector)

    east_component = np.dot(direction, east)
    north_component = np.dot(direction, north)
    up_component = np.clip(np.dot(direction, up), -1.0, 1.0)

    elevation_deg = float(np.degrees(np.arcsin(up_component)))

    azimuth_deg = float(
        np.degrees(
            np.arctan2(
                east_component,
                north_component,
            )
        )
        % 360.0
    )

    return elevation_deg, azimuth_deg


@spice_serialized(ensure_kernels=True)
def calculate_geometry(
    latitude_deg: float,
    longitude_deg: float,
    utc: str,
) -> HourlyGeometry:
    """
    Calculate Earth and Sun local geometry for a lunar surface location.
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    _, normalized_utc = _parse_utc(utc)
    et = spice.str2et(normalized_utc)
    state = _topocentric_state(latitude_deg, longitude_deg, et)

    return HourlyGeometry(
        utc=normalized_utc,
        earth_elevation_deg=state.earth_elevation_deg,
        earth_azimuth_deg=state.earth_azimuth_deg,
        sun_elevation_deg=state.sun_elevation_deg,
        sun_azimuth_deg=state.sun_azimuth_deg,
        earth_visible=state.earth_elevation_deg > 0.0,
    )


@lru_cache(maxsize=256)
def _site_frame_me(latitude_deg: float, longitude_deg: float
                   ) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Epoch-independent MOON_ME observer position and ENU basis for a site.

    Equivalent to ``_observer_position``/``_local_basis`` before the per-epoch
    ME->PA rotation; cached so time scans pay only for that rotation.
    """
    position_me = _observer_position_me(latitude_deg, longitude_deg)
    me_to_pa = spice.pxform("MOON_ME", "MOON_PA", 0.0)
    pa_to_me = np.asarray(me_to_pa).T
    east, north, up = (pa_to_me @ np.asarray(axis)
                       for axis in _local_basis(latitude_deg, longitude_deg, 0.0))
    for array in (position_me, east, north, up):
        array.setflags(write=False)
    return position_me, (east, north, up)


@dataclass(frozen=True)
class _TopocentricState:
    sun_elevation_deg: float
    sun_azimuth_deg: float
    earth_elevation_deg: float
    earth_azimuth_deg: float
    sun_unit_moon_pa: np.ndarray
    earth_unit_moon_pa: np.ndarray
    earth_range_km: float
    sun_range_km: float


def _topocentric_state(latitude_deg: float, longitude_deg: float, et: float) -> _TopocentricState:
    """Sun/Earth topocentric geometry at an ephemeris time (no input validation)."""
    position_me, basis_me = _site_frame_me(latitude_deg, longitude_deg)
    me_to_pa = np.asarray(spice.pxform("MOON_ME", "MOON_PA", et))
    observer = me_to_pa @ position_me
    east, north, up = (me_to_pa @ axis for axis in basis_me)
    earth_moon, _ = spice.spkpos("EARTH", et, "MOON_PA", "NONE", "MOON")
    sun_moon, _ = spice.spkpos("SUN", et, "MOON_PA", "NONE", "MOON")
    earth_vector = np.asarray(earth_moon) - observer
    sun_vector = np.asarray(sun_moon) - observer
    earth_elevation, earth_azimuth = _elevation_azimuth(earth_vector, east, north, up)
    sun_elevation, sun_azimuth = _elevation_azimuth(sun_vector, east, north, up)
    earth_range = float(np.linalg.norm(earth_vector))
    sun_range = float(np.linalg.norm(sun_vector))
    return _TopocentricState(
        sun_elevation, sun_azimuth, earth_elevation, earth_azimuth,
        sun_vector / sun_range, earth_vector / earth_range, earth_range, sun_range,
    )


@spice_serialized(ensure_kernels=True)
def calculate_current_geometry(
    latitude_deg: float,
    longitude_deg: float,
) -> HourlyGeometry:
    """Calculate geometry for the current UTC instant from the installed kernels.

    This is an ephemeris-based prediction at the current epoch, not a live
    observation or telemetry feed. The returned ``utc`` records the exact
    calculation epoch.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return calculate_geometry(latitude_deg, longitude_deg, now_utc)


@spice_serialized(ensure_kernels=True)
def calculate_hourly_geometry(
    latitude_deg: float,
    longitude_deg: float,
    start_utc: str,
    hours: int,
    *,
    step_minutes: float = 60.0,
) -> list[HourlyGeometry]:
    """
    Calculate Earth/Sun geometry over a mission window.

    ``hours`` is the window length; samples are ``step_minutes`` apart
    (hourly by default, preserving the original one-sample-per-hour schema).
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    start, _ = _parse_utc(start_utc)
    if hours < 0:
        raise ValueError("hours must be non-negative")
    if not np.isfinite(step_minutes) or step_minutes <= 0:
        raise ValueError("step_minutes must be positive")

    results: list[HourlyGeometry] = []

    for index in range(int(round(hours * 60.0 / step_minutes))):
        current = start + timedelta(minutes=index * step_minutes)

        utc = current.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        results.append(
            calculate_geometry(
                latitude_deg,
                longitude_deg,
                utc,
            )
        )

    return results


def summarize_communications(
    geometry: list[HourlyGeometry],
) -> CommunicationsSummary:
    """
    Summarize Earth line-of-sight availability.

    A communication opportunity exists when:
        Earth elevation > 0 degrees.
    """
    if not geometry:
        return CommunicationsSummary(
            uptime_percent=0.0,
            longest_blackout_hours=0.0,
            total_hours=0,
            visible_hours=0,
            blackout_intervals=[],
        )

    visible = [
        item.earth_visible
        for item in geometry
    ]

    total_hours = len(visible)
    visible_hours = sum(visible)

    uptime_percent = (
        visible_hours / total_hours
    ) * 100.0

    blackout_intervals: list[tuple[str, str]] = []

    blackout_start: str | None = None
    longest_blackout_hours = 0.0
    current_blackout_hours = 0.0

    for item in geometry:
        if not item.earth_visible:
            if blackout_start is None:
                blackout_start = item.utc

            current_blackout_hours += 1.0

        else:
            if blackout_start is not None:
                blackout_end = item.utc

                blackout_intervals.append(
                    (
                        blackout_start,
                        blackout_end,
                    )
                )

                longest_blackout_hours = max(
                    longest_blackout_hours,
                    current_blackout_hours,
                )

                blackout_start = None
                current_blackout_hours = 0.0

    if blackout_start is not None:
        final_time = datetime.fromisoformat(
            geometry[-1].utc.replace("Z", "+00:00")
        ) + timedelta(hours=1)
        blackout_end = final_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        blackout_intervals.append(
            (
                blackout_start,
                blackout_end,
            )
        )

        longest_blackout_hours = max(
            longest_blackout_hours,
            current_blackout_hours,
        )

    return CommunicationsSummary(
        uptime_percent=uptime_percent,
        longest_blackout_hours=longest_blackout_hours,
        total_hours=total_hours,
        visible_hours=visible_hours,
        blackout_intervals=blackout_intervals,
    )


# --- Temporal dynamics: horizon events, countdowns and scrubber tracks -------

SPEED_OF_LIGHT_KM_S = 299_792.458
SUN_RADIUS_KM = 695_700.0      # IAU 2015 nominal solar radius
EARTH_RADIUS_KM = 6_371.0      # mean radius; the visible limb, not the antenna
SYNODIC_MONTH_DAYS = 29.530589
BODIES = ("sun", "earth")


class _HorizonLike(Protocol):
    def elevation_at(self, azimuth_deg: float) -> float: ...


@dataclass(frozen=True)
class HorizonEvent:
    """A body crossing the local horizon; ``kind`` is ``rise`` or ``set``."""
    body: str
    kind: str
    utc: str
    hours_from_start: float

    def to_dict(self) -> dict[str, object]:
        return {"body": self.body, "kind": self.kind, "utc": self.utc,
                "hours_from_start": round(self.hours_from_start, 4)}


def format_countdown(hours: float | None) -> str | None:
    """Human-readable countdown: ``4d 18h`` (>= 1 day) or ``5h 12m``."""
    if hours is None or not np.isfinite(hours) or hours < 0:
        return None
    minutes = int(hours * 60.0)
    days, minutes = divmod(minutes, 1440)
    hrs, mins = divmod(minutes, 60)
    return f"{days}d {hrs}h" if days else f"{hrs}h {mins}m"


def angular_radius_deg(body_radius_km: float, range_km: float) -> float:
    return float(np.degrees(np.arcsin(min(body_radius_km / range_km, 1.0))))


def disk_visible_fraction(margin_deg: float, radius_deg: float) -> float | None:
    """Fraction of a body's disc area above a locally straight horizon.

    ``margin_deg`` is centre elevation minus horizon elevation. Uses the exact
    circular-segment area; the horizon is treated as a straight line across
    the disc (the mask is sampled at the centre azimuth only).
    """
    if not np.isfinite(margin_deg):
        return None
    h = float(np.clip(margin_deg / radius_deg, -1.0, 1.0))
    return float(1.0 - (np.arccos(h) - h * np.sqrt(1.0 - h * h)) / np.pi)


def _horizon_at(mask: _HorizonLike | None, azimuth_deg: float) -> float:
    return 0.0 if mask is None else float(mask.elevation_at(azimuth_deg))


def _margins(latitude_deg: float, longitude_deg: float, et: float,
             mask: _HorizonLike | None) -> tuple[_TopocentricState, dict[str, float]]:
    """Body elevation minus terrain horizon at the body azimuth (NaN = unknown)."""
    state = _topocentric_state(latitude_deg, longitude_deg, et)
    return state, {
        "sun": state.sun_elevation_deg - _horizon_at(mask, state.sun_azimuth_deg),
        "earth": state.earth_elevation_deg - _horizon_at(mask, state.earth_azimuth_deg),
    }


def _et_to_utc(et: float) -> str:
    return spice.et2utc(et, "ISOC", 0) + "Z"


@spice_serialized(ensure_kernels=True)
def find_horizon_events(
    latitude_deg: float,
    longitude_deg: float,
    start_utc: str,
    duration_days: float = SYNODIC_MONTH_DAYS,
    *,
    horizon_mask: _HorizonLike | None | str = "auto",
    step_minutes: float = 30.0,
    tolerance_seconds: float = 1.0,
) -> dict[str, object]:
    """Find Sun/Earth rise and set times against the local horizon.

    A body is up when its topocentric centre elevation exceeds the terrain
    horizon at its azimuth. ``horizon_mask="auto"`` (default) extracts the
    360-degree LOLA mask for the site (80 m polar DEM, else LDEM_64 tiles);
    pass a mask to reuse one, or ``None`` for a 0 deg spherical horizon. Where
    no terrain product covers the site, "auto" also degrades to spherical and
    ``horizon_model`` says so. The window is scanned every ``step_minutes`` and each
    sign change is refined by bisection to ``tolerance_seconds``. Crossings
    shorter than one scan step can be missed, and the Sun is treated as a
    point (its ~0.27 deg radius is not modelled).

    Countdowns from ``start_utc`` are ``None`` with an explicit status when the
    next event is beyond the window or crosses an unknown (NaN) horizon sector;
    they are never extrapolated.
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    _, normalized_start = _parse_utc(start_utc)
    if not np.isfinite(duration_days) or duration_days <= 0:
        raise ValueError("duration_days must be positive")
    if not np.isfinite(step_minutes) or step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    if isinstance(horizon_mask, str):
        if horizon_mask != "auto":
            raise ValueError('horizon_mask must be a mask, None, or "auto"')
        from .terrain import evaluate_site_terrain  # lazy: keeps SPICE import light
        horizon_mask = evaluate_site_terrain(latitude_deg, longitude_deg)["horizon_mask"]
    et0 = spice.str2et(normalized_start)
    step = step_minutes * 60.0
    count = int(np.ceil(duration_days * 86_400.0 / step))
    ets = et0 + np.arange(count + 1) * step
    ets[-1] = min(ets[-1], et0 + duration_days * 86_400.0)

    samples = [_margins(latitude_deg, longitude_deg, float(et), horizon_mask) for et in ets]
    margins = {body: np.array([m[body] for _, m in samples]) for body in BODIES}

    events: list[HorizonEvent] = []
    unknown_from: dict[str, float | None] = {}
    for body in BODIES:
        values = margins[body]
        unknown = np.flatnonzero(~np.isfinite(values))
        unknown_from[body] = float(ets[unknown[0]]) if len(unknown) else None
        for i in range(count):
            a, b = values[i], values[i + 1]
            if not (np.isfinite(a) and np.isfinite(b)) or (a > 0) == (b > 0):
                continue
            lo, hi = float(ets[i]), float(ets[i + 1])
            while hi - lo > tolerance_seconds:
                mid = 0.5 * (lo + hi)
                value = _margins(latitude_deg, longitude_deg, mid, horizon_mask)[1][body]
                if not np.isfinite(value):
                    break
                if (value > 0) == (a > 0):
                    lo = mid
                else:
                    hi = mid
            crossing = 0.5 * (lo + hi)
            events.append(HorizonEvent(body, "rise" if b > 0 else "set",
                                       _et_to_utc(crossing), (crossing - et0) / 3600.0))
    events.sort(key=lambda event: event.hours_from_start)

    state0 = samples[0][0]
    window_hours = duration_days * 24.0

    def countdown(body: str, kind: str) -> tuple[float | None, str]:
        nxt = next((e for e in events if e.body == body and e.kind == kind), None)
        blocked = unknown_from[body]
        if nxt is not None and (blocked is None or nxt.hours_from_start * 3600.0 + et0 <= blocked):
            return nxt.hours_from_start, "complete"
        if blocked is not None:
            return None, "terrain_horizon_incomplete"
        return None, f"no_{body}{kind}_within_window"

    def body_block(body: str, elevation: float, azimuth: float, up_key: str,
                   down_word: str, up_word: str, radius_deg: float) -> dict[str, object]:
        margin = margins[body][0]
        is_up = bool(margin > 0) if np.isfinite(margin) else None
        set_hours, set_status = countdown(body, "set")
        rise_hours, rise_status = countdown(body, "rise")
        return {
            "azimuth_deg": azimuth,
            "elevation_deg": elevation,
            "terrain_horizon_deg": _horizon_at(horizon_mask, azimuth),
            up_key: is_up,
            f"time_to_{down_word}_hours": set_hours if is_up else None,
            f"time_to_{down_word}_formatted": format_countdown(set_hours) if is_up else None,
            f"time_to_{up_word}_hours": rise_hours if is_up is False else None,
            f"time_to_{up_word}_formatted": format_countdown(rise_hours) if is_up is False else None,
            "countdown_status": ("terrain_horizon_incomplete" if is_up is None
                                 else set_status if is_up else rise_status),
            "fraction_of_window_up": (float(np.mean(margins[body] > 0))
                                      if np.isfinite(margins[body]).all() else None),
            "angular_radius_deg": radius_deg,
            "disk_visible_fraction": disk_visible_fraction(margin, radius_deg),
        }

    earth = body_block("earth", state0.earth_elevation_deg, state0.earth_azimuth_deg,
                       "direct_los", "earthset", "earthrise",
                       angular_radius_deg(EARTH_RADIUS_KM, state0.earth_range_km))
    earth["range_km"] = state0.earth_range_km
    earth["round_trip_light_time_s"] = 2.0 * state0.earth_range_km / SPEED_OF_LIGHT_KM_S
    return {
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "start_utc": normalized_start,
        "duration_days": duration_days,
        "window_hours": window_hours,
        "horizon_model": "spherical_horizon" if horizon_mask is None else "lola_terrain_mask",
        "visibility_rule": "body centre elevation > horizon elevation at body azimuth",
        "disk_rule": "disk_visible_fraction: exact disc-segment area above a locally straight horizon",
        "scan_step_minutes": step_minutes,
        "tolerance_seconds": tolerance_seconds,
        "sun": body_block("sun", state0.sun_elevation_deg, state0.sun_azimuth_deg,
                          "is_lit", "sunset", "sunrise",
                          angular_radius_deg(SUN_RADIUS_KM, state0.sun_range_km)),
        "earth": earth,
        "events": [event.to_dict() for event in events],
    }


@spice_serialized(ensure_kernels=True)
def calculate_geometry_track(
    latitude_deg: float,
    longitude_deg: float,
    start_utc: str,
    duration_days: float = 14.0,
    *,
    step_minutes: float = 60.0,
    horizon_mask: _HorizonLike | None = None,
    decimals: int = 4,
) -> dict[str, object]:
    """Precompute a column-oriented Sun/Earth track for a timeline scrubber.

    Columns are parallel arrays so a client can interpolate between samples
    at display frame rate without further SPICE work. Unit vectors are
    observer-to-body directions in MOON_PA. ``sun_lit``/``earth_los`` are
    ``None`` where the terrain horizon is unknown.
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    _, normalized_start = _parse_utc(start_utc)
    if not np.isfinite(duration_days) or duration_days <= 0:
        raise ValueError("duration_days must be positive")
    if not np.isfinite(step_minutes) or step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    et0 = spice.str2et(normalized_start)
    count = int(np.floor(duration_days * 1440.0 / step_minutes)) + 1
    columns: dict[str, list] = {key: [] for key in (
        "utc", "hours_from_start", "sun_elevation_deg", "sun_azimuth_deg",
        "sun_terrain_horizon_deg", "sun_lit", "sun_disk_visible_fraction",
        "earth_elevation_deg", "earth_azimuth_deg", "earth_terrain_horizon_deg", "earth_los",
        "earth_disk_visible_fraction", "earth_range_km",
        "round_trip_light_time_s", "sun_unit_moon_pa", "earth_unit_moon_pa")}

    def r(value: float) -> float | None:
        return round(float(value), decimals) if np.isfinite(value) else None

    for index in range(count):
        et = et0 + index * step_minutes * 60.0
        state = _topocentric_state(latitude_deg, longitude_deg, et)
        sun_h = _horizon_at(horizon_mask, state.sun_azimuth_deg)
        earth_h = _horizon_at(horizon_mask, state.earth_azimuth_deg)
        columns["utc"].append(_et_to_utc(et))
        columns["hours_from_start"].append(r(index * step_minutes / 60.0))
        columns["sun_elevation_deg"].append(r(state.sun_elevation_deg))
        columns["sun_azimuth_deg"].append(r(state.sun_azimuth_deg))
        columns["sun_terrain_horizon_deg"].append(r(sun_h))
        columns["sun_lit"].append(bool(state.sun_elevation_deg > sun_h) if np.isfinite(sun_h) else None)
        sun_fraction = disk_visible_fraction(
            state.sun_elevation_deg - sun_h, angular_radius_deg(SUN_RADIUS_KM, state.sun_range_km))
        columns["sun_disk_visible_fraction"].append(None if sun_fraction is None else r(sun_fraction))
        columns["earth_elevation_deg"].append(r(state.earth_elevation_deg))
        columns["earth_azimuth_deg"].append(r(state.earth_azimuth_deg))
        columns["earth_terrain_horizon_deg"].append(r(earth_h))
        columns["earth_los"].append(bool(state.earth_elevation_deg > earth_h) if np.isfinite(earth_h) else None)
        earth_fraction = disk_visible_fraction(
            state.earth_elevation_deg - earth_h, angular_radius_deg(EARTH_RADIUS_KM, state.earth_range_km))
        columns["earth_disk_visible_fraction"].append(None if earth_fraction is None else r(earth_fraction))
        columns["earth_range_km"].append(round(state.earth_range_km, 1))
        columns["round_trip_light_time_s"].append(
            round(2.0 * state.earth_range_km / SPEED_OF_LIGHT_KM_S, 4))
        columns["sun_unit_moon_pa"].append([r(v) for v in state.sun_unit_moon_pa])
        columns["earth_unit_moon_pa"].append([r(v) for v in state.earth_unit_moon_pa])

    def percent(flags: list[bool | None]) -> float | None:
        return None if any(f is None for f in flags) else round(100.0 * sum(flags) / len(flags), 2)

    def mean(values: list[float | None]) -> float | None:
        return None if any(v is None for v in values) else round(float(np.mean(values)), 4)

    def partial_percent(values: list[float | None]) -> float | None:
        if any(v is None for v in values):
            return None
        return round(100.0 * sum(0.0 < v < 1.0 for v in values) / len(values), 2)

    return {
        "schema": "apolloharness.geometry_track.v1",
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "start_utc": normalized_start,
        "duration_days": duration_days,
        "step_minutes": step_minutes,
        "samples": count,
        "frame": "MOON_PA (vectors); azimuth clockwise from north",
        "horizon_model": "spherical_horizon" if horizon_mask is None else "lola_terrain_mask",
        "sunlit_percent": percent(columns["sun_lit"]),
        "earth_los_percent": percent(columns["earth_los"]),
        "mean_sun_disk_visible_fraction": mean(columns["sun_disk_visible_fraction"]),
        "sun_partially_blocked_percent": partial_percent(columns["sun_disk_visible_fraction"]),
        "earth_partially_blocked_percent": partial_percent(columns["earth_disk_visible_fraction"]),
        "columns": columns,
    }


if __name__ == "__main__":
    load_kernels()

    try:
        latitude = -84.79
        longitude = 29.20

        geometry = calculate_hourly_geometry(
            latitude_deg=latitude,
            longitude_deg=longitude,
            start_utc="2026-10-20T00:00:00Z",
            hours=24,
        )

        summary = summarize_communications(
            geometry
        )

        print(
            f"Location: {latitude}°, {longitude}°"
        )

        print(
            f"Communication uptime: "
            f"{summary.uptime_percent:.2f}%"
        )

        print(
            f"Longest blackout: "
            f"{summary.longest_blackout_hours:.1f} hours"
        )

        print("\nFirst 5 hourly observations:")

        for item in geometry[:5]:
            print(
                item.utc,
                f"Earth elevation={item.earth_elevation_deg:.3f}°",
                f"Earth azimuth={item.earth_azimuth_deg:.3f}°",
                f"Sun elevation={item.sun_elevation_deg:.3f}°",
                f"Sun azimuth={item.sun_azimuth_deg:.3f}°",
                f"Earth visible={item.earth_visible}",
            )

    finally:
        unload_kernels()
