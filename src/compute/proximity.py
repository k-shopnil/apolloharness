"""Metric proximity to authoritative lunar permanently shadowed region data."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from .terrain import MOON_GEOGRAPHIC, MOON_SPS, PROJECT_ROOT

import threading

DEFAULT_PSR = PROJECT_ROOT / "data" / "psr" / "LPSR_80S_20MPP_ADJ.SHP"
# PGDA's LPSR product stores its stable identifier in ``name`` (e.g.
# "HNP_833388_0453121") and a row number in ``gid``; other datasets vary.
ID_COLUMNS = ("psr_id", "PSR_ID", "name", "NAME", "gid", "id", "ID")


DERIVED_DIR = PROJECT_ROOT / "cache" / "derived"
_INDEX_LOCK = threading.Lock()
INDEX_MIN_BYTES = 20_000_000


def indexed_psr_path(path: str | Path = DEFAULT_PSR) -> Path:
    """A FlatGeobuf copy of the PSR product with a packed R-tree, built once.

    Shapefiles without a spatial index make every bounding-box read scan all
    506,349 records (~0.3 s). The FlatGeobuf copy answers the same read in
    ~0.05 s. It is a derived cache (``cache/derived``, ~5 s to build), rebuilt
    when the source is newer; any failure falls back to the source file.
    """
    source = Path(path)
    target = DERIVED_DIR / f"{source.stem}.fgb"
    try:
        if source.stat().st_size < INDEX_MIN_BYTES:  # small files: a scan is already fast
            return source
        if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
            return target
        with _INDEX_LOCK:
            if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
                return target
            from pyogrio import read_dataframe, write_dataframe
            DERIVED_DIR.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".fgb.partial")
            write_dataframe(read_dataframe(source), partial, driver="FlatGeobuf",
                            layer_options={"SPATIAL_INDEX": "YES"})
            partial.replace(target)
            return target
    except Exception:  # read-only checkout, missing driver: stay correct, just slower
        return source


def _read_bbox(path: Path, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    return gpd.read_file(indexed_psr_path(path), bbox=bbox)


def _id_column(columns) -> str | None:
    return next((name for name in ID_COLUMNS if name in columns), None)


def _describe_psr(projected: gpd.GeoDataFrame, index) -> dict[str, Any]:
    """Identifier, area and IAU host crater of one PSR polygon."""
    from .psr_names import host_crater
    column = _id_column(projected.columns)
    identifier = projected.loc[index, column] if column else None
    area = projected.loc[index, "area_km2"] if "area_km2" in projected.columns else None
    anchor = gpd.GeoSeries([projected.geometry.loc[index].representative_point()],
                           crs=projected.crs).to_crs(MOON_GEOGRAPHIC).iloc[0]
    host = host_crater(anchor.y, anchor.x)
    return {"nearest_psr_id": None if identifier is None else str(identifier),
            "nearest_psr_area_km2": None if area is None else float(area),
            "nearest_psr_host": host,
            "nearest_psr_label": None if host is None else f"PSR in {host['name']} crater"}


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
        id_column = _id_column(projected.columns)
    identifier = projected.loc[index, id_column] if id_column else None
    return {"distance_m": distance_m, "distance_km": distance_m / 1000.0,
            "nearest_psr": None if identifier is None else str(identifier),
            "nearest_psr_id": None if identifier is None else str(identifier),
            "source_dataset": str(path), "analysis_crs": MOON_SPS.to_string()}


# Backwards-compatible function name.
nearest_psr = calculate_psr_distance


_NO_PSR = {"nearest_psr_id": None, "nearest_psr_area_km2": None, "nearest_psr_host": None,
           "nearest_psr_label": None}


def nearest_psr_within(latitude_deg: float, longitude_deg: float,
                       search_radius_m: float = 20_000.0,
                       dataset_path: str | Path = DEFAULT_PSR) -> dict[str, Any]:
    """Interactive PSR proximity using a bounding-box read of the vector dataset.

    Unlike ``calculate_psr_distance`` (distance to the nearest boundary), this
    reports ``distance_m == 0`` and ``inside_psr`` when the site lies inside a
    PSR polygon. With no PSR inside the search box, ``distance_m`` is ``None``
    and ``min_distance_m`` states the guaranteed lower bound.
    """
    if not np.isfinite(latitude_deg) or not -90 <= latitude_deg <= 90:
        raise ValueError("latitude_deg must be finite and between -90 and 90")
    if not np.isfinite(longitude_deg) or not -180 <= longitude_deg <= 180:
        raise ValueError("longitude_deg must be finite and between -180 and 180")
    if not np.isfinite(search_radius_m) or search_radius_m <= 0:
        raise ValueError("search_radius_m must be positive")
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"PSR dataset not found: {path}")
    point = gpd.GeoSeries([Point(longitude_deg, latitude_deg)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
    # The bbox is expressed in the dataset CRS (PGDA PSRs: south-polar stereographic).
    frame = _read_bbox(path, (point.x - search_radius_m, point.y - search_radius_m,
                              point.x + search_radius_m, point.y + search_radius_m))
    base = {"search_radius_m": search_radius_m, "source_dataset": path.name,
            "analysis_crs": MOON_SPS.to_string()}
    if frame.empty:
        return {**base, "status": "no_psr_within_search_radius", "distance_m": None,
                "min_distance_m": search_radius_m, "inside_psr": False, **_NO_PSR}
    projected = frame.to_crs(MOON_SPS)
    distances = projected.geometry.distance(point)
    index = distances.idxmin()
    distance_m = float(distances.loc[index])
    if distance_m > search_radius_m:  # bbox corner hit beyond the circular radius
        return {**base, "status": "no_psr_within_search_radius", "distance_m": None,
                "min_distance_m": search_radius_m, "inside_psr": False, **_NO_PSR}
    return {**base, "status": "complete", "distance_m": distance_m,
            "distance_km": distance_m / 1000.0, "min_distance_m": distance_m,
            "inside_psr": distance_m == 0.0, **_describe_psr(projected, index)}


def psr_distances(latitudes: np.ndarray, longitudes: np.ndarray, *,
                  search_radius_m: float = 20_000.0,
                  dataset_path: str | Path = DEFAULT_PSR) -> np.ndarray:
    """Vectorized distance (m) from many points to the nearest PSR polygon.

    One bounding-box read covers all points; an STRtree answers the queries.
    0 means inside a PSR; NaN means no PSR within ``search_radius_m``
    (a lower bound, not an estimate).
    """
    import shapely
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"PSR dataset not found: {path}")
    points = gpd.GeoSeries(gpd.points_from_xy(longitudes, latitudes),
                           crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS)
    xmin, ymin, xmax, ymax = points.total_bounds
    pad = search_radius_m
    frame = _read_bbox(path, (xmin - pad, ymin - pad, xmax + pad, ymax + pad))
    out = np.full(len(points), np.nan)
    if frame.empty:
        return out
    geometries = frame.to_crs(MOON_SPS).geometry.values
    tree = shapely.STRtree(geometries)
    (point_index, _), distances = tree.query_nearest(points.values, max_distance=search_radius_m,
                                                     return_distance=True, all_matches=False)
    out[point_index] = distances
    return out
