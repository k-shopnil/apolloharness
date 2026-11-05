"""Independent validation of the physics engine against NASA PGDA product 69.

NASA's long-term average solar illumination map (Mazarico et al. 2011 method,
``AVGVISIB``: mean visible fraction of the solar disc) is computed by NASA
from LOLA topography with its own ray tracer. Our engine computes the same
quantity from a different DEM release (PGDA product 90), NAIF SPICE
ephemerides and our horizon tracer. Agreement is therefore evidence that the
pipeline is physically right; disagreement is reported, not tuned away.

Nothing here is fitted: the "model" is the deterministic physics. Its only
free choices (horizon ray length, near-field resolution) are selected by a
pre-declared protocol that keeps the test set untouched:

1. Area-uniform random points, split into alternating 30-degree longitude
   wedges (dev / test) with a buffer at every wedge boundary, so nearby
   correlated points never straddle the split.
2. Candidate configurations are compared on dev only; the rule is lowest dev
   RMSE among candidates within the interactive latency budget.
3. The selected configuration (and the previous production configuration,
   for a before/after comparison) is evaluated once on test, with
   spatial-block bootstrap 95% CIs, a no-skill baseline, and errors
   stratified by how steeply NASA's own map varies around each point.

    python -m src.ml.validation --points 800 --epochs 2000
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer

from ..compute.regional import BodyTracks, DemArray, body_tracks, site_frames, topocentric
from ..compute.regional import disk_fraction, horizon_lookup
from ..compute.spice_engine import SPICE_LOCK, SUN_RADIUS_KM, load_kernels
from ..compute.terrain import DATA_DIR, MOON_GEOGRAPHIC, PROJECT_ROOT

PRODUCT_85S = DATA_DIR / "illumination" / "AVGVISIB_85S_060M_201608.TIF"
REPORT_PATH = PROJECT_ROOT / "data" / "validation" / "annual_illumination_validation.json"
NODAL_CYCLE_DAYS = 6798.38  # lunar nodal precession period, ~18.61 years
# Named reference points, evaluated separately from the random sample.
REFERENCE_POINTS = {
    "brief_shackleton_reference": (-89.54, 0.0),
}


def sample_points(count: int, seed: int, max_radius_m: float, to_map: Transformer
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Area-uniform random points within ``max_radius_m`` of the pole (map plane)."""
    rng = np.random.default_rng(seed)
    radius = max_radius_m * np.sqrt(rng.uniform(0.0, 1.0, count))
    theta = rng.uniform(0.0, 2 * np.pi, count)
    lon, lat = to_map.transform(radius * np.cos(theta), radius * np.sin(theta), direction="INVERSE")
    return np.asarray(lat), (np.asarray(lon) + 180.0) % 360.0 - 180.0


def stratified_epochs(count: int, seed: int, start_utc: str = "2000-01-01T00:00:00Z",
                      span_days: float = NODAL_CYCLE_DAYS) -> np.ndarray:
    """One jittered epoch per equal stratum across a full nodal cycle."""
    import spiceypy as spice
    rng = np.random.default_rng(seed + 1)
    with SPICE_LOCK:
        load_kernels()
        et0 = spice.str2et(start_utc)
    width = span_days * 86_400.0 / count
    return et0 + (np.arange(count) + rng.uniform(0.0, 1.0, count)) * width


def nasa_illumination(latitudes: np.ndarray, longitudes: np.ndarray,
                      product: Path = PRODUCT_85S) -> np.ndarray:
    """Nearest-pixel product-69 value as a 0-1 fraction (NaN for nodata)."""
    with rasterio.open(product) as ds:
        to_map = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
        x, y = to_map.transform(longitudes, latitudes)
        raw = np.array([v[0] for v in ds.sample(zip(np.asarray(x), np.asarray(y)), masked=True)],
                       dtype=object)
        scale = float(ds.scales[0]) if ds.scales else 1.0
    values = np.array([np.nan if (v is np.ma.masked or v is None) else float(v) for v in raw])
    return values * scale


def physics_illumination(latitudes: np.ndarray, longitudes: np.ndarray, dem: DemArray,
                         tracks: BodyTracks, *, max_distance_m: float,
                         near_field_m: float, radial_step_m: float = 80.0,
                         azimuth_step_deg: float = 1.0,
                         observer_height_m: float = 1.5) -> dict[str, np.ndarray]:
    masks = dem.horizon_masks(latitudes, longitudes, max_distance_m=max_distance_m,
                              radial_step_m=radial_step_m, azimuth_step_deg=azimuth_step_deg,
                              observer_height_m=observer_height_m, near_field_m=near_field_m)
    positions, east, north, up = site_frames(latitudes, longitudes)
    elevation, azimuth, ranges = topocentric(tracks.sun_me_km, positions, east, north, up)
    margin = elevation - horizon_lookup(masks, azimuth_step_deg, azimuth)
    known = np.isfinite(margin).all(axis=1)
    disc = disk_fraction(margin, np.degrees(np.arcsin(SUN_RADIUS_KM / ranges)))
    return {
        "disk_fraction": np.where(known, np.nanmean(disc, axis=1), np.nan),
        "centre_fraction": np.where(known, np.nanmean(margin > 0, axis=1), np.nan),
        "horizon_max_deg": np.nanmax(masks, axis=1),
    }


def _metrics(pred: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    error = pred - truth
    ss_res = float(np.sum(error ** 2))
    ss_tot = float(np.sum((truth - truth.mean()) ** 2))
    return {
        "mae_pct": 100 * float(np.mean(np.abs(error))),
        "rmse_pct": 100 * float(np.sqrt(np.mean(error ** 2))),
        "bias_pct": 100 * float(np.mean(error)),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "pearson_r": float(np.corrcoef(pred, truth)[0, 1]),
        "within_5pct": float(np.mean(np.abs(error) <= 0.05)),
    }


def block_bootstrap(pred: np.ndarray, truth: np.ndarray, blocks: np.ndarray, *,
                    replicates: int, seed: int) -> dict[str, list[float]]:
    """95% CIs by resampling whole spatial blocks (handles spatial correlation)."""
    rng = np.random.default_rng(seed + 2)
    unique = np.unique(blocks)
    members = {b: np.flatnonzero(blocks == b) for b in unique}
    samples: dict[str, list[float]] = {}
    for _ in range(replicates):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        index = np.concatenate([members[b] for b in chosen])
        for key, value in _metrics(pred[index], truth[index]).items():
            samples.setdefault(key, []).append(value)
    return {key: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
            for key, v in samples.items()}


CANDIDATES = {
    # name: (max ray m, near-field m)  -- near == max means single resolution
    "rays_050km_single_res": (50_000.0, 50_000.0),     # previous production default
    "rays_100km_multires": (100_000.0, 20_000.0),
    "rays_150km_multires": (150_000.0, 20_000.0),
    "rays_150km_single_res": (150_000.0, 150_000.0),   # reference, too slow for interactive
}
PREVIOUS_PRODUCTION = "rays_050km_single_res"
LATENCY_BUDGET_S = 0.15  # single-site horizon budget inside the 0.5 s request gate


def wedge_split(latitudes: np.ndarray, longitudes: np.ndarray, x: np.ndarray, y: np.ndarray,
                *, wedge_deg: float = 30.0, buffer_m: float = 5_000.0) -> np.ndarray:
    """Return 'dev' / 'test' / 'buffer' labels from alternating longitude wedges."""
    angle = np.degrees(np.arctan2(y, x)) % 360.0
    wedge = np.floor(angle / wedge_deg).astype(int)
    radius = np.hypot(x, y)
    offset = np.minimum(angle - wedge * wedge_deg, (wedge + 1) * wedge_deg - angle)
    near_boundary = np.radians(offset) * radius < buffer_m
    near_pole = radius < buffer_m * 2
    labels = np.where(wedge % 2 == 0, "dev", "test").astype(object)
    labels[near_boundary | near_pole] = "buffer"
    return labels


def local_truth_range(latitudes: np.ndarray, longitudes: np.ndarray, half_px: int = 3,
                      product: Path = PRODUCT_85S) -> np.ndarray:
    """Max-min of NASA's map in a (2*half_px+1)^2 window: local illumination gradient."""
    out = np.full(len(latitudes), np.nan)
    with rasterio.open(product) as ds:
        to_map = Transformer.from_crs(MOON_GEOGRAPHIC, ds.crs, always_xy=True)
        x, y = to_map.transform(longitudes, latitudes)
        scale = float(ds.scales[0]) if ds.scales else 1.0
        for i, (xi, yi) in enumerate(zip(np.asarray(x), np.asarray(y))):
            r, c = ds.index(xi, yi)
            window = ds.read(1, window=((r - half_px, r + half_px + 1),
                                        (c - half_px, c + half_px + 1)), masked=True)
            if window.count():
                out[i] = float(window.max() - window.min()) * scale
    return out


def _latency(dem: DemArray, max_m: float, near_m: float) -> float:
    from ..compute.terrain import extract_horizon_mask_fast
    extract_horizon_mask_fast(dem.dem_path, -86.0, 45.0, max_distance_m=max_m, near_field_m=near_m)
    started = time.perf_counter()
    for lat, lon in ((-84.79, 29.2), (-87.2, 133.0), (-88.2, -100.0)):
        extract_horizon_mask_fast(dem.dem_path, lat, lon, max_distance_m=max_m, near_field_m=near_m)
    return (time.perf_counter() - started) / 3


def _evaluate(physics: dict[str, np.ndarray], truth: np.ndarray, blocks: np.ndarray, *,
              replicates: int, seed: int) -> dict[str, Any]:
    valid = np.isfinite(physics["disk_fraction"]) & np.isfinite(truth)
    pred = physics["disk_fraction"][valid]
    return {"evaluated_points": int(valid.sum()), "excluded_points": int((~valid).sum()),
            "disk_fraction": _metrics(pred, truth[valid]),
            "centre_fraction": _metrics(physics["centre_fraction"][valid], truth[valid]),
            "disk_fraction_ci95": block_bootstrap(pred, truth[valid], blocks[valid],
                                                  replicates=replicates, seed=seed)}


def run_validation(*, points: int = 800, epochs: int = 2000, seed: int = 20261031,
                   block_m: float = 15_000.0, replicates: int = 1000,
                   product: Path = PRODUCT_85S) -> dict[str, Any]:
    started = time.perf_counter()
    dem = DemArray()
    with rasterio.open(product) as ds:
        product_radius = 0.98 * min(abs(ds.bounds.left), abs(ds.bounds.right))
    lat, lon = sample_points(points, seed, product_radius, dem.to_map)
    x, y = (np.asarray(v) for v in dem.to_map.transform(lon, lat))
    split = wedge_split(lat, lon, x, y)
    truth = nasa_illumination(lat, lon, product)
    tracks = body_tracks(stratified_epochs(epochs, seed))
    blocks = (np.floor(x / block_m).astype(int) * 100_000 + np.floor(y / block_m).astype(int))

    def physics_for(mask: np.ndarray, name: str) -> dict[str, np.ndarray]:
        max_m, near_m = CANDIDATES[name]
        return physics_illumination(lat[mask], lon[mask], dem, tracks, max_distance_m=max_m,
                                    near_field_m=near_m)

    dev, test = split == "dev", split == "test"
    # --- Step 2: model selection on dev only ---------------------------------
    selection: dict[str, Any] = {}
    for name, (max_m, near_m) in CANDIDATES.items():
        result = _evaluate(physics_for(dev, name), truth[dev], blocks[dev],
                           replicates=200, seed=seed)
        result["single_site_latency_s"] = round(_latency(dem, max_m, near_m), 3)
        result["within_latency_budget"] = result["single_site_latency_s"] <= LATENCY_BUDGET_S
        selection[name] = result
    eligible = {k: v for k, v in selection.items() if v["within_latency_budget"]}
    selected = min(eligible, key=lambda k: eligible[k]["disk_fraction"]["rmse_pct"])

    # --- Step 3: one-shot test evaluation -----------------------------------
    test_results: dict[str, Any] = {}
    selected_physics: dict[str, np.ndarray] = {}
    for name in dict.fromkeys((selected, PREVIOUS_PRODUCTION)):
        physics = physics_for(test, name)
        test_results[name] = _evaluate(physics, truth[test], blocks[test],
                                       replicates=replicates, seed=seed)
        if name == selected:
            selected_physics = physics
    valid = np.isfinite(selected_physics["disk_fraction"]) & np.isfinite(truth[test])
    t_lat, t_lon, t_truth = lat[test][valid], lon[test][valid], truth[test][valid]
    pred = selected_physics["disk_fraction"][valid]
    baseline = _metrics(np.full(len(t_truth), truth[dev][np.isfinite(truth[dev])].mean()), t_truth)
    gradient = local_truth_range(t_lat, t_lon, product=product)
    edges = np.nanpercentile(gradient, [0, 50, 90, 100])
    strata = {}
    for label, lo, hi in (("smooth_lower_50pct", edges[0], edges[1]),
                          ("moderate_50_90pct", edges[1], edges[2]),
                          ("steep_top_10pct", edges[2], edges[3])):
        # Half-open bins (closed on the last) so every point is counted once.
        member = (gradient >= lo) & ((gradient < hi) if hi < edges[-1] else (gradient <= hi))
        strata[label] = {"points": int(member.sum()),
                         "nasa_local_range_pct": [100 * float(lo), 100 * float(hi)],
                         **_metrics(pred[member], t_truth[member])}
    residual = pred - t_truth
    residual_analysis = {
        "corr_with_elevation": float(np.corrcoef(residual, dem.elevation(t_lat, t_lon))[0, 1]),
        "corr_with_horizon_max": float(np.corrcoef(residual, selected_physics["horizon_max_deg"][valid])[0, 1]),
        "corr_with_colatitude": float(np.corrcoef(residual, 90.0 + t_lat)[0, 1]),
        "corr_with_local_nasa_gradient": float(np.corrcoef(np.abs(residual), gradient)[0, 1]),
        "abs_error_p50_pct": 100 * float(np.percentile(np.abs(residual), 50)),
        "abs_error_p90_pct": 100 * float(np.percentile(np.abs(residual), 90)),
        "abs_error_max_pct": 100 * float(np.max(np.abs(residual))),
    }
    names = list(REFERENCE_POINTS)
    ref_lat = np.array([REFERENCE_POINTS[n][0] for n in names])
    ref_lon = np.array([REFERENCE_POINTS[n][1] for n in names])
    ref_truth = nasa_illumination(ref_lat, ref_lon)
    max_m, near_m = CANDIDATES[selected]
    ref_physics = physics_illumination(ref_lat, ref_lon, dem, tracks, max_distance_m=max_m,
                                       near_field_m=near_m)
    references = {
        name: {"latitude_deg": float(ref_lat[i]), "longitude_deg": float(ref_lon[i]),
               "nasa_product69_pct": 100 * float(ref_truth[i]),
               "physics_disk_pct": 100 * float(ref_physics["disk_fraction"][i]),
               "physics_centre_pct": 100 * float(ref_physics["centre_fraction"][i])}
        for i, name in enumerate(names)
    }
    return {
        "schema": "apolloharness.validation.annual_illumination.v2",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "truth": {"product": Path(product).name, "quantity": "mean visible solar-disc fraction",
                  "sampling": "nearest pixel (60 m)", "source_dem_epoch": "LOLA 2009-2013"},
        "physics": {"dem": "LDEM_80S_80MPP_ADJ (PGDA product 90, 80 m)",
                    "ephemeris": "NAIF DE430 + moon_pa_de421, geometric",
                    "epochs": epochs, "epoch_span_days": NODAL_CYCLE_DAYS,
                    "epoch_sampling": "stratified-jittered over one nodal cycle from 2000-01-01",
                    "max_epoch_standard_error_pct": 100 * float(np.sqrt(0.25 / epochs)),
                    "observer_height_m": 1.5, "azimuth_step_deg": 1.0, "radial_step_m": 80.0},
        "protocol": {"points": points, "seed": seed, "split": "alternating 30-deg wedges, 5 km buffer",
                     "dev_points": int(dev.sum()), "test_points": int(test.sum()),
                     "buffer_points": int((split == "buffer").sum()),
                     "selection_rule": f"lowest dev RMSE with single-site latency <= {LATENCY_BUDGET_S} s",
                     "spatial_block_m": block_m, "bootstrap_replicates": replicates},
        "candidates": {k: {"max_distance_m": v[0], "near_field_m": v[1]} for k, v in CANDIDATES.items()},
        "dev_selection": selection,
        "selected": selected,
        "previous_production": PREVIOUS_PRODUCTION,
        "test": test_results,
        "test_no_skill_baseline": baseline,
        "test_error_by_local_gradient": strata,
        "test_residual_analysis": residual_analysis,
        "reference_points": references,
        "runtime_s": round(time.perf_counter() - started, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--points", type=int, default=800)
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--product", type=Path, default=PRODUCT_85S,
                        help="truth raster (mean solar-disc fraction), e.g. a new PGDA release")
    args = parser.parse_args(argv)
    report = run_validation(points=args.points, epochs=args.epochs, seed=args.seed,
                            product=args.product)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("selected", "test", "test_no_skill_baseline",
                                             "test_error_by_local_gradient", "reference_points",
                                             "runtime_s")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
