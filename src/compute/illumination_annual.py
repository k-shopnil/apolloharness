"""Extraction of annual polar illumination from LROC/LOLA raster products."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
import rasterio
from .terrain import MOON_ME_GEOGRAPHIC, PROJECT_ROOT, cached_transformer

DEFAULT_PRODUCT = PROJECT_ROOT / "data" / "illumination" / "annual_south_pole.tif"
# rasterio's CRS.to_string() performs an EPSG authority search (~0.1 s); the
# label never changes for a file, so compute it once per product path.
_CRS_LABELS: dict[str, str] = {}


def _crs_label(path: Path, ds: rasterio.DatasetReader) -> str:
    key = str(path)
    if key not in _CRS_LABELS:
        _CRS_LABELS[key] = ds.crs.to_string()
    return _CRS_LABELS[key]


def calculate_annual_illumination(latitude_deg: float, longitude_deg: float,
                                 raster_path: str | Path = DEFAULT_PRODUCT) -> dict[str, Any]:
    """Read the annual illumination percentage/value at a point from a raster.

    The input product is an authoritative LROC/LOLA annual illumination raster;
    this function does not estimate annual illumination from a mission window.
    """
    if not np.isfinite(latitude_deg) or not -90 <= latitude_deg <= 90:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg) or not -180 <= longitude_deg <= 180:
        raise ValueError("longitude_deg must be finite and between -180 and 180")
    path = Path(raster_path)
    if not path.is_file():
        raise FileNotFoundError(f"Annual illumination product not found: {path}. "
                                "Place the NASA/LOLA or LROC annual product here.")
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError("Annual illumination raster has no CRS")
        x, y = cached_transformer(MOON_ME_GEOGRAPHIC, ds.crs).transform(
            longitude_deg, latitude_deg)
        sample = np.ma.asarray(next(ds.sample([(x, y)], masked=True)), dtype=float)
        raw_value = sample.filled(np.nan)[0]
        if not np.isfinite(raw_value):
            raise ValueError("Coordinate is outside valid annual illumination raster pixels")
        # PGDA solar-illumination GeoTIFF stores int16 values with GeoTIFF
        # scale=0.00004 and offset=0: the scaled value is a fraction of time.
        # Products without fractional scale metadata can store percent values.
        scale = float(ds.scales[0]) if ds.scales else 1.0
        offset = float(ds.offsets[0]) if ds.offsets else 0.0
        scaled_value = float(raw_value) * scale + offset
        percent = scaled_value * 100.0 if scale < 1.0 else scaled_value
        if not 0 <= percent <= 100:
            raise ValueError(f"Annual illumination value outside expected range: {percent}")
        return {"analysis_type": "annual_strategic_illumination", "latitude_deg": latitude_deg,
                "longitude_deg": longitude_deg, "illumination_percent": percent,
                "annual_sunlight_percent": percent,
                "source_raster": str(path), "source_crs": _crs_label(path, ds)}


# Backwards-compatible alias used in early Issue #2 development.
annual_illumination = calculate_annual_illumination
