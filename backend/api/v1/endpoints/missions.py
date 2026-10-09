import copy
import json
from pathlib import Path
from typing import Any, Optional
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
    landing_ellipse: Optional[LandingEllipse] = None
    payload_instruments: list[PayloadInstrument] = Field(default_factory=list)
    payload: list[PayloadInstrument] = Field(default_factory=list)


def _sanitize_mission_entry(item: dict) -> dict:
    """Provide clean defaults and mirror payload <-> payload_instruments."""
    sanitized = copy.deepcopy(item)
    sanitized.setdefault("target", "Moon")
    sanitized.setdefault("description", "")
    sanitized.setdefault("start_date", None)
    sanitized.setdefault("end_date", None)
    
    # Handle landing ellipse default if missing
    if "landing_ellipse" not in sanitized or sanitized["landing_ellipse"] is None:
        sanitized["landing_ellipse"] = {
            "semi_major_km": 5.0,
            "semi_minor_km": 2.5,
            "azimuth_deg": 0.0,
        }

    # Handle payload & payload_instruments normalization
    payload = sanitized.get("payload_instruments") or sanitized.get("payload") or []
    sanitized["payload_instruments"] = payload
    sanitized["payload"] = payload
    return sanitized


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    raw_list = data.get("missions", []) if isinstance(data, dict) else data
    return [_sanitize_mission_entry(m) for m in raw_list]


def load_missions() -> tuple[list[dict], str]:
    primary = settings.data_dir / "missions.json"
    fallback = settings.fixtures_dir / "missions.json"

    if not settings.offline and primary.exists():
        try:
            return _read(primary), "live"
        except (json.JSONDecodeError, OSError):
            pass  # fall through to fixtures

    if fallback.exists():
        return _read(fallback), "mock"

    raise FileNotFoundError("No mission catalog found in data/ or demo_fixtures/")


@router.get("/missions", response_model=list[Mission])
def list_missions(response: Response):
    try:
        missions, mode = load_missions()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Mission catalog unavailable")
    response.headers["X-Data-Mode"] = mode
    return missions
