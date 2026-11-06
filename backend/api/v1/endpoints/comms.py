"""Communications analysis endpoint returning Earth visibility, elevation angles, and blackout intervals."""
from datetime import datetime, timezone, timedelta
from copy import deepcopy
import math
from threading import RLock
from typing import Optional
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.core.config import settings
from backend.api.v1.endpoints.scores import cached_site_score, _parse_dates

from src.compute.spice_engine import calculate_hourly_geometry, summarize_communications

router = APIRouter()

# 24-hour in-memory TTL cache for comms analyses
_COMMS_CACHE = TTLCache(maxsize=1024, ttl=24 * 3600)
_COMMS_CACHE_LOCK = RLock()


def _comms_cache_key(lat, lon, start_date, end_date, target, permanently_shadowed):
    return (round(lat, 5), round(lon, 5), start_date, end_date, target, bool(permanently_shadowed))


def cached_site_comms(**kwargs):
    key = _comms_cache_key(**kwargs)
    with _COMMS_CACHE_LOCK:
        if key in _COMMS_CACHE:
            return deepcopy(_COMMS_CACHE[key]), True
    result = compute_site_comms(**kwargs)
    with _COMMS_CACHE_LOCK:
        if key not in _COMMS_CACHE:
            _COMMS_CACHE[key] = deepcopy(result)
        return deepcopy(_COMMS_CACHE[key]), False


def compute_site_comms(
    lat: float,
    lon: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target: str = "Moon",
    permanently_shadowed: bool = False,
) -> dict:
    start_dt, end_dt, duration_days = _parse_dates(start_date, end_date)
    score_res, _ = cached_site_score(
        lat=lat,
        lon=lon,
        start_date=start_date,
        end_date=end_date,
        target=target,
        permanently_shadowed=permanently_shadowed,
        solar_override=None,
    )
    scores = score_res["scores"]
    earth_comms_viability = scores["earth_comms_viability"]
    direct_to_earth_possible = earth_comms_viability > 0.0

    # Build hourly Earth elevation geometry and blackout intervals across requested window
    base_time = start_dt if start_dt else datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    hours_to_evaluate = min(168, int(duration_days * 24))  # up to 7 days of hourly analysis
    base_iso = base_time.strftime("%Y-%m-%dT%H:00:00Z")

    try:
        geo_list = calculate_hourly_geometry(lat, lon, base_iso, hours_to_evaluate)
        comms_sum = summarize_communications(geo_list)
        hourly_angles = [
            {
                "utc": item.utc,
                "earth_elevation_deg": item.earth_elevation_deg,
                "occluded": (not item.earth_visible) or permanently_shadowed,
                "earth_visible": item.earth_visible and not permanently_shadowed,
            }
            for item in geo_list
        ]
        blackout_intervals = [
            {
                "start_utc": b[0],
                "end_utc": b[1],
                "duration_hours": float((datetime.fromisoformat(b[1].replace("Z", "+00:00")) - datetime.fromisoformat(b[0].replace("Z", "+00:00"))).total_seconds() / 3600.0),
            }
            for b in comms_sum.blackout_intervals
        ]
        visible_hours_count = 0 if permanently_shadowed else comms_sum.visible_hours
        longest_blackout_hours = float(hours_to_evaluate if permanently_shadowed else comms_sum.longest_blackout_hours)
    except Exception:
        hourly_angles = []
        blackout_intervals = []
        current_blackout_start = None

        abs_lat = abs(lat)
        is_extreme_polar = abs_lat >= 89.0
        cos_c = math.cos(math.radians(lat)) * math.cos(math.radians(lon))

        if is_extreme_polar:
            base_elev = 1.5  # near horizon libration
            elev_amplitude = 2.0
        elif cos_c <= 0.0 or abs(lon) > 85.0:
            base_elev = -10.0
            elev_amplitude = 0.5
        else:
            base_elev = math.degrees(math.asin(max(-1.0, min(1.0, cos_c))))
            elev_amplitude = 1.2

        visible_hours_count = 0

        for h in range(hours_to_evaluate):
            t = base_time + timedelta(hours=h)
            iso_str = t.strftime("%Y-%m-%dT%H:00:00Z")
            angle_rad = 2 * math.pi * (h / (27.3 * 24.0))
            elev = round(base_elev + elev_amplitude * math.sin(angle_rad), 2)
            occluded = elev <= 0.0 or permanently_shadowed
            earth_visible = not occluded

            if earth_visible:
                visible_hours_count += 1
                if current_blackout_start is not None:
                    duration_hrs = (h - current_blackout_start)
                    blackout_intervals.append({
                        "start_utc": (base_time + timedelta(hours=current_blackout_start)).strftime("%Y-%m-%dT%H:00:00Z"),
                        "end_utc": iso_str,
                        "duration_hours": float(duration_hrs),
                    })
                    current_blackout_start = None
            else:
                if current_blackout_start is None:
                    current_blackout_start = h

            hourly_angles.append({
                "utc": iso_str,
                "earth_elevation_deg": elev,
                "occluded": occluded,
                "earth_visible": earth_visible,
            })

        if current_blackout_start is not None:
            duration_hrs = hours_to_evaluate - current_blackout_start
            blackout_intervals.append({
                "start_utc": (base_time + timedelta(hours=current_blackout_start)).strftime("%Y-%m-%dT%H:00:00Z"),
                "end_utc": (base_time + timedelta(hours=hours_to_evaluate)).strftime("%Y-%m-%dT%H:00:00Z"),
                "duration_hours": float(duration_hrs),
            })
        longest_blackout_hours = (
            max((b["duration_hours"] for b in blackout_intervals), default=0.0)
            if blackout_intervals
            else 0.0
        )

    longest_blackout = max([b["duration_hours"] for b in blackout_intervals], default=0.0)
    uptime_pct = round((visible_hours_count / max(1, hours_to_evaluate)) * 100.0, 1)
    avg_elev = round(sum(a["earth_elevation_deg"] for a in hourly_angles) / max(1, len(hourly_angles)), 2)
    min_elev = round(min(a["earth_elevation_deg"] for a in hourly_angles), 2) if hourly_angles else 0.0
    max_elev = round(max(a["earth_elevation_deg"] for a in hourly_angles), 2) if hourly_angles else 0.0

    return {
        "lat": lat,
        "lon": lon,
        "target": target,
        "earth_comms_viability": earth_comms_viability,
        "direct_to_earth_possible": direct_to_earth_possible,
        "start_date": start_date,
        "end_date": end_date,
        "data_mode": "mock" if settings.offline else "live",
        "model_status": "heuristic_demo_estimate",
        "visibility_model": "spherical_horizon_geometric_los",
        "communications_uptime_percent": uptime_pct,
        "avg_elevation_deg": avg_elev,
        "min_elevation_deg": min_elev,
        "max_elevation_deg": max_elev,
        "longest_blackout_hours": longest_blackout,
        "total_hours": hours_to_evaluate,
        "visible_hours": visible_hours_count,
        "blackout_intervals": blackout_intervals,
        "hourly_elevation_angles": hourly_angles,
        "description": "Prototype communications analysis with geometric LOS, libration variation, and blackout intervals.",
    }


@router.get("/sites/comms")
def get_site_comms(
    response: Response,
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in degrees (-90 to +90)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in degrees (-180 to +180)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    target: str = Query("Moon", description="Planetary body (default: Moon)"),
    permanently_shadowed: bool = Query(False, description="Flag for a permanently shadowed region"),
):
    result, cache_hit = cached_site_comms(
        lat=lat,
        lon=lon,
        start_date=start_date,
        end_date=end_date,
        target=target,
        permanently_shadowed=permanently_shadowed,
    )
    response.headers["X-Data-Mode"] = "mock" if settings.offline else "live"
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
    return result
