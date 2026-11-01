"""Transparent landing-site recommendation from a regional physics screen.

Decision science, not a learned model: candidates come from
``compute.regional.screen_region`` (exact physics), hard safety constraints
are applied first, then candidates are ordered by Pareto rank over the
objectives the planner chooses. No weights are invented: with no ``weights``
argument the order is (Pareto front, NSGA-II crowding distance, gentler
slope), which is parameter-free and spreads recommendations across the
trade-off; remaining ties prefer the safer slope. Planner
supplied weights are applied on direction-aware min-max normalised values
and reported as such.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

# Direction of preference for every objective the screen can provide.
OBJECTIVE_DIRECTIONS: dict[str, str] = {
    "sunlit_percent": "max",
    "mean_sun_disk_percent": "max",
    "earth_los_percent": "max",
    "longest_darkness_hours": "min",
    "longest_earth_blackout_hours": "min",
    "psr_distance_m": "min",       # science access to cold traps
    "slope_deg": "min",
}
DEFAULT_OBJECTIVES = ("mean_sun_disk_percent", "earth_los_percent", "longest_darkness_hours")
# Issue #8 lander slope envelope; slopes are over the DEM's 80 m baseline.
SLOPE_CLASSES = ((8.0, "nominal"), (12.0, "caution"), (float("inf"), "critical"))


def slope_class(slope_deg: float) -> str:
    return next(label for limit, label in SLOPE_CLASSES if slope_deg < limit)


def pareto_ranks(values: np.ndarray) -> np.ndarray:
    """Non-dominated sorting rank (0 = Pareto front) for a maximisation matrix (N, M)."""
    count = len(values)
    # dominates[i, j]: i is >= j in every objective and > in at least one.
    ge = (values[:, None, :] >= values[None, :, :]).all(axis=2)
    gt = (values[:, None, :] > values[None, :, :]).any(axis=2)
    dominates = ge & gt
    dominated_by = dominates.sum(axis=0)
    ranks = np.full(count, -1)
    current = np.flatnonzero(dominated_by == 0)
    rank = 0
    remaining = dominated_by.copy()
    while current.size:
        ranks[current] = rank
        remaining[current] = -1
        remaining -= dominates[current].sum(axis=0)
        current = np.flatnonzero(remaining == 0)
        rank += 1
    return ranks


def crowding_distance(values: np.ndarray) -> np.ndarray:
    """NSGA-II crowding distance within one front (boundary points = inf)."""
    count, objectives = values.shape
    distance = np.zeros(count)
    if count <= 2:
        return np.full(count, np.inf)
    for m in range(objectives):
        order = np.argsort(values[:, m])
        span = values[order[-1], m] - values[order[0], m]
        distance[order[0]] = distance[order[-1]] = np.inf
        if span > 0:
            distance[order[1:-1]] += (values[order[2:], m] - values[order[:-2], m]) / span
    return distance


def recommend_sites(screen: Mapping[str, Any], *,
                    objectives: Sequence[str] = DEFAULT_OBJECTIVES,
                    max_slope_deg: float = 8.0, top_k: int = 10,
                    weights: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Rank screened candidates; returns the top ``top_k`` with explanations."""
    unknown = [name for name in objectives if name not in OBJECTIVE_DIRECTIONS]
    if unknown or not objectives:
        raise ValueError(f"Unknown or empty objectives: {unknown or objectives}")
    if weights is not None:
        if set(weights) - set(objectives) or any(w < 0 for w in weights.values()) \
                or not sum(weights.values()) > 0:
            raise ValueError("weights must be non-negative, sum > 0, and name chosen objectives")
    columns = screen["columns"]
    count = len(columns["latitude_deg"])

    def column(name: str) -> np.ndarray:
        return np.array([np.nan if v is None else v for v in columns[name]], dtype=float)

    slope = column("slope_deg")
    raw = np.column_stack([column(name) for name in objectives])
    complete = np.isfinite(raw).all(axis=1)
    safe = np.isfinite(slope) & (slope < max_slope_deg)
    feasible = complete & safe
    exclusions = {"missing_objective_data": int((~complete).sum()),
                  f"slope_at_or_above_{max_slope_deg:g}_deg": int((complete & ~safe).sum())}
    index = np.flatnonzero(feasible)
    if index.size == 0:
        return {"status": "no_feasible_candidates", "candidates_screened": count,
                "excluded": exclusions, "recommendations": []}
    signs = np.array([1.0 if OBJECTIVE_DIRECTIONS[n] == "max" else -1.0 for n in objectives])
    oriented = raw[index] * signs                         # all objectives maximised
    ranks = pareto_ranks(oriented)
    crowd = np.zeros(len(index))
    for rank in np.unique(ranks):
        members = np.flatnonzero(ranks == rank)
        # Identical objective vectors share one crowding value; otherwise the
        # boundary "inf" would be handed to arbitrary duplicates.
        unique, inverse = np.unique(oriented[members], axis=0, return_inverse=True)
        crowd[members] = crowding_distance(unique)[inverse.ravel()]
    low, high = oriented.min(axis=0), oriented.max(axis=0)
    normalised = np.where(high > low, (oriented - low) / np.where(high > low, high - low, 1), 1.0)
    if weights:
        w = np.array([weights.get(n, 0.0) for n in objectives], dtype=float)
        score = normalised @ (w / w.sum())
        order = np.lexsort((slope[index], -crowd, -score))
        mode = "planner_weighted"
    else:
        score = None
        # Primary: Pareto front; then crowding (diversity); then gentler slope.
        order = np.lexsort((slope[index], -crowd, ranks))
        mode = "pareto_then_crowding"
    best_decile = np.percentile(normalised, 90, axis=0)
    recommendations = []
    for position in order[:top_k]:
        i = index[position]
        strengths = [n for m, n in enumerate(objectives) if normalised[position, m] >= best_decile[m]]
        recommendations.append({
            "latitude_deg": columns["latitude_deg"][i],
            "longitude_deg": columns["longitude_deg"][i],
            "pareto_rank": int(ranks[position]),
            "crowding_distance": None if not np.isfinite(crowd[position]) else round(float(crowd[position]), 4),
            "planner_score": None if score is None else round(float(score[position]), 4),
            "slope_class": slope_class(float(slope[i])),
            "top_decile_in": strengths,
            "metrics": {name: columns[name][i] for name in
                        ("elevation_m", "slope_deg", *OBJECTIVE_DIRECTIONS)
                        if name in columns},
        })
    return {
        "status": "complete",
        "ranking_mode": mode,
        "objectives": {n: OBJECTIVE_DIRECTIONS[n] for n in objectives},
        "weights": dict(weights) if weights else None,
        "constraints": {"max_slope_deg": max_slope_deg,
                        "slope_baseline_m": screen.get("horizon", {}).get("dem_resolution_m")},
        "candidates_screened": count,
        "feasible": int(index.size),
        "pareto_front_size": int((ranks == 0).sum()),
        "excluded": exclusions,
        "recommendations": recommendations,
        "caveats": [
            "Slopes are over the DEM pixel baseline; lander-footprint slopes need a finer DEM.",
            "Rankings compare candidates within this screen only; they are not absolute scores.",
        ],
    }
