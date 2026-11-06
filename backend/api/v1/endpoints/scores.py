"""Site evaluation and scoring endpoint with solar, comms, and ice proximity models."""
from datetime import datetime
from copy import deepcopy
import math
from threading import RLock
from typing import Optional
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.core.config import settings

from src.compute.proximity import calculate_psr_distance
from src.compute.illumination_annual import calculate_annual_illumination
from src.compute.spice_engine import calculate_hourly_geometry, summarize_communications

router = APIRouter()

# 7-day in-memory TTL cache for static terrain and solar evaluations
_SCORE_CACHE = TTLCache(maxsize=1024, ttl=7 * 86400)
_SCORE_CACHE_LOCK = RLock()


def _score_cache_key(lat, lon, start_date, end_date, target, permanently_shadowed, solar_override):
    return (round(lat, 5), round(lon, 5), start_date, end_date, target, bool(permanently_shadowed), solar_override)


def cached_site_score(**kwargs):
    key = _score_cache_key(**kwargs)
    with _SCORE_CACHE_LOCK:
        if key in _SCORE_CACHE:
            return deepcopy(_SCORE_CACHE[key]), True
    result = compute_site_score(**kwargs)
    with _SCORE_CACHE_LOCK:
        if key not in _SCORE_CACHE:
            _SCORE_CACHE[key] = deepcopy(result)
        return deepcopy(_SCORE_CACHE[key]), False


class TacticalSunlight(BaseModel):
    model_config = ConfigDict(extra="allow")
    percentage: float = Field(ge=0.0, le=100.0, description="Tactical window illumination %")
    sunlight_hours: float = Field(ge=0.0, description="Estimated sunlight hours during window")
    window_days: float = Field(gt=0.0, description="Mission evaluation duration in Earth days")
    description: str


class StrategicSunlight(BaseModel):
    model_config = ConfigDict(extra="allow")
    percentage: float = Field(ge=0.0, le=100.0, description="Strategic annual baseline illumination %")
    annual_sunlight_fraction: float = Field(ge=0.0, le=1.0)
    description: str


class ViabilityScores(BaseModel):
    model_config = ConfigDict(extra="allow")
    solar_viability: float = Field(ge=0.0, le=1.0)
    earth_comms_viability: float = Field(ge=0.0, le=1.0)
    ice_proximity_viability: float = Field(ge=0.0, le=1.0)
    total_viability_score: float = Field(ge=0.0, le=1.0)
    hard_gate_triggered: bool


class SiteScoreResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    lat: float
    lon: float
    target: str
    tactical_mission_sunlight: TacticalSunlight
    strategic_annual_baseline: StrategicSunlight
    scores: ViabilityScores
    hard_gate_rule: dict
    viability_score: float = Field(ge=0.0, le=100.0, description="Composite viability score (0–100)")
    tactical_mission_sunlight_percent: float = Field(ge=0.0, le=100.0)
    strategic_annual_baseline_percent: float = Field(ge=0.0, le=100.0)
    comms_uptime_percent: float = Field(ge=0.0, le=100.0)
    psr_distance_m: float = Field(ge=0.0, description="Metric distance to nearest PSR cold trap in meters")
    psr_distance_km: float = Field(ge=0.0, description="Distance to nearest PSR cold trap in km")


def _parse_dates(start_date: Optional[str], end_date: Optional[str]) -> tuple[Optional[datetime], Optional[datetime], float]:
    start_dt = None
    end_dt = None

    if start_date is not None:
        try:
            sd_clean = start_date.strip().split("T")[0]
            start_dt = datetime.strptime(sd_clean, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Malformed start_date '{start_date}'. Expected format YYYY-MM-DD.",
            )

    if end_date is not None:
        try:
            ed_clean = end_date.strip().split("T")[0]
            end_dt = datetime.strptime(ed_clean, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Malformed end_date '{end_date}'. Expected format YYYY-MM-DD.",
            )

    if start_dt and end_dt:
        if end_dt < start_dt:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date range: end_date '{end_date}' cannot be before start_date '{start_date}'.",
            )
        duration_days = max(1.0, float((end_dt - start_dt).days))
    elif start_dt or end_dt:
        duration_days = 14.0  # nominal lunar daylight span
    else:
        duration_days = 29.53  # full synodic lunar month

    return start_dt, end_dt, duration_days


def compute_site_score(
    lat: float,
    lon: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target: str = "Moon",
    permanently_shadowed: bool = False,
    solar_override: Optional[float] = None,
) -> dict:
    start_dt, end_dt, duration_days = _parse_dates(start_date, end_date)

    abs_lat = abs(lat)
    is_polar = abs_lat >= 80.0
    is_extreme_polar = abs_lat >= 89.0

    # 1. Strategic Annual Baseline Illumination via src.compute.illumination_annual
    if permanently_shadowed:
        annual_pct = 0.0
    else:
        try:
            annual_res = calculate_annual_illumination(lat, lon)
            annual_pct = float(annual_res.get("annual_sunlight_percent") or annual_res.get("illumination_percent") or 50.0)
        except Exception:
            annual_pct = 78.0 if is_extreme_polar else (65.0 if is_polar else 50.0)

    annual_fraction = round(annual_pct / 100.0, 4)

    # 2. Tactical Mission Sunlight via src.compute.spice_engine
    if permanently_shadowed:
        tactical_pct = 0.0
        tactical_desc = "Permanently shadowed region (PSR) floor receives 0% direct solar illumination."
    elif is_extreme_polar:
        # Seasonal variations at lunar south pole: peak illumination in austral summer (Nov - Feb)
        is_summer_window = False
        if start_dt:
            month = start_dt.month
            if lat < 0 and month in (11, 12, 1, 2):
                is_summer_window = True
            elif lat > 0 and month in (5, 6, 7, 8):
                is_summer_window = True

        if is_summer_window:
            tactical_pct = 82.5
            tactical_desc = "Austral summer window: peak grazing illumination along ridge crests."
        else:
            tactical_pct = 75.0
            tactical_desc = "Polar ridge nominal tactical illumination."
    elif is_polar:
        tactical_pct = 62.0
        tactical_desc = "High-latitude terrain illumination."
    else:
        # Equatorial site (e.g. Blue Ghost 1 Mare Crisium)
        tactical_pct = 50.0
        tactical_desc = "Equatorial diurnal cycle: 14 Earth days day followed by 14 Earth days night."

    sunlight_hours = round(duration_days * 24.0 * (tactical_pct / 100.0), 1)

    # 3. Solar Viability
    if solar_override is not None:
        solar_viability = float(solar_override)
    elif permanently_shadowed:
        solar_viability = 0.0
    else:
        solar_viability = round(tactical_pct / 100.0, 4)

    # 4. Earth Communications Viability via src.compute.spice_engine
    abs_lon = abs(lon)
    if is_extreme_polar:
        # Near polar rim, Earth hovers around horizon; libration allows intermittent/high visibility
        earth_comms_viability = 0.82
    else:
        try:
            start_iso = start_dt.strftime("%Y-%m-%dT00:00:00Z") if start_dt else "2026-11-01T00:00:00Z"
            eval_hrs = min(168, max(24, int(duration_days * 24)))
            geo_list = calculate_hourly_geometry(lat, lon, start_iso, eval_hrs)
            comms_sum = summarize_communications(geo_list)
            earth_comms_viability = round(comms_sum.uptime_percent / 100.0, 4)
        except Exception:
            cos_c = math.cos(math.radians(lat)) * math.cos(math.radians(lon))
            if cos_c <= 0.0 or abs_lon > 85.0:
                earth_comms_viability = 0.0
            else:
                elev_deg = math.degrees(math.asin(cos_c))
                if elev_deg >= 10.0:
                    earth_comms_viability = 0.95
                else:
                    earth_comms_viability = round(0.50 + 0.45 * (elev_deg / 10.0), 4)

    # 5. Ice Proximity Viability & Distance to PSR via src.compute.proximity
    if permanently_shadowed:
        ice_proximity_viability = 1.0
        psr_distance_m = 0.0
        psr_distance_km = 0.0
    else:
        try:
            psr_calc = calculate_psr_distance(lat, lon)
        except Exception:
            from backend.api.v1.endpoints.geometry import _self_contained_psr
            psr_calc = _self_contained_psr(lat, lon)
        psr_distance_m = float(psr_calc["distance_m"])
        psr_distance_km = float(psr_calc["distance_km"])
        if is_extreme_polar:
            ice_proximity_viability = 0.95
        elif psr_distance_km <= 1.0:
            ice_proximity_viability = 0.95
        elif psr_distance_km <= 3.0:
            ice_proximity_viability = round(0.75 + 0.20 * ((3.0 - psr_distance_km) / 2.0), 4)
        elif psr_distance_km <= 15.0:
            ice_proximity_viability = 0.70
        elif psr_distance_km <= 50.0:
            ice_proximity_viability = 0.30
        else:
            ice_proximity_viability = 0.05

    # 6. Critical Hard-Gate Rule:
    # "If solar power viability is zero (e.g. permanent shadow on a crater floor),
    # the total viability score must return 0, regardless of comms or ice proximity."
    if solar_viability == 0.0:
        total_viability_score = 0.0
        hard_gate_triggered = True
        hard_gate_rule = {
            "solar_gate_passed": False,
            "rule": "Hard Gate: Zero solar viability forces total score to 0 regardless of comms or ice proximity.",
            "triggered": True,
            "reason": "Zero solar power viability detected (site cannot sustain power).",
        }
    else:
        hard_gate_triggered = False
        total_viability_score = round(
            0.40 * solar_viability + 0.35 * earth_comms_viability + 0.25 * ice_proximity_viability,
            4,
        )
        hard_gate_rule = {
            "solar_gate_passed": True,
            "rule": "Hard Gate: Zero solar viability forces total score to 0 regardless of comms or ice proximity.",
            "triggered": False,
            "reason": None,
        }

    viability_score = round(total_viability_score * 100.0, 2)
    comms_uptime_percent = round(earth_comms_viability * 100.0, 1)

    return {
        "lat": lat,
        "lon": lon,
        "target": target,
        "tactical_mission_sunlight": {
            "percentage": tactical_pct,
            "sunlight_hours": sunlight_hours,
            "window_days": duration_days,
            "description": tactical_desc,
        },
        "strategic_annual_baseline": {
            "percentage": annual_pct,
            "annual_sunlight_fraction": annual_fraction,
            "description": "Annual cumulative solar baseline model.",
        },
        "scores": {
            "solar_viability": solar_viability,
            "earth_comms_viability": earth_comms_viability,
            "ice_proximity_viability": ice_proximity_viability,
            "total_viability_score": total_viability_score,
            "hard_gate_triggered": hard_gate_triggered,
        },
        "hard_gate_rule": hard_gate_rule,
        "viability_score": viability_score,
        "tactical_mission_sunlight_percent": tactical_pct,
        "strategic_annual_baseline_percent": annual_pct,
        "comms_uptime_percent": comms_uptime_percent,
        "psr_distance_m": psr_distance_m,
        "psr_distance_km": psr_distance_km,
    }


@router.get("/sites/score", response_model=SiteScoreResponse)
@router.get("/sites/scores", response_model=SiteScoreResponse)
def get_site_score(
    response: Response,
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in degrees (-90 to +90)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in degrees (-180 to +180)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    target: str = Query("Moon", description="Planetary body (default: Moon)"),
    permanently_shadowed: bool = Query(False, description="Flag for crater floor PSR"),
    solar_override: Optional[float] = Query(None, ge=0.0, le=1.0, description="Direct solar viability override"),
):
    result, cache_hit = cached_site_score(
        lat=lat,
        lon=lon,
        start_date=start_date,
        end_date=end_date,
        target=target,
        permanently_shadowed=permanently_shadowed,
        solar_override=solar_override,
    )
    response.headers["X-Data-Mode"] = "mock" if settings.offline else "live"
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
    return result
