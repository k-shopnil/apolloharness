"""Metric proximity to authoritative lunar permanently shadowed region data."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import geopandas as gpd
from shapely.geometry import Point
from .terrain import MOON_GEOGRAPHIC, MOON_SPS, PROJECT_ROOT

DEFAULT_PSR = PROJECT_ROOT / "data" / "psr" / "psr_boundaries.gpkg"


def nearest_psr(latitude_deg: float, longitude_deg: float,
                dataset_path: str | Path = DEFAULT_PSR,
                *, id_column: str | None = None) -> dict[str, Any]:
    """Return metric distance to nearest PSR polygon boundary in MOON_SPS.

    Requires an authoritative vector dataset; missing data raises an explicit error.
    """
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"PSR dataset not found: {path}. Install an authoritative "
                                "NASA/USGS/PDS PSR boundary dataset at this path.")
    frame = gpd.read_file(path)
    if frame.empty:
        raise ValueError("PSR dataset contains no features")
    if frame.crs is None:
        raise ValueError("PSR dataset CRS is undefined")
    point = gpd.GeoSeries([Point(longitude_deg, latitude_deg)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
    projected = frame.to_crs(MOON_SPS)
    boundary_distances = projected.geometry.boundary.distance(point)
    index = boundary_distances.idxmin()
    distance_m = float(boundary_distances.loc[index])
    identifier = projected.loc[index, id_column] if id_column and id_column in projected else None
    return {"distance_m": distance_m, "distance_km": distance_m / 1000.0,
            "nearest_psr_id": None if identifier is None else str(identifier),
            "source_dataset": str(path), "analysis_crs": MOON_SPS.to_string()}
