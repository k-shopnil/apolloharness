"""Extraction of annual polar illumination from LROC/LOLA raster products."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
import rasterio
from pyproj import Transformer
from .terrain import MOON_GEOGRAPHIC, PROJECT_ROOT

DEFAULT_PRODUCT = PROJECT_ROOT / "data" / "illumination" / "annual_south_pole.tif"


def annual_illumination(latitude_deg: float, longitude_deg: float,
                        raster_path: str | Path = DEFAULT_PRODUCT) -> dict[str, Any]:
    """Read the annual illumination percentage/value at a point from a raster.

    The input product is an authoritative LROC/LOLA annual illumination raster;
    this function does not estimate annual illumination from a mission window.
    """
    path = Path(raster_path)
    if not path.is_file():
        raise FileNotFoundError(f"Annual illumination product not found: {path}. "
                                "Place the NASA/LOLA or LROC annual product here.")
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError("Annual illumination raster has no CRS")
        x, y = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True).transform(
            longitude_deg, latitude_deg)
        value = np.ma.asarray(next(ds.sample([(x, y)], masked=True))).filled(np.nan)[0]
        if not np.isfinite(value):
            raise ValueError("Coordinate is outside valid annual illumination raster pixels")
        if value > 1:
            percent = float(value)
        else:
            percent = float(value * 100.0)
        if not 0 <= percent <= 100:
            raise ValueError(f"Annual illumination value outside expected range: {value}")
        return {"analysis_type": "annual_strategic_illumination", "latitude_deg": latitude_deg,
                "longitude_deg": longitude_deg, "illumination_percent": percent,
                "source_raster": str(path), "source_crs": ds.crs.to_string()}
