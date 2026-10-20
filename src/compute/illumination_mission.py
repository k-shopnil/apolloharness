"""Terrain-aware hourly tactical sunlight analysis for a mission window."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any
from .spice_engine import calculate_geometry, load_kernels, unload_kernels
from .terrain import HorizonMask

@dataclass(frozen=True)
class HourlyIllumination:
    utc: str
    sun_elevation_deg: float
    sun_azimuth_deg: float
    terrain_horizon_deg: float
    illuminated: bool | None


def calculate_tactical_illumination(latitude_deg: float, longitude_deg: float,
        mission_start_utc: str, duration_days: float, horizon_mask: HorizonMask,
        *, manage_kernels: bool = True) -> dict[str, Any]:
    """Calculate hourly illumination; a Sun ray is lit only above terrain horizon."""
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    start = datetime.fromisoformat(mission_start_utc.replace("Z", "+00:00"))
    if start.tzinfo is None:
        raise ValueError("mission_start_utc must include a UTC offset")
    start = start.astimezone(timezone.utc)
    count = int(round(duration_days * 24))
    if manage_kernels:
        load_kernels()
    try:
        records = []
        for hour in range(count):
            utc = (start + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%SZ")
            geo = calculate_geometry(latitude_deg, longitude_deg, utc)
            terrain = horizon_mask.elevation_at(geo.sun_azimuth_deg)
            valid = math.isfinite(terrain)
            records.append(HourlyIllumination(utc, geo.sun_elevation_deg,
                geo.sun_azimuth_deg, terrain, bool(geo.sun_elevation_deg > terrain) if valid else None))
    finally:
        if manage_kernels:
            unload_kernels()
    lit = [r.illuminated for r in records]
    unknown = any(value is None for value in lit)
    intervals = []
    begin = None
    longest = 0
    run = 0
    for i, record in enumerate(records):
        if record.illuminated is False:
            if begin is None:
                begin = record.utc
            run += 1
        elif begin is not None:
            intervals.append((begin, record.utc)); longest = max(longest, run)
            begin, run = None, 0
    if begin is not None:
        intervals.append((begin, (start + timedelta(hours=count)).strftime("%Y-%m-%dT%H:%M:%SZ")))
        longest = max(longest, run)
    lit_hours = sum(value is True for value in lit)
    sunlight_percent = None if unknown else 100 * lit_hours / count
    if unknown:
        longest = None
        intervals = []
    return {
        "analysis_type": "tactical_mission_window",
        "analysis_status": "insufficient_terrain_data" if unknown else "complete",
        "tactical_sunlight_percent": sunlight_percent,
        "sunlight_percent": sunlight_percent,  # retained for compatibility
        "illuminated_hours": None if unknown else lit_hours,
        "total_hours": count,
        "longest_darkness_hours": longest,
        "unavailable_hours": sum(value is None for value in lit),
        "darkness_intervals": intervals,
        "blackout_intervals": intervals,
        "hourly": [asdict(r) for r in records],
    }


# Stable public name for downstream callers. The older name remains supported.
calculate_mission_illumination = calculate_tactical_illumination
