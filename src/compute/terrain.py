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
MOON_GEOGRAPHIC = CRS.from_proj4(
    f"+proj=longlat +a={MOON_RADIUS_M} +b={MOON_RADIUS_M} +no_defs"
)
MOON_SPS = CRS.from_proj4(
    f"+proj=stere +lat_0=-90 +lon_0=0 +k=1 +a={MOON_RADIUS_M} "
    f"+b={MOON_RADIUS_M} +units=m +no_defs"
)


@dataclass(frozen=True)
class HorizonMask:
    """Terrain horizon elevation angles indexed by north-clockwise azimuth."""
    azimuth_deg: np.ndarray
    elevation_deg: np.ndarray

    def elevation_at(self, azimuth_deg: float) -> float:
        if len(self.azimuth_deg) != len(self.elevation_deg) or not len(self.azimuth_deg):
            raise ValueError("Horizon mask must contain matching, non-empty arrays")
        return float(np.interp(azimuth_deg % 360.0, self.azimuth_deg, self.elevation_deg,
                               period=360.0))


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
    with rasterio.open(dem_path) as ds:
        if ds.crs is None or not ds.crs.is_projected:
            raise ValueError("LOLA DEM must declare a projected lunar CRS")
        if ds.crs.axis_info and any((axis.unit_name or "").lower() not in {"metre", "meter"}
                                    for axis in ds.crs.axis_info[:2]):
            raise ValueError("LOLA DEM projected axes must use meters")
        tx = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
        x0, y0 = tx.transform(longitude_deg, latitude_deg)
        distances = np.arange(radial_step_m, max_distance_m + radial_step_m, radial_step_m)
        azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
        angles = np.full(azimuths.shape, np.nan)
        base = ds.sample([(x0, y0)], masked=True)
        base_value = np.ma.asarray(next(base)).filled(np.nan)[0]
        if not np.isfinite(base_value):
            raise ValueError("Observer coordinate falls outside valid LOLA DEM pixels")
        for i, az in enumerate(azimuths):
            theta = np.radians(az)
            coords = [(x0 + d * np.sin(theta), y0 + d * np.cos(theta)) for d in distances]
            heights = np.ma.vstack(list(ds.sample(coords, masked=True))).filled(np.nan)[:, 0]
            valid = np.isfinite(heights)
            if valid.any():
                angles[i] = np.degrees(np.arctan2(heights[valid] - base_value - observer_height_m,
                                                   distances[valid]))
        if not np.isfinite(angles).any():
            raise ValueError("No valid terrain samples found around observer")
        angles = np.where(np.isfinite(angles), angles, -90.0)
        return HorizonMask(azimuths, angles)
