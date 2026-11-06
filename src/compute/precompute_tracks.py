"""Precompute offline Sun/Earth scrubber tracks and countdowns per mission.

Run from the repository root:

    python -m src.compute.precompute_tracks            # all eligible missions
    python -m src.compute.precompute_tracks --days 14  # shorter windows

Each eligible mission gets ``data/precomputed/tracks/<id>.json`` and the run
writes ``index.json`` listing every mission with its eligibility status. A
mission is skipped (never guessed) when it was terminated, or has no
coordinate or no exact start date. The window starts at ``touchdown_utc`` when recorded, otherwise
at 00:00Z on a full ``target_date``.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from .spice_engine import (
    SYNODIC_MONTH_DAYS, calculate_geometry_track, find_horizon_events, load_kernels,
    unload_kernels,
)
from .terrain import DEFAULT_DEM, PROJECT_ROOT, evaluate_site_terrain

MANIFEST = PROJECT_ROOT / "data" / "missions.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "precomputed" / "tracks"
_FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Missions that will never fly need no surface-operations window.
TERMINAL_STATUSES = {"terminated", "cancelled"}


def mission_window_start(mission: dict[str, Any]) -> str | None:
    if mission.get("touchdown_utc"):
        return str(mission["touchdown_utc"])
    target = mission.get("target_date")
    if isinstance(target, str) and _FULL_DATE.match(target):
        return f"{target}T00:00:00Z"
    return None


def precompute_mission(mission: dict[str, Any], *, duration_days: float,
                       step_minutes: float, dem_path: Path = DEFAULT_DEM) -> dict[str, Any]:
    site = mission["landing_site"]
    lat, lon = site["latitude_deg"], site["longitude_deg"]
    start = mission_window_start(mission)
    terrain = evaluate_site_terrain(lat, lon, dem_path)
    mask = terrain.pop("horizon_mask")
    track = calculate_geometry_track(lat, lon, start, duration_days,
                                     step_minutes=step_minutes, horizon_mask=mask)
    events = find_horizon_events(lat, lon, start, duration_days, horizon_mask=mask)
    from .proximity import DEFAULT_PSR
    from .site_evaluation import _psr
    # Static per site, so offline UIs can show the cold-trap line without the 160 MB product.
    psr = _psr(lat, lon, DEFAULT_PSR)
    psr.pop("analysis_crs", None)
    return {
        "mission_id": mission["id"],
        "mission": mission["mission"],
        "coordinate_type": site["coordinate_type"],
        "window_start_basis": "touchdown_utc" if mission.get("touchdown_utc") else "target_date",
        "terrain": {**terrain, "horizon_mask": None if mask is None else mask.to_dict()},
        "countdowns_at_start": {"sun": events["sun"], "earth": events["earth"]},
        "psr": psr,
        "events": events["events"],
        "track": track,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=float, default=SYNODIC_MONTH_DAYS)
    parser.add_argument("--step-minutes", type=float, default=60.0)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    missions = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    load_kernels()
    try:
        for mission in missions:
            site = mission.get("landing_site") or {}
            start = mission_window_start(mission)
            entry = {"mission_id": mission["id"], "mission": mission["mission"]}
            if mission.get("status") in TERMINAL_STATUSES:
                index.append({**entry, "status": f"skipped_mission_{mission['status']}"})
                continue
            if site.get("latitude_deg") is None or site.get("longitude_deg") is None:
                index.append({**entry, "status": "skipped_no_coordinate"})
                continue
            if start is None:
                index.append({**entry, "status": "skipped_no_exact_date"})
                continue
            began = time.perf_counter()
            result = precompute_mission(mission, duration_days=args.days,
                                        step_minutes=args.step_minutes)
            path = args.output / f"{mission['id']}.json"
            path.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
            index.append({**entry, "status": "complete", "file": path.name,
                          "window_start_utc": result["track"]["start_utc"],
                          "horizon_model": result["track"]["horizon_model"]})
            print(f"{mission['id']}: {result['track']['horizon_model']} "
                  f"({time.perf_counter() - began:.2f}s)")
    finally:
        unload_kernels()
    (args.output / "index.json").write_text(json.dumps({
        "schema": "apolloharness.track_index.v1",
        "duration_days": args.days, "step_minutes": args.step_minutes, "missions": index,
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
