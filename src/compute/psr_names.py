"""Human-readable names for permanently shadowed regions (PSRs).

PSRs have no official names: the IAU names craters, not shadows. NASA's PGDA
PSR product therefore carries only coded identifiers (``HNP_833388_0453121``).
What a planner can say truthfully is *which named crater a PSR lies in*. This
module answers that from the IAU/USGS Gazetteer of Planetary Nomenclature:

* the host is the **smallest** IAU-named crater whose rim circle (centre +
  diameter / 2) holds at least half of the PSR's area
  (``host_crater_for_polygon``), so a PSR in a small crater on Shackleton's
  wall goes to the small crater, while a 242 km² PSR on de Gerlache's floor is
  not credited to the 17 km Brill crater merely because its centre point
  falls inside Brill (a point test alone got that wrong);
* rim circles are an approximation (craters are not perfect circles), so the
  result states its ``relation`` and ``psr_area_fraction_inside_rim`` and never
  claims an official name;
* no containing crater means ``None``: the UI shows the distance only.

The gazetteer subset is committed (``data/psr/iau_south_polar_craters.csv``,
craters south of 70 deg S) so the lookup works offline. Rebuild it with
``python -m src.acquire.usgs_nomenclature``.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .terrain import DATA_DIR, MOON_RADIUS_M

GAZETTEER_SUBSET = DATA_DIR / "psr" / "iau_south_polar_craters.csv"
SOURCE = "IAU/USGS Gazetteer of Planetary Nomenclature (MOON_nomenclature_center_pts)"


@lru_cache(maxsize=2)
def _craters(path: str) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray]:
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    lat = np.radians([float(r["center_lat_deg"]) for r in rows])
    lon = np.radians([float(r["center_lon_deg"]) for r in rows])
    radius = np.array([float(r["diameter_km"]) * 500.0 for r in rows])  # metres
    unit = np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    return rows, unit, radius, np.array([float(r["diameter_km"]) for r in rows])


def host_crater(latitude_deg: float, longitude_deg: float, *,
                gazetteer: str | Path = GAZETTEER_SUBSET) -> dict[str, Any] | None:
    """Smallest IAU-named crater whose rim circle contains the point, or None."""
    path = Path(gazetteer)
    if not path.is_file():
        return None
    rows, unit, radius, diameter = _craters(str(path))
    lat, lon = np.radians(latitude_deg), np.radians(longitude_deg)
    point = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    distance = MOON_RADIUS_M * np.arccos(np.clip(unit @ point, -1.0, 1.0))
    inside = np.flatnonzero(distance <= radius)
    if inside.size == 0:
        return None
    best = int(inside[np.argmin(diameter[inside])])
    row = rows[best]
    return {"name": row["name"], "diameter_km": float(row["diameter_km"]),
            "center_lat_deg": float(row["center_lat_deg"]),
            "center_lon_deg": float(row["center_lon_deg"]),
            "distance_from_center_km": round(float(distance[best]) / 1000.0, 2),
            "relation": "within_rim_circle", "usgs_url": row["usgs_url"], "source": SOURCE}


MAJORITY = 0.5


def host_crater_for_polygon(polygon, crs, *, gazetteer: str | Path = GAZETTEER_SUBSET,
                            min_overlap: float = MAJORITY) -> dict[str, Any] | None:
    """Smallest IAU crater whose rim circle holds >= ``min_overlap`` of the polygon's area.

    ``polygon`` is a shapely geometry in ``crs`` (a projected, metric CRS such as
    the south-polar stereographic MOON_SPS; its scale error is < 0.8 % at 80 S).
    """
    import geopandas as gpd
    from shapely.geometry import Point
    from .terrain import MOON_GEOGRAPHIC
    path = Path(gazetteer)
    if not path.is_file() or polygon.is_empty or polygon.area <= 0:
        return None
    rows, unit, radius, diameter = _craters(str(path))
    anchor = gpd.GeoSeries([polygon.centroid], crs=crs).to_crs(MOON_GEOGRAPHIC).iloc[0]
    lat, lon = np.radians(anchor.y), np.radians(anchor.x)
    centre = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    reach = np.sqrt(polygon.area / np.pi) * 4 + radius  # generous prefilter, metres
    near = np.flatnonzero(MOON_RADIUS_M * np.arccos(np.clip(unit @ centre, -1, 1)) <= reach)
    if near.size == 0:
        return None
    centres = gpd.GeoSeries([Point(float(rows[i]["center_lon_deg"]), float(rows[i]["center_lat_deg"]))
                             for i in near], crs=MOON_GEOGRAPHIC).to_crs(crs)
    best, best_overlap = None, 0.0
    for i, point in zip(near[np.argsort(diameter[near])], centres.iloc[np.argsort(diameter[near])]):
        overlap = polygon.intersection(point.buffer(radius[i], 64)).area / polygon.area
        if overlap >= min_overlap:
            best, best_overlap = int(i), float(overlap)
            break
    if best is None:
        return None
    row = rows[best]
    return {"name": row["name"], "diameter_km": float(row["diameter_km"]),
            "center_lat_deg": float(row["center_lat_deg"]),
            "center_lon_deg": float(row["center_lon_deg"]),
            "psr_area_fraction_inside_rim": round(best_overlap, 3),
            "relation": "majority_within_rim_circle", "usgs_url": row["usgs_url"],
            "source": SOURCE}

