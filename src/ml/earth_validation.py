"""Validate Earth line of sight against NASA PGDA product 69 Earth visibility.

Truth: ``AVGVISIB_85S_060M_201608_EARTH`` — the fraction of hourly timesteps
over 18.6 years in which **any part of Earth's disc** is above the terrain
(NASA's definition, PGDA product 69). We compute exactly that quantity:
``mean(elevation - horizon > -angular_radius)`` over the same stratified
epochs as the solar validation.

Protocol: identical to ``src.ml.validation`` (same 800 area-uniform points,
seed, wedge dev/test split, 15 km block bootstrap, no-skill baseline,
steepness strata). The horizon configuration is the production one selected
on *solar* dev data and frozen; nothing is tuned to Earth data, so the test
result is fully out-of-sample.

    python -m src.ml.earth_validation          # ~1 min
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from ..compute import terrain
from ..compute.regional import DemArray, body_tracks, horizon_lookup, site_frames, topocentric
from ..compute.spice_engine import EARTH_RADIUS_KM
from ..compute.terrain import DATA_DIR, PROJECT_ROOT
from .review_status import review_fields
from .validation import (
    _metrics, block_bootstrap, local_truth_range, nasa_illumination, sample_points,
    stratified_epochs, wedge_split,
)

PRODUCT = DATA_DIR / "illumination" / "AVGVISIB_85S_060M_201608_EARTH.TIF"
REPORT_PATH = PROJECT_ROOT / "data" / "validation" / "earth_visibility_validation.json"


def physics_earth(latitudes: np.ndarray, longitudes: np.ndarray, dem: DemArray, tracks,
                  *, max_distance_m: float = terrain.HORIZON_MAX_DISTANCE_M,
                  near_field_m: float = terrain.NEAR_FIELD_M) -> dict[str, np.ndarray]:
    masks = dem.horizon_masks(latitudes, longitudes, max_distance_m=max_distance_m,
                              near_field_m=near_field_m)
    positions, east, north, up = site_frames(latitudes, longitudes)
    elevation, azimuth, ranges = topocentric(tracks.earth_me_km, positions, east, north, up)
    margin = elevation - horizon_lookup(masks, 1.0, azimuth)
    radius = np.degrees(np.arcsin(EARTH_RADIUS_KM / ranges))
    known = np.isfinite(margin).all(axis=1)
    return {
        "any_part_fraction": np.where(known, np.mean(margin > -radius, axis=1), np.nan),
        "centre_fraction": np.where(known, np.mean(margin > 0, axis=1), np.nan),
    }


def run(*, points: int = 800, epochs: int = 2000, seed: int = 20261031,
        block_m: float = 15_000.0, replicates: int = 1000, product: Path = PRODUCT,
        output: Path = REPORT_PATH) -> dict[str, Any]:
    started = time.perf_counter()
    dem = DemArray()
    with rasterio.open(product) as ds:
        product_radius = 0.98 * min(abs(ds.bounds.left), abs(ds.bounds.right))
    lat, lon = sample_points(points, seed, product_radius, dem.to_map)
    x, y = (np.asarray(v) for v in dem.to_map.transform(lon, lat))
    split = wedge_split(lat, lon, x, y)
    truth = nasa_illumination(lat, lon, product)
    tracks = body_tracks(stratified_epochs(epochs, seed))
    blocks = np.floor(x / block_m).astype(int) * 100_000 + np.floor(y / block_m).astype(int)
    physics = physics_earth(lat, lon, dem, tracks)

    def evaluate(mask: np.ndarray) -> dict[str, Any]:
        valid = mask & np.isfinite(physics["any_part_fraction"]) & np.isfinite(truth)
        pred, ref = physics["any_part_fraction"][valid], truth[valid]
        return {"n": int(valid.sum()), "any_part": _metrics(pred, ref),
                "centre_only": _metrics(physics["centre_fraction"][valid], ref),
                "any_part_ci95": block_bootstrap(pred, ref, blocks[valid],
                                                 replicates=replicates, seed=seed),
                "within_5pp_pct": float(100 * np.mean(np.abs(pred - ref) <= 0.05))}

    dev, test = split == "dev", split == "test"
    result_test = evaluate(test)
    valid = test & np.isfinite(physics["any_part_fraction"]) & np.isfinite(truth)
    dev_valid = dev & np.isfinite(truth)
    baseline = _metrics(np.full(int(valid.sum()), truth[dev_valid].mean()), truth[valid])
    gradient = local_truth_range(lat[valid], lon[valid])
    pred, ref = physics["any_part_fraction"][valid], truth[valid]
    edges = np.percentile(gradient, [50, 90])
    strata = {}
    for label, member in (("smooth_lower_50pct", gradient < edges[0]),
                          ("moderate_50_90pct", (gradient >= edges[0]) & (gradient < edges[1])),
                          ("steep_top_10pct", gradient >= edges[1])):
        strata[label] = {"n": int(member.sum()), **_metrics(pred[member], ref[member])}
    report = {
        "schema": "apolloharness.earth_visibility_validation.v1",
        "source": {
            "authority": "NASA GSFC Planetary Geology, Geophysics, and Geochemistry "
                         "Analysis Tool (PGDA), product 69",
            "url": "https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF",
            "reference_data": "Committed truth raster named by truth.product.",
        },
        "truth": {"product": Path(product).name, "publisher": "NASA GSFC PGDA product 69",
                  "quantity": "fraction of time any part of Earth's disc is above the terrain"},
        "engine": {"horizon_max_distance_m": terrain.HORIZON_MAX_DISTANCE_M,
                   "near_field_m": terrain.NEAR_FIELD_M,
                   "configuration": "production, selected on solar dev data and frozen"},
        "protocol": {"points": points, "epochs": epochs, "seed": seed,
                     "split": "alternating 30 deg wedges, 5 km buffer (same as solar)",
                     "bootstrap": f"{replicates} replicates, {block_m / 1000:.0f} km blocks"},
        "dev": evaluate(dev), "test": result_test, "test_no_skill_baseline": baseline,
        "test_strata_by_local_truth_range": strata,
        "runtime_s": round(time.perf_counter() - started, 1),
        "automated_comparison": {
            "status": "computed",
            "purpose": "Numerical comparison to the cited NASA raster; not scientific approval.",
            **review_fields("earth_visibility_validation"),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--points", type=int, default=800)
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--product", type=Path, default=PRODUCT,
                        help="truth raster (Earth visibility fraction), e.g. a new PGDA release")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    report = run(points=args.points, epochs=args.epochs, product=args.product, output=args.output)
    test = report["test"]
    print(json.dumps({"test_n": test["n"], "any_part": test["any_part"],
                      "ci95": test["any_part_ci95"], "within_5pp_pct": test["within_5pp_pct"],
                      "centre_only": test["centre_only"],
                      "baseline_mae_pct": report["test_no_skill_baseline"]["mae_pct"],
                      "strata": report["test_strata_by_local_truth_range"],
                      "runtime_s": report["runtime_s"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
