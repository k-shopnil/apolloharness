"""Site celestial geometry endpoint delegating to src.compute.api_payloads."""
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Optional
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Query, Response
from backend.core.config import settings
from backend.core.engine_gate import ENGINE_GATE

router = APIRouter()

_GEOMETRY_CACHE: TTLCache = TTLCache(maxsize=1024, ttl=24 * 3600)
_GEOMETRY_CACHE_LOCK = RLock()

def _resolve_utc(utc: Optional[str], start_date: Optional[str]) -> str:
    if utc:
        return utc
    if start_date:
        return f"{start_date}T12:00:00Z"
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cached_site_geometry(lat: float, lon: float, utc: str) -> tuple[dict[str, Any], bool]:
    key = (round(lat, 5), round(lon, 5), utc)
    with _GEOMETRY_CACHE_LOCK:
        cached = _GEOMETRY_CACHE.get(key)
    if cached is not None:
        return deepcopy(cached), True

    from src.compute.api_payloads import site_geometry
    with ENGINE_GATE:
        payload = site_geometry(lat, lon, utc)

    with _GEOMETRY_CACHE_LOCK:
        _GEOMETRY_CACHE[key] = deepcopy(payload)
    return payload, False


@router.get("/sites/geometry")
def get_site_geometry(
    response: Response,
    site_id: Optional[str] = Query(None, description="Catalog mission site ID (e.g. clps-prime-1-im2)"),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Latitude in degrees (-90 to +90)"),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Longitude in degrees (-180 to +180)"),
    utc: Optional[str] = Query(None, description="ISO 8601 UTC timestamp"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
):
    mode = "offline" if settings.offline else "live"

    if site_id:
        lookup_id = site_id  # canonical IDs from data/missions.json only; no aliases
        if utc and (lat is None or lon is None):
            from src.compute.api_payloads import catalog_records
            rec = next((r for r in catalog_records() if r["id"] == lookup_id), None)
            if rec is None:
                raise HTTPException(status_code=404, detail=f"unknown site_id: {lookup_id}")
            lat = rec.get("lat")
            lon = rec.get("lon")
            if lat is None or lon is None:
                raise HTTPException(status_code=404, detail=f"{lookup_id} has no published landing coordinate")
        elif not utc:
            try:
                from src.compute.api_payloads import mission_geometry
                payload = mission_geometry(lookup_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"geometry engine unavailable: {exc}")
            response.headers["X-Data-Mode"] = mode
            response.headers["X-Cache"] = "HIT"
            return payload

    if lat is None or lon is None:
        raise HTTPException(status_code=422, detail="give site_id, or lat and lon")

    utc_str = _resolve_utc(utc, start_date)
    try:
        payload, cache_hit = cached_site_geometry(lat, lon, utc_str)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"geometry engine unavailable: {exc}")

    response.headers["X-Data-Mode"] = mode
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
    return payload
