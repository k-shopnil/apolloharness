"""Terrain-aware hourly tactical sunlight analysis for a mission window."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from .spice_engine import calculate_geometry, load_kernels, unload_kernels
from .terrain import HorizonMask

@dataclass(frozen=True)
class HourlyIllumination:
    utc: str
    sun_elevation_deg: float
    sun_azimuth_deg: float
    terrain_horizon_deg: float
    illuminated: bool


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
            records.append(HourlyIllumination(utc, geo.sun_elevation_deg,
                geo.sun_azimuth_deg, terrain, geo.sun_elevation_deg > terrain))
    finally:
        if manage_kernels:
            unload_kernels()
    lit = [r.illuminated for r in records]
    intervals = []
    begin = None
    longest = 0
    run = 0
    for i, record in enumerate(records):
        if not record.illuminated:
            if begin is None:
                begin = record.utc
            run += 1
        elif begin is not None:
            intervals.append((begin, record.utc)); longest = max(longest, run)
            begin, run = None, 0
    if begin is not None:
        intervals.append((begin, (start + timedelta(hours=count)).strftime("%Y-%m-%dT%H:%M:%SZ")))
        longest = max(longest, run)
    lit_hours = sum(lit)
    return {"analysis_type": "tactical_mission_window", "sunlight_percent": 100 * lit_hours / count,
            "illuminated_hours": lit_hours, "total_hours": count,
            "longest_darkness_hours": longest, "darkness_intervals": intervals,
            "hourly": [asdict(r) for r in records]}
