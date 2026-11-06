import copy
import json
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.core.config import settings

router = APIRouter()


class LandingEllipse(BaseModel):
    model_config = ConfigDict(extra="allow")

    semi_major_km: float = Field(gt=0, description="Semi-major axis in km")
    semi_minor_km: float = Field(gt=0, description="Semi-minor axis in km")
    azimuth_deg: float = Field(default=0.0, ge=-360, le=360, description="Orientation angle in degrees")


class PayloadInstrument(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, description="Instrument name")
    type: str = Field(min_length=1, description="Instrument type/discipline")
    description: Optional[str] = Field(default="", description="Instrument summary")


class MissionViability(BaseModel):
    model_config = ConfigDict(extra="allow")
    windowSunlight: float = Field(default=75.0, description="Tactical mission sunlight %")
    annualSunlight: float = Field(default=50.0, description="Strategic annual sunlight %")
    commsLos: float = Field(default=80.0, description="Earth communications line-of-sight %")
    psrKm: float = Field(default=2.5, description="Distance to nearest PSR cold trap in km")


class Mission(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    target: str = Field(default="Moon")
    description: str = Field(default="")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    score: Optional[int] = Field(default=None, description="Composite environmental viability index (0-100)")
    viability: Optional[MissionViability] = None
    landing_ellipse: Optional[LandingEllipse] = None
    payload_instruments: list[PayloadInstrument] = Field(default_factory=list)
    payload: list[PayloadInstrument] = Field(default_factory=list)


def _sanitize_mission_entry(item: dict) -> dict:
    """Provide clean defaults and mirror payload <-> payload_instruments.
    
    Robustly handles both legacy schema (lat, lon, start_date) and data-pipeline
    schema (landing_site.latitude_deg, mission, target_date, payloads).
    """
    sanitized = copy.deepcopy(item)
    sanitized["id"] = str(sanitized.get("id") or "mission")

    # Name mapping
    sanitized["name"] = sanitized.get("name") or sanitized.get("mission") or sanitized.get("id")

    # Geographic coordinates mapping
    landing_site = sanitized.get("landing_site") or {}
    lat_val = sanitized.get("lat")
    if lat_val is None:
        lat_val = landing_site.get("latitude_deg")
    if lat_val is None:
        lat_val = -84.79
    sanitized["lat"] = float(lat_val)

    lon_val = sanitized.get("lon")
    if lon_val is None:
        lon_val = landing_site.get("longitude_deg")
    if lon_val is None:
        lon_val = 29.20
    sanitized["lon"] = float(lon_val)

    # Date normalization
    start_date = sanitized.get("start_date")
    if not start_date:
        target_date = sanitized.get("target_date")
        if target_date:
            target_str = str(target_date).strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", target_str):
                start_date = target_str
            elif re.match(r"^\d{4}$", target_str):
                start_date = f"{target_str}-06-01"
        if not start_date:
            start_date = "2026-06-01"
    sanitized["start_date"] = start_date
    sanitized.setdefault("end_date", None)

    sanitized.setdefault("target", sanitized.get("target_site") or "Moon")
    sanitized.setdefault("description", sanitized.get("region") or "")

    # Landing ellipse normalization (ensure semi_major_km >= semi_minor_km)
    if "landing_ellipse" not in sanitized or sanitized["landing_ellipse"] is None:
        ellipse_km = sanitized.get("landing_ellipse_km") or {}
        major = ellipse_km.get("major_axis_km") or ellipse_km.get("semi_major_km") or 4.0
        minor = ellipse_km.get("minor_axis_km") or ellipse_km.get("semi_minor_km")
        if minor is None:
            minor = min(float(major), 2.5) if major else 2.5
        major_val = float(major if major is not None and major > 0 else 4.0)
        minor_val = float(minor if minor is not None and minor > 0 else 2.5)
        if major_val < minor_val:
            major_val, minor_val = minor_val, major_val
        sanitized["landing_ellipse"] = {
            "semi_major_km": major_val,
            "semi_minor_km": minor_val,
            "azimuth_deg": 0.0,
        }
    else:
        le = sanitized["landing_ellipse"]
        major_val = float(le.get("semi_major_km") or 4.0)
        minor_val = float(le.get("semi_minor_km") or 2.5)
        if major_val < minor_val:
            major_val, minor_val = minor_val, major_val
        le["semi_major_km"] = major_val
        le["semi_minor_km"] = minor_val
        le.setdefault("azimuth_deg", 0.0)

    # Payload & payload_instruments normalization
    instruments = sanitized.get("payload_instruments") or []
    if not instruments:
        payloads = sanitized.get("payloads") or sanitized.get("payload") or []
        for p in payloads:
            if isinstance(p, dict):
                p_name = p.get("name") or "Science Instrument"
                p_type = p.get("type")
                if not p_type:
                    purpose = p.get("purpose")
                    if isinstance(purpose, list) and purpose:
                        p_type = ", ".join(str(x) for x in purpose)
                    elif isinstance(purpose, str):
                        p_type = purpose
                    else:
                        p_type = "Science Payload"
                p_desc = p.get("description") or (f"{p_name} payload" if not p.get("purpose") else f"Purposes: {p_type}")
                instruments.append({"name": p_name, "type": p_type, "description": p_desc})
    if not instruments:
        instruments = [{"name": "Default Sensor", "type": "Science Payload", "description": "Standard lunar sensor suite"}]

    sanitized["payload_instruments"] = instruments
    sanitized["payload"] = instruments

    sanitized.setdefault("score", 75)
    sanitized.setdefault("viability", {
        "windowSunlight": 75.0,
        "annualSunlight": 50.0,
        "commsLos": 80.0,
        "psrKm": 2.5,
    })

    return sanitized


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    raw_list = data.get("missions", []) if isinstance(data, dict) else data
    return [_sanitize_mission_entry(m) for m in raw_list]


_MISSIONS_CACHE: dict[tuple, tuple[list[dict], str]] = {}

def load_missions(force_reload: bool = False) -> tuple[list[dict], str]:
    primary = settings.data_dir / "missions.json"
    fallback = settings.fixtures_dir / "missions.json"

    primary_mtime = primary.stat().st_mtime if primary.exists() else None
    fallback_mtime = fallback.stat().st_mtime if fallback.exists() else None

    cache_key = (
        bool(settings.offline),
        str(settings.data_dir),
        str(settings.fixtures_dir),
        primary_mtime,
        fallback_mtime,
    )

    if not force_reload and cache_key in _MISSIONS_CACHE:
        return _MISSIONS_CACHE[cache_key]

    if not settings.offline and primary.exists():
        try:
            res = (_read(primary), "live")
            _MISSIONS_CACHE[cache_key] = res
            return res
        except (json.JSONDecodeError, OSError):
            pass  # fall through to fixtures

    if fallback.exists():
        res = (_read(fallback), "mock")
        _MISSIONS_CACHE[cache_key] = res
        return res

    raise FileNotFoundError("No mission catalog found in data/ or demo_fixtures/")


@router.get("/missions", response_model=list[Mission])
def list_missions(response: Response):
    try:
        missions, mode = load_missions()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Mission catalog unavailable")
    response.headers["X-Data-Mode"] = mode
    return missions
