from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

    observer = _observer_position(
        latitude_deg,
        longitude_deg,
        et,
    )

    east, north, up = _local_basis(
        latitude_deg,
        longitude_deg,
        et,
    )

    earth_moon, _ = spice.spkpos(
        "EARTH",
        et,
        "MOON_PA",
        "NONE",
        "MOON",
    )

    sun_moon, _ = spice.spkpos(
        "SUN",
        et,
        "MOON_PA",
        "NONE",
        "MOON",
    )

    earth_vector = earth_moon - observer
    sun_vector = sun_moon - observer

    earth_elevation, earth_azimuth = _elevation_azimuth(
        earth_vector,
        east,
        north,
        up,
    )

    sun_elevation, sun_azimuth = _elevation_azimuth(
        sun_vector,
        east,
        north,
        up,
    )

    return HourlyGeometry(
        utc=normalized_utc,
        earth_elevation_deg=earth_elevation,
        earth_azimuth_deg=earth_azimuth,
        sun_elevation_deg=sun_elevation,
        sun_azimuth_deg=sun_azimuth,
        earth_visible=earth_elevation > 0.0,
    )


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


def calculate_hourly_geometry(
    latitude_deg: float,
    longitude_deg: float,
    start_utc: str,
    hours: int,
) -> list[HourlyGeometry]:
    """
    Calculate hourly Earth/Sun geometry over a mission window.
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    start, _ = _parse_utc(start_utc)
    if hours < 0:
        raise ValueError("hours must be non-negative")

    results: list[HourlyGeometry] = []

    for hour in range(hours):
        current = start + timedelta(hours=hour)

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
