"""Mission manifest and target landing site catalog endpoint.

Serves the canonical 16-record fleet from `src.compute.api_payloads.catalog_records()`,
matching the exact shape of `offline_fixtures/site_geometry/missions.json`.
"""
from typing import Any
from fastapi import APIRouter, HTTPException, Response

from backend.core.config import settings
from src.compute.api_payloads import catalog_records

router = APIRouter()


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
