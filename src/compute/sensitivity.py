""""Small changes, big effects": how sensitive a site is to where and when.

Near the lunar south pole, sunlight and Earth line of sight are set by
grazing geometry against distant terrain, so a few hundred metres or a few
days can change a site completely. This module quantifies that for any point
inside the 80 m polar DEM (80-90°S), with the same exact physics as the rest
of the engine (``regional``):

* **Position** — every grid point within ``radius_m`` is evaluated over the
  same window. The result reports the spread among neighbours and the best
  neighbour for sunlight and for Earth line of sight, with its distance and
  bearing, so a UI can say "move 300 m north-east: +18 pp of sunlight".
* **Arrival date** — the same site with the arrival slipped by whole days.
* **Observer height** — the horizon traced from the surface, the default
  instrument height and a mast, for sunlight and Earth line of sight.

All percentages are of the analysis window (default 14 days, one lunar
daytime: a typical CLPS surface mission). The site's own horizon must be
complete inside the polar DEM, which holds south of about 83.5°S (100 km
rays); further north the call is refused rather than answered with nulls.
Slopes come from the 80 m DEM, a regional slope: lander-footprint slopes
are steeper, so ``max_regional_slope_deg`` is a screen, not a safety check.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import spiceypy as spice

from .regional import (
    DemArray, body_tracks, candidate_grid, horizon_lookup, site_frames, topocentric,
    visibility_statistics,
)
from .spice_engine import SPICE_LOCK, _parse_utc, _validate_coordinates, load_kernels
from .terrain import DEFAULT_DEM, MOON_GEOGRAPHIC, NEAR_FIELD_M, cached_transformer

SCHEMA = "apolloharness.site_sensitivity.v1"
MOON_RADIUS_M = 1_737_400.0
OBSERVER_HEIGHT_M = 1.5          # engine default (instrument height)
OBSERVER_HEIGHTS_M = (0.0, 1.5, 5.0)
DISTANCE_BANDS_M = (250.0, 500.0, 1_000.0, 2_000.0)
MAX_GRID_POINTS = 2_000
MISSION_WINDOW_DAYS = 14.0       # one lunar daytime, the usual CLPS surface mission          # keeps a request under ~30 s worst case


def _distance_bearing(lat0: float, lon0: float, lat: np.ndarray, lon: np.ndarray
                      ) -> tuple[np.ndarray, np.ndarray]:
    """Great-circle distance (m) and initial true bearing (deg, 0 = north)."""
    p0, l0 = np.radians(lat0), np.radians(lon0)
    p1, l1 = np.radians(lat), np.radians(lon)
    dl = l1 - l0
    a = np.sin((p1 - p0) / 2) ** 2 + np.cos(p0) * np.cos(p1) * np.sin(dl / 2) ** 2
    distance = 2 * MOON_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    bearing = np.degrees(np.arctan2(np.sin(dl) * np.cos(p1),
                                    np.cos(p0) * np.sin(p1) - np.sin(p0) * np.cos(p1) * np.cos(dl)))
    return distance, bearing % 360.0


_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def _compass(bearing_deg: float) -> str:
    return _COMPASS[int(((bearing_deg % 360.0) + 22.5) // 45.0) % 8]


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), digits)


def _spread(values: np.ndarray) -> dict[str, float | None]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"min": None, "p10": None, "median": None, "p90": None, "max": None}
    q = np.percentile(finite, [0, 10, 50, 90, 100])
    return dict(zip(("min", "p10", "median", "p90", "max"), (round(float(v), 2) for v in q)))


def _metric_block(name: str, values: np.ndarray, *, higher_is_better: bool, unit: str,
                  distance: np.ndarray, bearing: np.ndarray, eligible: np.ndarray,
                  lat: np.ndarray, lon: np.ndarray, slope: np.ndarray) -> dict[str, Any]:
    """Centre value, neighbour spread, best neighbour overall and per distance band.

    Index 0 is the centre. Ties are broken toward the nearest point, so a
    flat field never sends the user somewhere for nothing.
    """
    centre = float(values[0])
    sign = 1.0 if higher_is_better else -1.0
    neighbours = np.arange(1, len(values))

    def best_within(limit_m: float) -> dict[str, Any] | None:
        pool = neighbours[(distance[neighbours] <= limit_m) & eligible[neighbours]
                          & np.isfinite(values[neighbours])]
        if pool.size == 0 or not np.isfinite(centre):
            return None
        score = sign * values[pool]
        top = pool[score >= score.max() - 1e-9]
        i = int(top[np.argmin(distance[top])])
        gain = sign * (values[i] - centre) + 0.0
        return {"latitude_deg": round(float(lat[i]), 6), "longitude_deg": round(float(lon[i]), 6),
                "distance_m": round(float(distance[i]), 1),
                "bearing_deg": round(float(bearing[i]), 1), "direction": _compass(bearing[i]),
                "value": _round(values[i]), "improvement": _round(gain),
                "regional_slope_deg": _round(slope[i])}

    overall = best_within(float(distance.max()) if len(distance) > 1 else 0.0)
    bands = {f"within_{int(b)}_m": best_within(b) for b in DISTANCE_BANDS_M
             if b <= float(distance.max()) + 1e-6}
    # Only propose a move that actually improves the metric.
    centre_is_best = overall is None or not (overall["improvement"] or 0) > 0
    if centre_is_best:
        overall = None
    bands = {k: (v if v and (v["improvement"] or 0) > 0 else None) for k, v in bands.items()}
    headline = None
    if overall:
        verb = "raises" if higher_is_better else "cuts"
        fmt = (lambda v: f"{v:.1f}%") if unit == "%" else (lambda v: f"{v:.0f} {unit}")
        headline = (f"Moving {overall['distance_m']:.0f} m {overall['direction']} {verb} "
                    f"{name} from {fmt(centre)} to {fmt(overall['value'])}.")
    return {"unit": unit, "higher_is_better": higher_is_better, "centre": _round(centre),
            "neighbours": _spread(values[1:]), "centre_is_best": centre_is_best,
            "best_neighbour": overall,
            "best_by_distance": bands, "headline": headline}


def _date_sensitivity(dem: DemArray, lat: float, lon: float, et0: float, *,
                      duration_days: float, step_hours: float, slip_days: int) -> list[dict]:
    """Centre-site sunlight / Earth LOS for arrivals slipped by -slip..+slip whole days."""
    mask = dem.horizon_masks(np.array([lat]), np.array([lon]))
    per_day = int(round(24.0 / step_hours))
    window = int(np.floor(duration_days * 24.0 / step_hours)) + 1
    count = 2 * slip_days * per_day + window
    ets = et0 - slip_days * 86_400.0 + np.arange(count) * step_hours * 3600.0
    tracks = body_tracks(ets)
    positions, east, north, up = site_frames(np.array([lat]), np.array([lon]))
    up_series = {}
    for body, track in (("sun", tracks.sun_me_km), ("earth", tracks.earth_me_km)):
        elevation, azimuth, _ = topocentric(track, positions, east, north, up)
        margin = (elevation - horizon_lookup(mask, 1.0, azimuth))[0]
        up_series[body] = np.where(np.isfinite(margin), margin > 0, np.nan)
    rows = []
    for k in range(-slip_days, slip_days + 1):
        start = (k + slip_days) * per_day
        sun = up_series["sun"][start:start + window]
        earth = up_series["earth"][start:start + window]
        with SPICE_LOCK:
            stamp = spice.et2utc(float(ets[start]), "ISOC", 0) + "Z"
        rows.append({"slip_days": k, "start_utc": stamp,
                     "lit_at_arrival": None if np.isnan(sun[0]) else bool(sun[0]),
                     "earth_visible_at_arrival": None if np.isnan(earth[0]) else bool(earth[0]),
                     "sunlit_percent": _round(100 * np.mean(sun)) if np.isfinite(sun).all() else None,
                     "earth_los_percent": (_round(100 * np.mean(earth))
                                           if np.isfinite(earth).all() else None)})
    return rows


def _height_sensitivity(dem: DemArray, lat: float, lon: float, tracks) -> list[dict]:
    rows = []
    for height in OBSERVER_HEIGHTS_M:
        mask = dem.horizon_masks(np.array([lat]), np.array([lon]), observer_height_m=height)
        stats = visibility_statistics(np.array([lat]), np.array([lon]), mask, 1.0, tracks)
        rows.append({"observer_height_m": height,
                     "sunlit_percent": _round(100 * stats["sun_up_fraction"][0]),
                     "earth_los_percent": _round(100 * stats["earth_up_fraction"][0])})
    return rows


def site_sensitivity(latitude_deg: float, longitude_deg: float, utc: str, *,
                     radius_m: float = 1_000.0, spacing_m: float = 100.0,
                     duration_days: float = MISSION_WINDOW_DAYS, step_hours: float = 1.0,
                     slip_days: int = 7, max_regional_slope_deg: float | None = 15.0,
                     dem_path: str | Path = DEFAULT_DEM) -> dict[str, Any]:
    """Position, arrival-date and observer-height sensitivity of one polar site.

    Raises ``ValueError`` for bad input or a point outside the polar DEM
    (map to HTTP 422). Typical latency with the defaults is a few seconds.
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    _, normalized = _parse_utc(utc)
    if not (0 < radius_m <= 5_000.0) or not (spacing_m >= 40.0):
        raise ValueError("radius_m must be in (0, 5000] and spacing_m >= 40")
    if not (1.0 <= duration_days <= 60.0) or not (0.25 <= step_hours <= 6.0):
        raise ValueError("duration_days must be in [1, 60] and step_hours in [0.25, 6]")
    if not (0 <= int(slip_days) <= 15):
        raise ValueError("slip_days must be in [0, 15]")
    with rasterio.open(dem_path) as ds:
        to_map = cached_transformer(MOON_GEOGRAPHIC, ds.crs)
    grid_lat, grid_lon = candidate_grid(latitude_deg, longitude_deg, radius_m, spacing_m, to_map)
    if grid_lat.size > MAX_GRID_POINTS:
        raise ValueError(f"grid of {grid_lat.size} points exceeds {MAX_GRID_POINTS}; "
                         "increase spacing_m or reduce radius_m")
    x0, y0 = to_map.transform(longitude_deg, latitude_deg)
    reach = radius_m + NEAR_FIELD_M + 1_000.0
    dem = DemArray(dem_path, bounds_xy=(x0 - reach, y0 - reach, x0 + reach, y0 + reach))
    lat = np.concatenate([[latitude_deg], grid_lat])
    lon = np.concatenate([[longitude_deg], grid_lon])
    elevation = dem.elevation(lat, lon)
    if not np.isfinite(elevation[0]):
        raise ValueError("site is outside the 80 m polar DEM (80-90°S); "
                         "sensitivity needs real terrain around the site")
    keep = np.isfinite(elevation)
    keep[0] = True
    lat, lon, elevation = lat[keep], lon[keep], elevation[keep]
    # The grid can contain the centre itself; drop exact duplicates of index 0.
    distance, bearing = _distance_bearing(latitude_deg, longitude_deg, lat, lon)
    unique = np.ones(len(lat), bool)
    unique[1:] = distance[1:] > 1.0
    lat, lon, elevation, distance, bearing = (a[unique] for a in (lat, lon, elevation, distance,
                                                                   bearing))
    slope = dem.slope_deg(lat, lon)
    masks = dem.horizon_masks(lat, lon)
    with SPICE_LOCK:
        load_kernels()
        et0 = spice.str2et(normalized)
    count = int(np.floor(duration_days * 24.0 / step_hours)) + 1
    tracks = body_tracks(et0 + np.arange(count) * step_hours * 3600.0)
    stats = visibility_statistics(lat, lon, masks, 1.0, tracks)
    if not (np.isfinite(stats["sun_up_fraction"][0]) and np.isfinite(stats["earth_up_fraction"][0])):
        raise ValueError("the site's horizon reaches beyond the 80 m polar DEM (80-90°S), so "
                         "neighbour comparison would be incomplete; sensitivity is available "
                         "south of about 83.5°S")
    eligible = np.ones(len(lat), bool) if max_regional_slope_deg is None else (
        np.isfinite(slope) & (slope <= max_regional_slope_deg))
    common = dict(distance=distance, bearing=bearing, eligible=eligible, lat=lat, lon=lon,
                  slope=slope)
    position = {
        "sunlit_percent": _metric_block("sunlight", 100 * stats["sun_up_fraction"],
                                        higher_is_better=True, unit="%", **common),
        "earth_los_percent": _metric_block("Earth line of sight", 100 * stats["earth_up_fraction"],
                                           higher_is_better=True, unit="%", **common),
        "longest_darkness_hours": _metric_block(
            "longest darkness", stats["sun_longest_down_samples"] * step_hours,
            higher_is_better=False, unit="h", **common),
        "longest_earth_blackout_hours": _metric_block(
            "longest Earth blackout", stats["earth_longest_down_samples"] * step_hours,
            higher_is_better=False, unit="h", **common),
    }
    return {
        "schema": SCHEMA,
        "site": {"latitude_deg": latitude_deg, "longitude_deg": longitude_deg,
                 "elevation_m": _round(elevation[0], 1), "regional_slope_deg": _round(slope[0])},
        "utc": normalized,
        "window": {"duration_days": duration_days, "step_hours": step_hours},
        "grid": {"radius_m": radius_m, "spacing_m": spacing_m, "points": int(len(lat) - 1),
                 "dem_resolution_m": dem.pixel_m,
                 "max_regional_slope_deg": max_regional_slope_deg,
                 "eligible_points": int(eligible[1:].sum())},
        "observer_height_m": OBSERVER_HEIGHT_M,
        "position": position,
        "arrival_date": _date_sensitivity(dem, latitude_deg, longitude_deg, et0,
                                          duration_days=duration_days, step_hours=step_hours,
                                          slip_days=int(slip_days)),
        "observer_height": _height_sensitivity(dem, latitude_deg, longitude_deg, tracks),
        "notes": [
            "Percentages are of the analysis window starting at utc.",
            "Slopes are 80 m regional DEM slopes; lander-footprint slopes are steeper.",
            "Neighbours steeper than max_regional_slope_deg are never proposed as best.",
        ],
    }
