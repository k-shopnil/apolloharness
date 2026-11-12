"""Site evaluation, geometry, sensitivity, and Artemis region endpoints."""
from datetime import datetime, timezone
from typing import Optional
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Query

from backend.api.v1.endpoints.geometry import (
    router as geometry_router,
    cached_site_geometry,
    get_site_geometry,
    _GEOMETRY_CACHE,
    _GEOMETRY_CACHE_LOCK,
)

router = APIRouter()
router.include_router(geometry_router)

__all__ = [
    "router",
    "cached_site_geometry",
    "get_site_geometry",
    "compute_site_score",
    "_GEOMETRY_CACHE",
    "_GEOMETRY_CACHE_LOCK",
]

def compute_site_score(*args, **kwargs):
    """Stub for legacy test suite compatibility (scores endpoint retired per Quality Gate 1)."""
    return {
        "status": "deprecated",
        "composite_score": 0.0,
        "detail": "Viability scores were retired from the product per Quality Gate 1.",
    }

_SENSITIVITY_CACHE = TTLCache(maxsize=256, ttl=24 * 3600)
_ARTEMIS_REGIONS_CACHE = None


@router.get("/sites/custom")
def custom_site(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    utc: Optional[str] = Query(None),
    include_psr: bool = Query(True),
    include_track: bool = Query(False),
):
    utc_str = utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        from src.compute.api_payloads import site_geometry
        return site_geometry(
            lat, lon, utc_str, include_psr=include_psr, include_track=include_track
        )
    except TypeError:
        # Fallback for environments where engine site_geometry does not yet accept include_track
        from src.compute.api_payloads import site_geometry
        return site_geometry(lat, lon, utc_str, include_psr=include_psr)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(503, detail=f"geometry engine unavailable: {exc}")


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
        raise HTTPException(404, detail=f"unknown site_id: {site_id}")
    lat = match.get("lat")
    lon = match.get("lon")
    if lat is None or lon is None:
        raise HTTPException(404, detail=f"{site_id} has no published landing coordinate")
    try:
        from src.compute.site_evaluation import compare_launch_dates
        return compare_launch_dates(lat, lon, date_a, date_b, duration_days=duration_days)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(503, detail=f"compare-dates engine unavailable: {exc}")


@router.get("/sites/sensitivity")
def sensitivity(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    utc: Optional[str] = Query(None, description="ISO 8601 UTC timestamp (defaults to current time)"),
):
    utc_str = utc.strip() if utc else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_key = (round(lat, 4), round(lon, 4), utc_str)
    if cache_key in _SENSITIVITY_CACHE:
        return _SENSITIVITY_CACHE[cache_key]
    try:
        from src.compute.api_payloads import site_sensitivity
        res = site_sensitivity(lat, lon, utc_str)
        _SENSITIVITY_CACHE[cache_key] = res
        return res
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(503, detail=f"sensitivity engine unavailable: {exc}")


@router.get("/artemis-regions")
def get_artemis_regions():
    global _ARTEMIS_REGIONS_CACHE
    if _ARTEMIS_REGIONS_CACHE is None:
        from src.compute.api_payloads import artemis_regions
        _ARTEMIS_REGIONS_CACHE = artemis_regions()
    return _ARTEMIS_REGIONS_CACHE
