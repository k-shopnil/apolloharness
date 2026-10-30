"""One-call site evaluation for custom coordinates and launch-slip comparison.

These are the data-pipeline entry points for the Issue #8 backend routes
(``/sites/custom`` and ``/sites/compare-dates``). Every metric carries the
model it came from; anything not covered by a NASA product is ``None`` with a
status, never a default value.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .illumination_annual import calculate_annual_illumination
from .proximity import DEFAULT_PSR, nearest_psr_within
from .spice_engine import (
    SYNODIC_MONTH_DAYS, _parse_utc, _validate_coordinates, calculate_geometry_track,
    find_horizon_events, load_kernels,
)
from .terrain import DATA_DIR, DEFAULT_DEM, HorizonMask, evaluate_site_terrain

# Finest product first: 85-90S at 60 m, then 75-90S at 120 m (NASA PGDA product 69).
ANNUAL_PRODUCTS = (
    DATA_DIR / "illumination" / "AVGVISIB_85S_060M_201608.TIF",
    DATA_DIR / "illumination" / "AVGVISIB_75S_120M_201608.TIF",
)


def _annual_illumination(latitude_deg: float, longitude_deg: float) -> dict[str, Any]:
    for product in ANNUAL_PRODUCTS:
        if not product.is_file():
            continue
        try:
            result = calculate_annual_illumination(latitude_deg, longitude_deg, product)
        except ValueError:
            continue
        return {"status": "complete", "annual_sunlight_percent": result["annual_sunlight_percent"],
                "source_dataset": product.name}
    return {"status": "outside_product_coverage", "annual_sunlight_percent": None,
            "source_dataset": None}


def _psr(latitude_deg: float, longitude_deg: float, psr_path: Path) -> dict[str, Any]:
    if latitude_deg > -79.0:  # PGDA PSR product covers 80-90S only
        return {"status": "outside_product_coverage", "distance_m": None, "inside_psr": None}
    if not psr_path.is_file():
        return {"status": "product_not_installed", "distance_m": None, "inside_psr": None}
    return nearest_psr_within(latitude_deg, longitude_deg, dataset_path=psr_path)


def evaluate_custom_site(
    latitude_deg: float, longitude_deg: float, utc: str, *,
    duration_days: float = SYNODIC_MONTH_DAYS, include_track: bool = False,
    include_psr: bool = False, dem_path: str | Path = DEFAULT_DEM,
    psr_path: str | Path = DEFAULT_PSR, global_terrain: bool = True,
) -> dict[str, Any]:
    """Evaluate any lunar coordinate at ``utc``: terrain, Sun/Earth, countdowns.

    Typical latency on the bundled products is ~0.3-0.5 s. ``include_psr`` adds
    ~1 s (vector read) and ``include_track`` adds the scrubber columns.
    Caller must have SPICE kernels loaded or this loads them (idempotent).
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    _, normalized = _parse_utc(utc)
    load_kernels()
    terrain = evaluate_site_terrain(latitude_deg, longitude_deg, dem_path,
                                    global_terrain=global_terrain)
    mask: HorizonMask | None = terrain.pop("horizon_mask")
    events = find_horizon_events(latitude_deg, longitude_deg, normalized, duration_days,
                                 horizon_mask=mask)
    result: dict[str, Any] = {
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "utc": normalized,
        "terrain": {**terrain, "horizon_mask": None if mask is None else mask.to_dict()},
        "sun": events["sun"],
        "earth": events["earth"],
        "events": events["events"],
        "horizon_model": events["horizon_model"],
        "annual_illumination": _annual_illumination(latitude_deg, longitude_deg),
        "psr": (_psr(latitude_deg, longitude_deg, Path(psr_path)) if include_psr
                else {"status": "not_requested", "distance_m": None, "inside_psr": None}),
    }
    if include_track:
        result["track"] = calculate_geometry_track(
            latitude_deg, longitude_deg, normalized, duration_days, horizon_mask=mask)
    return result


def compare_launch_dates(
    latitude_deg: float, longitude_deg: float, date_a_utc: str, date_b_utc: str, *,
    duration_days: float = 14.0, step_minutes: float = 60.0,
    dem_path: str | Path = DEFAULT_DEM, global_terrain: bool = True,
) -> dict[str, Any]:
    """Same site, two arrival epochs: synchronized tracks plus a delta summary.

    Tracks share the same relative clock (``hours_from_start``) so Date A and
    Date B curves overlay directly. The terrain mask is computed once.
    """
    _validate_coordinates(latitude_deg, longitude_deg)
    load_kernels()
    terrain = evaluate_site_terrain(latitude_deg, longitude_deg, dem_path,
                                    global_terrain=global_terrain)
    mask: HorizonMask | None = terrain.pop("horizon_mask")
    scenarios: dict[str, Any] = {}
    for label, utc in (("date_a", date_a_utc), ("date_b", date_b_utc)):
        _, normalized = _parse_utc(utc)
        events = find_horizon_events(latitude_deg, longitude_deg, normalized, duration_days,
                                     horizon_mask=mask)
        track = calculate_geometry_track(latitude_deg, longitude_deg, normalized, duration_days,
                                         step_minutes=step_minutes, horizon_mask=mask)
        scenarios[label] = {"start_utc": normalized, "sun": events["sun"],
                            "earth": events["earth"], "events": events["events"],
                            "sunlit_percent": track["sunlit_percent"],
                            "earth_los_percent": track["earth_los_percent"], "track": track}

    def delta(key: str) -> float | None:
        a, b = scenarios["date_a"][key], scenarios["date_b"][key]
        return None if a is None or b is None else round(b - a, 2)

    a_sun, b_sun = scenarios["date_a"]["sun"], scenarios["date_b"]["sun"]
    return {
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "duration_days": duration_days,
        "horizon_model": "spherical_horizon" if mask is None else "lola_terrain_mask",
        "terrain": {**terrain, "horizon_mask": None if mask is None else mask.to_dict()},
        **scenarios,
        "delta_b_minus_a": {
            "sunlit_percent": delta("sunlit_percent"),
            "earth_los_percent": delta("earth_los_percent"),
            "lit_at_arrival_changed": a_sun["is_lit"] != b_sun["is_lit"],
        },
    }
