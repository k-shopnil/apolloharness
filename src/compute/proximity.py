"""Metric proximity to authoritative lunar permanently shadowed region data."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from .terrain import MOON_GEOGRAPHIC, MOON_SPS, PROJECT_ROOT

DEFAULT_PSR = PROJECT_ROOT / "data" / "psr" / "LPSR_80S_20MPP_ADJ.SHP"


def calculate_psr_distance(latitude_deg: float, longitude_deg: float,
                           dataset_path: str | Path = DEFAULT_PSR,
                           *, id_column: str | None = None) -> dict[str, Any]:
    """Return metric distance to nearest PSR polygon boundary in MOON_SPS.

    Requires an authoritative vector dataset; missing data raises an explicit error.
    """
    if not np.isfinite(latitude_deg) or not -90 <= latitude_deg <= 90:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg) or not -180 <= longitude_deg <= 180:
        raise ValueError("longitude_deg must be finite and between -180 and 180")
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"PSR dataset not found: {path}. Install an authoritative "
                                "NASA/USGS/PDS PSR boundary dataset at this path.")
    frame = gpd.read_file(path)
    if frame.empty:
        raise ValueError("PSR dataset contains no features")
    if frame.crs is None:
        raise ValueError("PSR dataset CRS is undefined")
    if frame.geometry.isna().any() or frame.geometry.is_empty.any() or not frame.geometry.is_valid.all():
        raise ValueError("PSR dataset contains null, empty, or invalid geometries")
    point = gpd.GeoSeries([Point(longitude_deg, latitude_deg)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
    projected = frame.to_crs(MOON_SPS)
    boundary_distances = projected.geometry.boundary.distance(point)
    index = boundary_distances.idxmin()
    distance_m = float(boundary_distances.loc[index])
    if id_column is None:
        id_column = next((name for name in ("psr_id", "PSR_ID", "id", "ID")
                          if name in projected.columns), None)
    identifier = projected.loc[index, id_column] if id_column else None
    return {"distance_m": distance_m, "distance_km": distance_m / 1000.0,
            "nearest_psr": None if identifier is None else str(identifier),
            "nearest_psr_id": None if identifier is None else str(identifier),
            "source_dataset": str(path), "analysis_crs": MOON_SPS.to_string()}


# Backwards-compatible function name.
nearest_psr = calculate_psr_distance
