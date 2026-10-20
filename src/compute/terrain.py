"""LOLA DEM access and observer-centered terrain horizon sampling.

Raster coordinates must describe a lunar south-polar stereographic grid in
meters (MOON_SPS). Dataset-specific frame metadata should be checked before use.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
MOON_RADIUS_M = 1_737_400.0
MOON_ME_GEOGRAPHIC = CRS.from_proj4(
    f"+proj=longlat +a={MOON_RADIUS_M} +b={MOON_RADIUS_M} "
    "+type=crs +no_defs"
)
MOON_ME_SPS = CRS.from_proj4(
    f"+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 "
    f"+a={MOON_RADIUS_M} +b={MOON_RADIUS_M} +units=m +type=crs +no_defs"
)
# Backwards-compatible names; coordinates in NASA PGDA products use MOON_ME.
MOON_GEOGRAPHIC = MOON_ME_GEOGRAPHIC
MOON_SPS = MOON_ME_SPS


@dataclass(frozen=True)
class HorizonMask:
    """Terrain horizon elevation angles indexed by north-clockwise azimuth."""
    azimuth_deg: np.ndarray
    elevation_deg: np.ndarray

    def elevation_at(self, azimuth_deg: float) -> float:
        if len(self.azimuth_deg) != len(self.elevation_deg) or not len(self.azimuth_deg):
            raise ValueError("Horizon mask must contain matching, non-empty arrays")
        azimuth = azimuth_deg % 360.0
        step = float(self.azimuth_deg[1] - self.azimuth_deg[0]) if len(self.azimuth_deg) > 1 else 360.0
        position = azimuth / step
        lower = int(np.floor(position)) % len(self.azimuth_deg)
        fraction = position - np.floor(position)
        upper = (lower + 1) % len(self.azimuth_deg)
        if np.isclose(fraction, 0.0):
            return float(self.elevation_deg[lower])
        low, high = self.elevation_deg[lower], self.elevation_deg[upper]
        if not np.isfinite(low) or not np.isfinite(high):
            return float("nan")
        return float(low + fraction * (high - low))


def extract_horizon_mask(
    dem_path: str | Path, latitude_deg: float, longitude_deg: float, *,
    max_distance_m: float = 20_000.0, radial_step_m: float = 100.0,
    azimuth_step_deg: float = 1.0, observer_height_m: float = 1.5,
) -> HorizonMask:
    """Sample 360 radial terrain profiles from a projected lunar DEM.

    Elevation is the maximum apparent terrain angle along each radial profile.
    Uses the input GeoTIFF's declared CRS and rejects geographic/non-metric rasters.
    """
    if not (-90 <= latitude_deg <= 90) or not (-180 <= longitude_deg <= 180):
        raise ValueError("Latitude/longitude out of range")
    if min(max_distance_m, radial_step_m, azimuth_step_deg) <= 0:
        raise ValueError("Sampling distances and azimuth step must be positive")
    if not np.isclose(360.0 / azimuth_step_deg, round(360.0 / azimuth_step_deg)):
        raise ValueError("azimuth_step_deg must divide 360 evenly")
    with rasterio.open(dem_path) as ds:
        if ds.crs is None or not ds.crs.is_projected:
            raise ValueError("LOLA DEM must declare a projected lunar CRS")
        pyproj_crs = CRS.from_user_input(ds.crs)
        if pyproj_crs.axis_info and any(
            (axis.unit_name or "").lower() not in {"metre", "meter"}
            for axis in pyproj_crs.axis_info[:2]
        ):
            raise ValueError("LOLA DEM projected axes must use meters")
        tx = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
        x0, y0 = tx.transform(longitude_deg, latitude_deg)
        delta_lat_deg = 1.0e-4
        cosine = max(abs(float(np.cos(np.radians(latitude_deg)))), 1.0e-6)
        x_east, y_east = tx.transform(
            longitude_deg + delta_lat_deg / cosine, latitude_deg
        )
        x_north, y_north = tx.transform(
            longitude_deg, min(90.0, latitude_deg + delta_lat_deg)
        )
        east_xy = np.array([x_east - x0, y_east - y0], dtype=float)
        north_xy = np.array([x_north - x0, y_north - y0], dtype=float)
        east_xy /= np.linalg.norm(east_xy)
        north_xy /= np.linalg.norm(north_xy)
        distances = np.arange(radial_step_m, max_distance_m + radial_step_m, radial_step_m)
        azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
        angles = np.full(azimuths.shape, np.nan)
        base = ds.sample([(x0, y0)], masked=True)
        base_value = np.ma.asarray(next(base), dtype=float).filled(np.nan)[0]
        if not np.isfinite(base_value):
            raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
        for i, az in enumerate(azimuths):
            theta = np.radians(az)
            projected_direction = east_xy * np.sin(theta) + north_xy * np.cos(theta)
            coords = [(x0 + d * projected_direction[0],
                       y0 + d * projected_direction[1]) for d in distances]
            heights = np.ma.vstack(list(ds.sample(coords, masked=True)), dtype=float).filled(np.nan)[:, 0]
            valid = np.isfinite(heights)
            # A horizon is valid only when the requested radial extent is
            # fully covered; partial coverage cannot prove there is no farther obstruction.
            if valid.all():
                # Account for lunar curvature: DEM heights are relative to a
                # reference sphere, not a locally flat tangent plane.
                angular_distance = distances[valid] / MOON_RADIUS_M
                terrain_radius = MOON_RADIUS_M + heights[valid]
                observer_radius = MOON_RADIUS_M + base_value + observer_height_m
                vertical = terrain_radius * np.cos(angular_distance) - observer_radius
                horizontal = terrain_radius * np.sin(angular_distance)
                radial_angles = np.degrees(np.arctan2(vertical, horizontal))
                angles[i] = float(np.max(radial_angles))
        if not np.isfinite(angles).any():
            raise ValueError("No complete terrain rays found around observer")
        return HorizonMask(azimuths, angles)
