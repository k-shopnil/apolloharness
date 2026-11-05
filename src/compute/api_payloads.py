"""Backend bridge: the exact payloads the FastAPI routes in Issue #8 §4.2 serve.

Each function returns JSON-ready data built only from engine output, so a
route handler is a one-liner and the backend needs no knowledge of SPICE,
rasters or the nested catalog schema:

    from src.compute.api_payloads import catalog_records, mission_geometry, site_geometry

    GET /api/v1/missions                    -> catalog_records()
    GET /api/v1/sites/geometry?lat&lon&utc  -> site_geometry(lat, lon, utc)
    GET /api/v1/sites/geometry?site_id=     -> mission_geometry(site_id)

Errors: ``ValueError`` for bad input (map to HTTP 422), ``LookupError`` for an
unknown site or a site without a published coordinate/date (map to 404).
Call ``site_evaluation.warm_up()`` once at startup; scale with worker
processes, not threads (SPICE calls are serialized per process).
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .terrain import DATA_DIR

CATALOG = DATA_DIR / "missions.json"
TRACK_DIR = DATA_DIR / "precomputed" / "tracks"
SCHEMA = "apolloharness.site_geometry.v1"


def _full_date(value: str | None) -> str | None:
    return value if isinstance(value, str) and len(value) == 10 and value[4] == "-" else None


def flatten_mission(record: dict[str, Any]) -> dict[str, Any]:
    """One catalog record in the backend's flat ``Mission`` shape (guide mapping table)."""
    site = record.get("landing_site") or {}
    ellipse = record.get("landing_ellipse_km")
    touchdown = record.get("touchdown_utc")
    return {
        "id": record["id"],
        "name": record["mission"],
        "category": record.get("category"),
        "provider": record.get("provider"),
        "lander": record.get("lander"),
        "status": record.get("status"),
        "target_site": record.get("target_site"),
        "lat": site.get("latitude_deg"),
        "lon": site.get("longitude_deg"),
        "coordinate_type": site.get("coordinate_type"),
        "target_feature": record.get("target_feature"),
        "start_date": touchdown[:10] if touchdown else _full_date(record.get("target_date")),
        "touchdown_utc": touchdown,
        "landing_ellipse": ellipse,  # null = unknown; never default it
        "payload_summary": record.get("payload_summary"),
        "payload_instruments": [{"name": p["name"], "type": ", ".join(p.get("purpose", []))}
                                for p in record.get("payloads", [])],
        "has_precomputed_track": (TRACK_DIR / f"{record['id']}.json").is_file(),
        "sources": record.get("sources", []),
    }


@lru_cache(maxsize=4)
def _catalog(path: str) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(Path(path).read_text(encoding="utf-8")))


def catalog_records(path: str | Path = CATALOG) -> list[dict[str, Any]]:
    """All catalog missions, flattened, with canonical ``data/missions.json`` IDs."""
    return [flatten_mission(r) for r in _catalog(str(path))]


def _clean(value: Any) -> Any:
    """Recursively replace NaN/inf (invalid JSON) with None."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _terrain_summary(terrain: dict[str, Any]) -> dict[str, Any]:
    keys = ("elevation_m", "dem_product", "dem_resolution_m", "horizon_model",
            "horizon_incomplete_azimuths", "horizon_azimuths_filled_from_global", "status")
    return {k: terrain.get(k) for k in keys}


def site_geometry(latitude_deg: float, longitude_deg: float, utc: str, *,
                  include_psr: bool = True, duration_days: float = 29.530589) -> dict[str, Any]:
    """Instantaneous Sun/Earth geometry, countdowns, DTE and PSR context for any point."""
    from .site_evaluation import evaluate_custom_site
    result = evaluate_custom_site(latitude_deg, longitude_deg, utc, duration_days=duration_days,
                                  include_psr=include_psr, include_track=False)
    return _clean({
        "schema": SCHEMA,
        "source": "engine",
        "site": {"latitude_deg": latitude_deg, "longitude_deg": longitude_deg},
        "utc": result["utc"],
        "frame": "MOON_PA; unit vectors point from the site to the body",
        "sun": result["sun"],
        "earth": result["earth"],
        "events": result["events"],
        "psr": result["psr"],
        "horizon_model": result["horizon_model"],
        "terrain": _terrain_summary(result["terrain"]),
    })


def mission_geometry(site_id: str, *, track_dir: str | Path = TRACK_DIR) -> dict[str, Any]:
    """Geometry at the start of a catalog mission's precomputed window (no SPICE call)."""
    if not site_id or "/" in site_id or "\\" in site_id or site_id.startswith("."):
        raise ValueError("invalid site_id")
    path = Path(track_dir) / f"{site_id}.json"
    if not path.is_file():
        known = {r["id"]: r for r in _catalog(str(CATALOG))}
        if site_id not in known:
            raise LookupError(f"unknown site_id: {site_id}")
        raise LookupError(f"{site_id} has no precomputed track (no published coordinate "
                          "or exact date); see data/precomputed/tracks/index.json")
    track = json.loads(path.read_text(encoding="utf-8"))
    columns = track["track"]["columns"]
    countdowns = track["countdowns_at_start"]
    sun, earth = dict(countdowns["sun"]), dict(countdowns["earth"])
    sun.setdefault("unit_vector_moon_pa", columns["sun_unit_moon_pa"][0])
    earth.setdefault("unit_vector_moon_pa", columns["earth_unit_moon_pa"][0])
    return _clean({
        "schema": SCHEMA,
        "source": "precomputed_track",
        "site_id": track["mission_id"],
        "mission": track["mission"],
        "site": {"latitude_deg": track["track"]["latitude_deg"],
                 "longitude_deg": track["track"]["longitude_deg"],
                 "coordinate_type": track["coordinate_type"]},
        "utc": track["track"]["start_utc"],
        "window_start_basis": track["window_start_basis"],
        "frame": "MOON_PA; unit vectors point from the site to the body",
        "sun": sun,
        "earth": earth,
        "events": track["events"],
        "psr": track.get("psr") or {"status": "not_in_track"},
        "horizon_model": track["track"]["horizon_model"],
        "terrain": _terrain_summary(track.get("terrain") or {}),
        "track_summary": {k: track["track"][k] for k in (
            "sunlit_percent", "earth_los_percent", "mean_sun_disk_visible_fraction")},
    })


FIXTURE_DIR = DATA_DIR.parent / "offline_fixtures" / "site_geometry"


def export_fixtures(output: str | Path = FIXTURE_DIR) -> list[str]:
    """Write ``mission_geometry`` for every tracked site, plus the flat catalog.

    The files have exactly the API's shape, so the frontend's offline fallback
    is the same code path as the live API (Issue #8 gate 7).
    """
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for record in catalog_records():
        if record["has_precomputed_track"]:
            payload = mission_geometry(record["id"])
            (out / f"{record['id']}.json").write_text(
                json.dumps(payload, indent=1, allow_nan=False) + "\n", encoding="utf-8")
            written.append(record["id"])
    (out / "missions.json").write_text(
        json.dumps(catalog_records(), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return written


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else FIXTURE_DIR
    ids = export_fixtures(target)
    print(f"{len(ids)} site_geometry fixtures + missions.json -> {target}")
