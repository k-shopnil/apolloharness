"""Site evaluation and scoring endpoint with solar, comms, and ice proximity models."""
from datetime import datetime, timezone
import math
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.core.config import settings

router = APIRouter()


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


def _parse_dates(start_date: Optional[str], end_date: Optional[str]) -> tuple[Optional[datetime], Optional[datetime], float]:
    start_dt = None
    end_dt = None

    if start_date is not None:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Malformed start_date '{start_date}'. Expected format YYYY-MM-DD.",
            )

    if end_date is not None:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
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

    # 1. Strategic Annual Baseline Illumination
    if permanently_shadowed:
        annual_pct = 0.0
    elif is_extreme_polar:
        # High peaks of eternal / persistent light near south pole (e.g. Shackleton rim)
        annual_pct = 78.0
    elif is_polar:
        annual_pct = 65.0
    else:
        # Equatorial and mid-latitude lunar surface receives ~50% illumination annually
        annual_pct = 50.0

    annual_fraction = round(annual_pct / 100.0, 4)

    # 2. Tactical Mission Sunlight
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

    # 4. Earth Communications Viability (Direct Line-of-Sight)
    abs_lon = abs(lon)
    if is_extreme_polar:
        # Near polar rim, Earth hovers around horizon; libration allows intermittent/high visibility
        earth_comms_viability = 0.82
    else:
        # Near-side vs far-side based on angular distance from sub-Earth point (0, 0)
        cos_c = math.cos(math.radians(lat)) * math.cos(math.radians(lon))
        if cos_c <= 0.0 or abs_lon > 85.0:
            # Lunar limb / far-side has no direct line-of-sight to Earth without relay
            earth_comms_viability = 0.0
        else:
            # Elevation angle above horizon in degrees = arcsin(cos_c)
            elev_deg = math.degrees(math.asin(cos_c))
            if elev_deg >= 10.0:
                earth_comms_viability = 0.95
            else:
                earth_comms_viability = round(0.50 + 0.45 * (elev_deg / 10.0), 4)

    # 5. Ice Proximity Viability
    if permanently_shadowed:
        ice_proximity_viability = 1.0
    elif is_extreme_polar:
        # Ridge crest adjacent to deep cold traps
        ice_proximity_viability = 0.95
    elif is_polar:
        ice_proximity_viability = 0.70
    elif abs_lat >= 60.0:
        ice_proximity_viability = 0.30
    else:
        # Equatorial / Mare Crisium thermal extremes vaporize surface volatiles
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
    }


@router.get("/sites/score", response_model=SiteScoreResponse)
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
    result = compute_site_score(
        lat=lat,
        lon=lon,
        start_date=start_date,
        end_date=end_date,
        target=target,
        permanently_shadowed=permanently_shadowed,
        solar_override=solar_override,
    )
    response.headers["X-Data-Mode"] = "mock" if settings.offline else "live"
    return result
