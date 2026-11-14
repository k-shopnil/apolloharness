"""Mission manifest and target landing site catalog endpoint.

Serves the canonical 16-record fleet from `src.compute.api_payloads.catalog_records()`,
matching the exact shape of `offline_fixtures/site_geometry/missions.json`.
"""
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.core.config import settings
from src.compute.api_payloads import catalog_records

router = APIRouter()


class PayloadInstrument(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Instrument name")
    type: str = Field(..., description="Instrument discipline/type")
    description: Optional[str] = Field(default="", description="Instrument description")


class Mission(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Canonical mission identifier")
    name: str = Field(..., description="Mission display name")
    category: str = Field(default="clps", description="Mission category: clps, artemis, anchor")
    provider: Optional[str] = Field(default=None, description="Commercial provider or operating agency")
    lander: Optional[str] = Field(default=None, description="Lander model / spacecraft name")
    status: str = Field(default="planned", description="Mission lifecycle status")
    target_site: Optional[str] = Field(default=None, description="Target landing site name")
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude in degrees (-90 to +90)")
    lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude in degrees (-180 to +180)")
    coordinate_type: Optional[str] = Field(default=None, description="Coordinate provenance classification")
    target_feature: Optional[Any] = Field(default=None, description="Target IAU lunar feature")
    start_date: Optional[str] = Field(default=None, description="Target arrival / landing date (YYYY-MM-DD)")
    touchdown_utc: Optional[str] = Field(default=None, description="Actual touchdown UTC if landed")
    landing_ellipse: Optional[dict[str, Any]] = Field(default=None, description="Landing ellipse dimensions in km, or null")
    payload_summary: Optional[str] = Field(default=None, description="Summary of payloads")
    payload_instruments: list[PayloadInstrument] = Field(default_factory=list, description="Detailed manifest")
    has_precomputed_track: bool = Field(default=False, description="Whether precomputed 29.5-day track exists")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="Primary source citations")


def load_missions(force_reload: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Retrieve catalog records and active runtime mode."""
    primary = settings.data_dir / "missions.json"
    fallback = settings.fixtures_dir / "missions.json"
    if not settings.offline and primary.exists():
        try:
            return catalog_records(primary), "live"
        except Exception:
            pass
    if fallback.exists():
        return catalog_records(fallback), "offline"
    raise FileNotFoundError("No mission catalog found in data/ or offline_fixtures/")


@router.get("/missions")
def list_missions(response: Response) -> list[dict[str, Any]]:
    """Retrieve the authoritative catalog of CLPS, Artemis, and anchor lunar missions."""
    try:
        records, mode = load_missions()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Mission catalog unavailable")
    response.headers["X-Data-Mode"] = mode
    return records
