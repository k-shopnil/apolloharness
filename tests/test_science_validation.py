"""Scientific validation and ground-truth benchmark assertions.

Collaborators: Ether (@Eetherr77) & Thirtha (@Thirtha17).
Verifies:
1. Physical and mathematical ground-truth benchmarks for lunar exploration sites.
2. Hard-gate rule invariance (zero solar viability forces zero composite viability).
3. Monotonicity, boundary conditions, and regression prevention.
"""
import pytest
from backend.api.v1.endpoints.sites import compute_site_score


# --- Ground Truth Benchmarks ---

def test_benchmark_shackleton_rim_polar_conditions():
    """
    Benchmark: Shackleton Crater Rim (-89.5 deg S, 0.0 deg E).
    Physical characteristics:
    - Austral summer tactical mission window (Nov to Feb) receives peak grazing sunlight (>80%).
    - High ridge topography provides near-persistent strategic annual illumination (>70%).
    - Proximity to cold traps within the crater floor yields high ice volatile potential (>0.90).
    - Periodic Earth visibility through lunar libration (>0.75).
    """
    res = compute_site_score(
        lat=-89.5,
        lon=0.0,
        start_date="2026-11-01",
        end_date="2027-02-15",
    )

    tactical = res["tactical_mission_sunlight"]
    strategic = res["strategic_annual_baseline"]
    scores = res["scores"]

    # Illumination benchmarks
    assert tactical["percentage"] >= 80.0, f"Expected peak summer sunlight >= 80%, got {tactical['percentage']}"
    assert strategic["percentage"] >= 75.0, f"Expected annual strategic baseline >= 75%, got {strategic['percentage']}"

    # Viability sub-scores
    assert scores["solar_viability"] >= 0.80
    assert scores["earth_comms_viability"] >= 0.75
    assert scores["ice_proximity_viability"] >= 0.90

    # Composite score
    assert scores["total_viability_score"] >= 0.80
    assert scores["hard_gate_triggered"] is False
    assert res["hard_gate_rule"]["solar_gate_passed"] is True


def test_benchmark_permanently_shadowed_region_hard_gate():
    """
    Benchmark: PSR Crater Floor (-89.9 deg S, 0.0 deg E).
    Physical characteristics & Hard-Gate Rule:
    - 0% solar illumination and 0.0 solar viability.
    - 1.0 ice proximity viability (cold trap volatile condensation).
    - Hard-gate MUST trigger: total_viability_score == 0.0 regardless of comms or ice.
    """
    res = compute_site_score(
        lat=-89.9,
        lon=0.0,
        permanently_shadowed=True,
    )

    scores = res["scores"]
    rule = res["hard_gate_rule"]

    assert res["tactical_mission_sunlight"]["percentage"] == 0.0
    assert res["strategic_annual_baseline"]["percentage"] == 0.0

    # Solar power viability is strictly zero
    assert scores["solar_viability"] == 0.0
    # Ice potential is maximal in cold trap
    assert scores["ice_proximity_viability"] == 1.0

    # HARD-GATE ASSERTION:
    assert scores["total_viability_score"] == 0.0, (
        "Hard-gate violation: total_viability_score must be 0 when solar_viability is 0"
    )
    assert scores["hard_gate_triggered"] is True
    assert rule["solar_gate_passed"] is False
    assert rule["triggered"] is True
    assert rule["reason"] is not None


def test_benchmark_equatorial_blue_ghost_1_mare_crisium():
    """
    Benchmark: Blue Ghost 1 / Mare Crisium (18.56 deg N, 61.81 deg E).
    Physical characteristics:
    - Standard lunar equatorial diurnal cycle: ~50% tactical and strategic sunlight.
    - Near-side visibility: continuous direct line-of-sight to Earth (>0.90).
    - Thermal environment eliminates surface ice deposits (<0.15).
    """
    res = compute_site_score(
        lat=18.56,
        lon=61.81,
        start_date="2024-11-15",
        end_date="2024-12-05",
    )

    tactical = res["tactical_mission_sunlight"]
    strategic = res["strategic_annual_baseline"]
    scores = res["scores"]

    assert round(tactical["percentage"]) == 50
    assert round(strategic["percentage"]) == 50
    assert scores["earth_comms_viability"] >= 0.90
    assert scores["ice_proximity_viability"] <= 0.15
    assert scores["solar_viability"] == 0.50

    # Non-zero composite score without hard-gate triggering
    assert scores["total_viability_score"] > 0.40
    assert scores["hard_gate_triggered"] is False


def test_benchmark_apollo_11_tranquility_base():
    """
    Benchmark: Apollo 11 Tranquility Base (0.674 deg N, 23.473 deg E).
    Physical characteristics:
    - Equatorial central near side.
    - Earth overhead with high line of sight.
    - Minimal volatile ice viability.
    """
    res = compute_site_score(lat=0.674, lon=23.473)
    scores = res["scores"]

    assert scores["earth_comms_viability"] >= 0.90
    assert scores["ice_proximity_viability"] <= 0.10
    assert scores["solar_viability"] == 0.50
    assert scores["total_viability_score"] > 0.0


# --- Boundary Conditions & Scientific Invariants ---

def test_far_side_comms_blackout():
    """Points on lunar far-side (|lon| > 90 deg) have no direct Earth communications."""
    res = compute_site_score(lat=0.0, lon=180.0)
    assert res["scores"]["earth_comms_viability"] == 0.0


def test_ice_proximity_increases_towards_poles():
    """Thermal modeling invariant: volatile ice stability increases poleward."""
    latitudes = [0.0, 30.0, 60.0, 80.0, 89.5]
    ice_scores = [compute_site_score(lat=l, lon=0.0)["scores"]["ice_proximity_viability"] for l in latitudes]

    for i in range(len(ice_scores) - 1):
        assert ice_scores[i] <= ice_scores[i + 1], f"Ice viability should increase poleward: {ice_scores}"


def test_hard_gate_parameter_sweep():
    """
    Verify mathematical hard gate across solar viability continuum [0.0 to 1.0].
    Total score must be 0 if and only if solar viability is 0.0.
    """
    # Sweep override values
    for s_val in [0.0, 0.05, 0.25, 0.5, 0.75, 1.0]:
        res = compute_site_score(lat=0.0, lon=0.0, solar_override=s_val)
        total = res["scores"]["total_viability_score"]
        triggered = res["scores"]["hard_gate_triggered"]

        if s_val == 0.0:
            assert total == 0.0
            assert triggered is True
            assert res["hard_gate_rule"]["solar_gate_passed"] is False
        else:
            assert total > 0.0
            assert triggered is False
            assert res["hard_gate_rule"]["solar_gate_passed"] is True


def test_calculation_determinism():
    """Ensure identical inputs produce identical scores across successive calculations."""
    res1 = compute_site_score(lat=-89.5, lon=0.0, start_date="2026-11-01", end_date="2027-02-15")
    res2 = compute_site_score(lat=-89.5, lon=0.0, start_date="2026-11-01", end_date="2027-02-15")
    assert res1 == res2
