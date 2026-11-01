"""Vectorized exact physics for many candidate points at once.

The single-site API (``site_evaluation``) costs ~0.3 s per point. Regional
screening and validation need thousands of points, so this module computes
the same quantities in bulk without approximation:

* Sun/Earth directions come from one SPICE call per epoch in ``MOON_ME``;
  the per-point topocentric direction is ``body - observer`` in vector form,
  so parallax is exact (it matters for Earth: ~0.015 deg across 100 km).
* Horizon masks for all points are traced on one in-memory DEM array with
  the same bilinear sampling, curvature and completeness rules as
  ``terrain.extract_horizon_mask_fast``.

Results agree with the single-site functions to floating-point precision
(see ``tests/test_regional.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import spiceypy as spice
from pyproj import Transformer
from rasterio.windows import Window

from .spice_engine import (
    EARTH_RADIUS_KM, SPICE_LOCK, SUN_RADIUS_KM, _parse_utc, _site_frame_me, load_kernels,
)
from .terrain import (
    DEFAULT_DEM, HORIZON_MAX_DISTANCE_M, MOON_GEOGRAPHIC, MULTIRES_MAX_PIXEL_M, NEAR_FIELD_M,
    _fractional_index, _Grid, _projected_local_axes, _validate_dem_crs, cached_transformer,
    coarse_grid,
    trace_horizon,
)


@dataclass(frozen=True)
class BodyTracks:
    """Body positions relative to the Moon centre in MOON_ME, km, per epoch."""
    ets: np.ndarray
    sun_me_km: np.ndarray    # (T, 3)
    earth_me_km: np.ndarray  # (T, 3)


def body_tracks(epochs_et: np.ndarray) -> BodyTracks:
    """One SPICE query per epoch and body (geometric, no aberration correction)."""
    ets = np.asarray(epochs_et, dtype=float)
    with SPICE_LOCK:
        load_kernels()
        sun = np.array([spice.spkpos("SUN", et, "MOON_ME", "NONE", "MOON")[0] for et in ets])
        earth = np.array([spice.spkpos("EARTH", et, "MOON_ME", "NONE", "MOON")[0] for et in ets])
    return BodyTracks(ets, sun, earth)


def epochs_between(start_utc: str, duration_days: float, step_hours: float) -> np.ndarray:
    _, normalized = _parse_utc(start_utc)
    with SPICE_LOCK:
        load_kernels()
        et0 = spice.str2et(normalized)
    count = int(np.floor(duration_days * 24.0 / step_hours)) + 1
    return et0 + np.arange(count) * step_hours * 3600.0


def site_frames(latitudes: np.ndarray, longitudes: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Observer positions (N,3) km and E/N/U unit axes (N,3 each) in MOON_ME."""
    with SPICE_LOCK:
        load_kernels()
        frames = [_site_frame_me(float(lat), float(lon))
                  for lat, lon in zip(latitudes, longitudes)]
    positions = np.array([f[0] for f in frames])
    east = np.array([f[1][0] for f in frames])
    north = np.array([f[1][1] for f in frames])
    up = np.array([f[1][2] for f in frames])
    return positions, east, north, up


def topocentric(body_me_km: np.ndarray, positions: np.ndarray, east: np.ndarray,
                north: np.ndarray, up: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Elevation, azimuth (deg) and range (km) as (N, T) arrays."""
    vectors = body_me_km[None, :, :] - positions[:, None, :]          # (N, T, 3)
    ranges = np.linalg.norm(vectors, axis=2)
    unit = vectors / ranges[..., None]
    elevation = np.degrees(np.arcsin(np.clip(np.einsum("ntk,nk->nt", unit, up), -1.0, 1.0)))
    azimuth = np.degrees(np.arctan2(np.einsum("ntk,nk->nt", unit, east),
                                    np.einsum("ntk,nk->nt", unit, north))) % 360.0
    return elevation, azimuth, ranges


def horizon_lookup(masks: np.ndarray, azimuth_step_deg: float, azimuth: np.ndarray) -> np.ndarray:
    """Linear interpolation of per-point masks (N, A) at azimuths (N, T)."""
    count = masks.shape[1]
    position = (azimuth % 360.0) / azimuth_step_deg
    lower = np.floor(position).astype(int) % count
    upper = (lower + 1) % count
    fraction = position - np.floor(position)
    rows = np.arange(masks.shape[0])[:, None]
    return masks[rows, lower] * (1.0 - fraction) + masks[rows, upper] * fraction


def disk_fraction(margin_deg: np.ndarray, radius_deg: np.ndarray) -> np.ndarray:
    """Vectorized ``spice_engine.disk_visible_fraction`` (NaN where unknown)."""
    h = np.clip(margin_deg / radius_deg, -1.0, 1.0)
    return 1.0 - (np.arccos(h) - h * np.sqrt(1.0 - h * h)) / np.pi


class DemArray:
    """A DEM held in memory (whole or a window) for repeated bulk sampling.

    Horizon tracing uses ``terrain.trace_horizon`` (the same code as the
    single-site path), including the cached far-field grid for fine DEMs.
    """

    def __init__(self, dem_path: str | Path = DEFAULT_DEM, *,
                 bounds_xy: tuple[float, float, float, float] | None = None):
        self.dem_path = Path(dem_path)
        with rasterio.open(dem_path) as ds:
            _validate_dem_crs(ds)
            self.crs = ds.crs
            if bounds_xy is None:
                window = Window(0, 0, ds.width, ds.height)
            else:
                xmin, ymin, xmax, ymax = bounds_xy
                rows, cols = _fractional_index(ds, np.array([xmin, xmax]), np.array([ymax, ymin]))
                r0, c0 = max(int(np.floor(rows.min())) - 2, 0), max(int(np.floor(cols.min())) - 2, 0)
                r1 = min(int(np.ceil(rows.max())) + 3, ds.height)
                c1 = min(int(np.ceil(cols.max())) + 3, ds.width)
                window = Window(c0, r0, c1 - c0, r1 - r0)
            self.grid = _Grid.from_window(ds, window)
        self.pixel_m = self.grid.pixel_m
        self.to_map = cached_transformer(MOON_GEOGRAPHIC, self.crs)

    def _xy(self, latitudes: np.ndarray, longitudes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x, y = self.to_map.transform(np.asarray(longitudes, float), np.asarray(latitudes, float))
        return np.asarray(x), np.asarray(y)

    def elevation(self, latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
        return self.grid.sample(*self._xy(latitudes, longitudes))

    def slope_deg(self, latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
        """Surface slope from central differences over one pixel (DEM baseline).

        At 80 m/pixel this is a regional slope; lander-footprint (few-metre)
        slopes need a finer DEM and are typically steeper.
        """
        x, y = self._xy(latitudes, longitudes)
        d = self.pixel_m
        dzdx = (self.grid.sample(x + d, y) - self.grid.sample(x - d, y)) / (2 * d)
        dzdy = (self.grid.sample(x, y + d) - self.grid.sample(x, y - d)) / (2 * d)
        return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))

    def horizon_masks(self, latitudes: np.ndarray, longitudes: np.ndarray, *,
                      max_distance_m: float = HORIZON_MAX_DISTANCE_M, radial_step_m: float = 80.0,
                      azimuth_step_deg: float = 1.0, observer_height_m: float = 1.5,
                      near_field_m: float = NEAR_FIELD_M) -> np.ndarray:
        """(N, A) horizon elevations; NaN where a ray leaves valid DEM pixels."""
        lats = np.asarray(latitudes, float)
        lons = np.asarray(longitudes, float)
        multires = self.pixel_m < MULTIRES_MAX_PIXEL_M and max_distance_m > near_field_m
        coarse = coarse_grid(self.dem_path) if multires else None
        base = self.elevation(lats, lons)
        out = np.full((len(lats), int(round(360.0 / azimuth_step_deg))), np.nan)
        for i in range(len(lats)):
            if not np.isfinite(base[i]):
                continue
            x0, y0, east_xy, north_xy = _projected_local_axes(self.to_map, lats[i], lons[i])
            _, out[i] = trace_horizon(
                self.grid, coarse, x0, y0, east_xy, north_xy, base[i] + observer_height_m,
                max_distance_m=max_distance_m, radial_step_m=radial_step_m,
                azimuth_step_deg=azimuth_step_deg,
                near_field_m=near_field_m if coarse is not None else max_distance_m)
        return out


def visibility_statistics(latitudes: np.ndarray, longitudes: np.ndarray, masks: np.ndarray,
                          azimuth_step_deg: float, tracks: BodyTracks) -> dict[str, np.ndarray]:
    """Per-point sunlit / Earth-LOS fractions and mean disc visibility over epochs.

    Points with any unknown horizon azimuth crossed by a body get NaN for
    that body's statistics rather than an optimistic or pessimistic guess.
    """
    positions, east, north, up = site_frames(latitudes, longitudes)
    result: dict[str, np.ndarray] = {}
    for name, track, radius in (("sun", tracks.sun_me_km, SUN_RADIUS_KM),
                                ("earth", tracks.earth_me_km, EARTH_RADIUS_KM)):
        elevation, azimuth, ranges = topocentric(track, positions, east, north, up)
        horizon = horizon_lookup(masks, azimuth_step_deg, azimuth)
        margin = elevation - horizon
        known = np.isfinite(margin).all(axis=1)
        up_fraction = np.where(known, np.nanmean(margin > 0, axis=1), np.nan)
        disc = disk_fraction(margin, np.degrees(np.arcsin(radius / ranges)))
        result[f"{name}_up_fraction"] = up_fraction
        result[f"{name}_mean_disk_fraction"] = np.where(known, np.nanmean(disc, axis=1), np.nan)
        result[f"{name}_mean_elevation_deg"] = elevation.mean(axis=1)
        # Longest continuous run without the body (in samples) — darkness/blackout.
        down = ~(margin > 0)
        longest = np.zeros(len(latitudes))
        run = np.zeros(len(latitudes))
        for column in down.T:
            run = np.where(column, run + 1, 0)
            longest = np.maximum(longest, run)
        result[f"{name}_longest_down_samples"] = np.where(known, longest, np.nan)
    return result


def candidate_grid(center_lat: float, center_lon: float, radius_m: float, spacing_m: float,
                   to_map: Transformer) -> tuple[np.ndarray, np.ndarray]:
    """Regular map-space grid within ``radius_m`` of a centre, as lat/lon arrays."""
    x0, y0 = to_map.transform(center_lon, center_lat)
    offsets = np.arange(-radius_m, radius_m + spacing_m / 2, spacing_m)
    xx, yy = np.meshgrid(x0 + offsets, y0 + offsets)
    inside = np.hypot(xx - x0, yy - y0) <= radius_m
    lon, lat = to_map.transform(xx[inside], yy[inside], direction="INVERSE")
    return np.asarray(lat), (np.asarray(lon) + 180.0) % 360.0 - 180.0


def screen_region(center_lat: float, center_lon: float, start_utc: str, *,
                  radius_m: float = 5_000.0, spacing_m: float = 500.0,
                  duration_days: float = 14.0, step_hours: float = 1.0,
                  max_distance_m: float = HORIZON_MAX_DISTANCE_M, azimuth_step_deg: float = 1.0,
                  radial_step_m: float = 80.0, dem_path: str | Path = DEFAULT_DEM,
                  include_psr: bool = True, psr_search_radius_m: float = 20_000.0
                  ) -> dict[str, object]:
    """Exact-physics screening of a candidate grid around a polar site.

    Returns column arrays (lat, lon, elevation, slope, sunlit/Earth-LOS
    percentages, mean solar-disc fraction, longest darkness/blackout hours,
    distance to the nearest PSR cold trap) for every grid point inside the
    80 m polar DEM.
    """
    if radius_m <= 0 or spacing_m <= 0:
        raise ValueError("radius_m and spacing_m must be positive")
    with rasterio.open(dem_path) as ds:
        to_map = cached_transformer(MOON_GEOGRAPHIC, ds.crs)
    lat, lon = candidate_grid(center_lat, center_lon, radius_m, spacing_m, to_map)
    x0, y0 = to_map.transform(center_lon, center_lat)
    # Fine window only needs the near field; the far field uses the cached coarse grid.
    reach = radius_m + min(max_distance_m, NEAR_FIELD_M) + 1_000.0
    dem = DemArray(dem_path, bounds_xy=(x0 - reach, y0 - reach, x0 + reach, y0 + reach))
    elevation = dem.elevation(lat, lon)
    keep = np.isfinite(elevation)
    lat, lon, elevation = lat[keep], lon[keep], elevation[keep]
    slope = dem.slope_deg(lat, lon)
    masks = dem.horizon_masks(lat, lon, max_distance_m=max_distance_m,
                              radial_step_m=radial_step_m, azimuth_step_deg=azimuth_step_deg)
    tracks = body_tracks(epochs_between(start_utc, duration_days, step_hours))
    stats = visibility_statistics(lat, lon, masks, azimuth_step_deg, tracks)
    psr_m = np.full(len(lat), np.nan)
    psr_status = "not_requested"
    if include_psr:
        from .proximity import DEFAULT_PSR, psr_distances
        if lat.size and lat.max() <= -79.0 and DEFAULT_PSR.is_file():
            psr_m = psr_distances(lat, lon, search_radius_m=psr_search_radius_m)
            psr_status = "complete"
        else:
            psr_status = "outside_product_coverage_or_not_installed"

    def pct(values: np.ndarray) -> list[float | None]:
        return [None if not np.isfinite(v) else round(100.0 * float(v), 2) for v in values]

    def hours(values: np.ndarray) -> list[float | None]:
        return [None if not np.isfinite(v) else float(v) * step_hours for v in values]

    return {
        "schema": "apolloharness.region_screen.v1",
        "center_lat_deg": center_lat, "center_lon_deg": center_lon,
        "start_utc": _parse_utc(start_utc)[1], "duration_days": duration_days,
        "step_hours": step_hours, "radius_m": radius_m, "spacing_m": spacing_m,
        "horizon": {"max_distance_m": max_distance_m, "azimuth_step_deg": azimuth_step_deg,
                    "radial_step_m": radial_step_m, "dem_resolution_m": dem.pixel_m},
        "count": int(len(lat)),
        "columns": {
            "latitude_deg": lat.round(6).tolist(),
            "longitude_deg": lon.round(6).tolist(),
            "elevation_m": elevation.round(1).tolist(),
            "slope_deg": [None if not np.isfinite(v) else round(float(v), 2) for v in slope],
            "sunlit_percent": pct(stats["sun_up_fraction"]),
            "mean_sun_disk_percent": pct(stats["sun_mean_disk_fraction"]),
            "earth_los_percent": pct(stats["earth_up_fraction"]),
            "longest_darkness_hours": hours(stats["sun_longest_down_samples"]),
            "longest_earth_blackout_hours": hours(stats["earth_longest_down_samples"]),
            "psr_distance_m": [None if not np.isfinite(v) else round(float(v), 1) for v in psr_m],
        },
        "psr": {"status": psr_status, "search_radius_m": psr_search_radius_m,
                "null_means": "no PSR within search radius (distance > search_radius_m)"},
    }
