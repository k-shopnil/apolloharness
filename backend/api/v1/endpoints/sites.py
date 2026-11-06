"""Site evaluation and scoring endpoint with solar, comms, and ice proximity models.

Re-exports models and routers from scores.py, comms.py, and geometry.py for backward compatibility.
"""
from fastapi import APIRouter
from backend.api.v1.endpoints.scores import (
    router as scores_router,
    compute_site_score,
    cached_site_score,
    get_site_score,
    TacticalSunlight,
    StrategicSunlight,
    ViabilityScores,
    SiteScoreResponse,
    _SCORE_CACHE,
    _SCORE_CACHE_LOCK,
)
from backend.api.v1.endpoints.comms import (
    router as comms_router,
    compute_site_comms,
    cached_site_comms,
    get_site_comms,
)
from backend.api.v1.endpoints.geometry import (
    router as geometry_router,
    compute_site_geometry,
    cached_site_geometry,
    get_site_geometry,
    EarthGeometry,
    SunGeometry,
    PsrProximity,
    IlluminationStatus,
    DteCommsStatus,
    SiteGeometryResponse,
    _GEOMETRY_CACHE,
    _GEOMETRY_CACHE_LOCK,
)

router = APIRouter()
router.include_router(scores_router)
router.include_router(comms_router)
router.include_router(geometry_router)

__all__ = [
    "router",
    "compute_site_score",
    "cached_site_score",
    "get_site_score",
    "compute_site_comms",
    "cached_site_comms",
    "get_site_comms",
    "compute_site_geometry",
    "cached_site_geometry",
    "get_site_geometry",
    "TacticalSunlight",
    "StrategicSunlight",
    "ViabilityScores",
    "SiteScoreResponse",
    "EarthGeometry",
    "SunGeometry",
    "PsrProximity",
    "IlluminationStatus",
    "DteCommsStatus",
    "SiteGeometryResponse",
    "_SCORE_CACHE",
    "_SCORE_CACHE_LOCK",
    "_GEOMETRY_CACHE",
    "_GEOMETRY_CACHE_LOCK",
]


from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, Query

@router.get("/sites/custom")
def custom_site(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    utc: Optional[str] = Query(None),
    include_psr: bool = Query(False),
    include_track: bool = Query(False),
):
    utc = utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        from src.compute.site_evaluation import evaluate_custom_site
        return evaluate_custom_site(lat, lon, utc, include_psr=include_psr, include_track=include_track)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@router.get("/sites/compare-dates")
def compare_dates(
    site_id: str = Query(...),
    date_a: str = Query(...),
    date_b: str = Query(...),
    duration_days: float = Query(14.0, ge=1.0, le=60.0),
):
    from backend.api.v1.endpoints.missions import load_missions
    missions, _ = load_missions()
    match = next((m for m in missions if m["id"] == site_id), None)
    if not match:
        raise HTTPException(404, f"unknown site_id: {site_id}")
    lat = match.get("lat")
    lon = match.get("lon")
    if lat is None or lon is None:
        raise HTTPException(404, f"{site_id} has no published landing coordinate")
    try:
        from src.compute.site_evaluation import compare_launch_dates
        return compare_launch_dates(lat, lon, date_a, date_b, duration_days=duration_days)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

from cachetools import TTLCache

_SENSITIVITY_CACHE = TTLCache(maxsize=256, ttl=24 * 3600)
_ARTEMIS_REGIONS_CACHE = None

@router.get("/sites/sensitivity")
def sensitivity(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    utc: Optional[str] = Query(None),
):
    utc_str = utc.strip() if utc else "2026-11-15T12:00:00Z"
    cache_key = (round(lat, 4), round(lon, 4), utc_str)
    if cache_key in _SENSITIVITY_CACHE:
        return _SENSITIVITY_CACHE[cache_key]
    try:
        from src.compute.api_payloads import site_sensitivity
        res = site_sensitivity(lat, lon, utc_str)
        _SENSITIVITY_CACHE[cache_key] = res
        return res
    except ValueError as exc:
        raise HTTPException(422, str(exc))

@router.get("/artemis-regions")
def get_artemis_regions():
    global _ARTEMIS_REGIONS_CACHE
    if _ARTEMIS_REGIONS_CACHE is None:
        from src.compute.api_payloads import artemis_regions
        _ARTEMIS_REGIONS_CACHE = artemis_regions()
    return _ARTEMIS_REGIONS_CACHE
