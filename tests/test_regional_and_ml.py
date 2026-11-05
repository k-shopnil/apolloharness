"""Vectorized physics, validation protocol and recommender contracts."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from src.compute import terrain
from src.compute.spice_engine import (
    _margins, _scan_margins, calculate_geometry_track, load_kernels, unload_kernels,
)
from src.ml import validation
from src.ml.recommend import (
    crowding_distance, pareto_ranks, recommend_sites, slope_class,
)

POLAR_DEM = Path("data/lola/LDEM_80S_80MPP_ADJ.TIF")
REAL_DEM = POLAR_DEM.exists() and POLAR_DEM.stat().st_size > 10_000
REPORT = Path("data/validation/annual_illumination_validation.json")


@unittest.skipUnless(REAL_DEM, "80 m polar DEM not present (run `git lfs pull`)")
class VectorizedPhysicsTests(unittest.TestCase):
    SITES = (np.array([-84.79, -89.5, -86.0]), np.array([29.2, 0.0, -45.0]))

    @classmethod
    def setUpClass(cls) -> None:
        from src.compute.regional import DemArray
        load_kernels()
        cls.dem = DemArray()

    @classmethod
    def tearDownClass(cls) -> None:
        unload_kernels()

    def test_bulk_masks_equal_single_site_masks(self) -> None:
        lats, lons = self.SITES
        bulk = self.dem.horizon_masks(lats, lons)
        for i in range(len(lats)):
            single = terrain.extract_horizon_mask_fast(POLAR_DEM, lats[i], lons[i]).elevation_deg
            np.testing.assert_allclose(bulk[i], single, atol=1e-8)

    def test_multiresolution_far_field_matches_full_resolution(self) -> None:
        lats, lons = self.SITES
        for lat, lon in zip(lats, lons):
            multi = terrain.extract_horizon_mask_fast(POLAR_DEM, lat, lon).elevation_deg
            full = terrain.extract_horizon_mask_fast(
                POLAR_DEM, lat, lon,
                near_field_m=terrain.HORIZON_MAX_DISTANCE_M).elevation_deg
            # Far terrain subtends tiny angles; well below the 0.27 deg solar radius.
            self.assertLess(float(np.nanmax(np.abs(multi - full))), 0.1)

    def test_bulk_visibility_equals_single_site_track(self) -> None:
        from src.compute.regional import body_tracks, epochs_between, visibility_statistics
        lats, lons = self.SITES
        masks = self.dem.horizon_masks(lats, lons)
        stats = visibility_statistics(lats, lons, masks, 1.0,
                                      body_tracks(epochs_between("2026-11-15T12:00:00Z", 3, 1)))
        for i in range(len(lats)):
            mask = terrain.HorizonMask(np.arange(0.0, 360.0, 1.0), masks[i])
            track = calculate_geometry_track(lats[i], lons[i], "2026-11-15T12:00:00Z", 3,
                                             horizon_mask=mask)
            # Track percentages are rounded to 0.01 for transport.
            self.assertAlmostEqual(100 * stats["sun_up_fraction"][i], track["sunlit_percent"], delta=0.006)
            self.assertAlmostEqual(100 * stats["earth_up_fraction"][i], track["earth_los_percent"], delta=0.006)

    def test_vectorized_event_scan_is_identical_to_scalar(self) -> None:
        import spiceypy as spice
        mask = terrain.evaluate_site_terrain(-84.79, 29.2)["horizon_mask"]
        ets = spice.str2et("2026-11-15T12:00:00Z") + np.arange(200) * 1800.0
        vectorized = _scan_margins(-84.79, 29.2, ets, mask)
        for body in ("sun", "earth"):
            scalar = np.array([_margins(-84.79, 29.2, float(et), mask)[1][body] for et in ets])
            np.testing.assert_allclose(vectorized[body], scalar, atol=1e-9)

    def test_screen_region_contract(self) -> None:
        from src.compute.proximity import nearest_psr_within
        from src.compute.regional import screen_region
        screen = screen_region(-84.79, 29.2, "2026-11-15T12:00:00Z", radius_m=1_000,
                               spacing_m=500, duration_days=2)
        columns = screen["columns"]
        self.assertTrue(all(len(v) == screen["count"] for v in columns.values()))
        self.assertEqual(screen["psr"]["status"], "complete")
        reference = nearest_psr_within(columns["latitude_deg"][0], columns["longitude_deg"][0])
        self.assertAlmostEqual(columns["psr_distance_m"][0], reference["distance_m"], delta=0.1)


@unittest.skipUnless(Path("data/illumination/AVGVISIB_85S_060M_201608.TIF").exists() and
                     Path("data/illumination/AVGVISIB_85S_060M_201608.TIF").stat().st_size > 10_000,
                     "PGDA illumination products not present (run `git lfs pull`)")
class AnnualProductSelectionTests(unittest.TestCase):
    def test_square_footprint_prefers_the_finer_product_north_of_85s(self) -> None:
        # The 60 m product is a square raster: its corners reach north of 85S,
        # so Mons Mouton (84.79S) must use it rather than the 120 m product.
        from src.compute.site_evaluation import _annual_illumination
        result = _annual_illumination(-84.79, 29.2)
        self.assertEqual(result["source_dataset"], "AVGVISIB_85S_060M_201608.TIF")
        self.assertEqual(_annual_illumination(-80.0, 10.0)["source_dataset"],
                         "AVGVISIB_75S_120M_201608.TIF")
        self.assertEqual(_annual_illumination(35.0, -20.0)["status"], "outside_product_coverage")


class ValidationProtocolTests(unittest.TestCase):
    def test_wedge_split_separates_and_buffers(self) -> None:
        angles = np.radians(np.array([10.0, 40.0, 29.9, 15.0]))
        radius = np.array([50_000.0, 50_000.0, 50_000.0, 5_000.0])
        x, y = radius * np.cos(angles), radius * np.sin(angles)
        labels = validation.wedge_split(np.zeros(4), np.zeros(4), x, y)
        self.assertEqual(labels[0], "dev")       # wedge 0
        self.assertEqual(labels[1], "test")      # wedge 1
        self.assertEqual(labels[2], "buffer")    # 0.1 deg from the boundary
        self.assertEqual(labels[3], "buffer")    # near the pole every wedge touches

    def test_metrics_and_bootstrap(self) -> None:
        truth = np.linspace(0.0, 1.0, 50)
        metrics = validation._metrics(truth + 0.01, truth)
        self.assertAlmostEqual(metrics["bias_pct"], 1.0)
        self.assertAlmostEqual(metrics["mae_pct"], 1.0)
        rng = np.random.default_rng(1)
        pred = truth + rng.normal(0, 0.02, 50)
        ci = validation.block_bootstrap(pred, truth, np.arange(50) // 5, replicates=200, seed=1)
        point = validation._metrics(pred, truth)["rmse_pct"]
        self.assertLessEqual(ci["rmse_pct"][0], point)
        self.assertGreaterEqual(ci["rmse_pct"][1], point)

    @unittest.skipUnless(REPORT.is_file(), "validation report not generated")
    def test_production_horizon_matches_validated_selection(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        selected = report["candidates"][report["selected"]]
        self.assertEqual(terrain.HORIZON_MAX_DISTANCE_M, selected["max_distance_m"])
        self.assertEqual(terrain.NEAR_FIELD_M, selected["near_field_m"])
        test = report["test"][report["selected"]]["disk_fraction"]
        # Guard against silently shipping a regression in the validated engine.
        self.assertGreater(test["r2"], 0.9)
        self.assertLess(abs(test["bias_pct"]), 1.0)


HORIZONS_CACHE = Path("data/validation/horizons")


@unittest.skipUnless(HORIZONS_CACHE.is_dir() and any(HORIZONS_CACHE.glob("*.txt")),
                     "Horizons responses not cached (python -m src.ml.horizons_crosscheck --refresh)")
class HorizonsCrossCheckTests(unittest.TestCase):
    """Independent JPL Horizons (DE441) check of the engine's Sun/Earth directions."""

    @classmethod
    def setUpClass(cls) -> None:
        from src.ml import horizons_crosscheck
        cls.result = horizons_crosscheck.run()

    def test_every_catalog_site_was_checked(self) -> None:
        from src.ml.horizons_crosscheck import catalog_sites
        self.assertEqual(self.result["sites"], len(catalog_sites()))
        self.assertGreater(self.result["samples_per_body"], 1000)

    def test_engine_matches_horizons_within_aberration(self) -> None:
        geometric = self.result["angular_separation_deg"]["geometric"]
        # Geometric vs apparent differ by stellar aberration: <= 20.6" (0.0057 deg) + DE430/DE441.
        self.assertLess(geometric["sun"]["max"], 0.007)
        self.assertLess(geometric["earth"]["max"], 0.001)

    def test_residual_is_fully_explained_by_light_corrections(self) -> None:
        apparent = self.result["angular_separation_deg"]["apparent"]
        # Same corrections in SPICE reproduce Horizons to < 0.2 arcsec: frames and time are right.
        for body in ("sun", "earth"):
            self.assertLess(apparent[body]["max"], 5e-5)
            self.assertEqual(self.result["spherical_horizon_visibility_agreement"][body]["fraction"], 1.0)


class RecommenderTests(unittest.TestCase):
    @staticmethod
    def _screen(**columns: list) -> dict:
        n = len(next(iter(columns.values())))
        base = {"latitude_deg": [-85.0] * n, "longitude_deg": list(range(n)),
                "elevation_m": [0.0] * n, "slope_deg": [1.0] * n}
        base.update(columns)
        return {"columns": base, "horizon": {"dem_resolution_m": 80.0}}

    def test_pareto_ranks_match_brute_force(self) -> None:
        values = np.random.default_rng(0).normal(size=(120, 3))
        ranks = pareto_ranks(values)
        front = {i for i in range(len(values))
                 if not any((values[j] >= values[i]).all() and (values[j] > values[i]).any()
                            for j in range(len(values)))}
        self.assertEqual(front, set(np.flatnonzero(ranks == 0)))
        self.assertTrue((ranks >= 0).all())

    def test_constraints_directions_and_ties(self) -> None:
        screen = self._screen(mean_sun_disk_percent=[90, 90, 95, 99, None],
                              earth_los_percent=[100, 100, 80, 100, 100],
                              longest_darkness_hours=[5, 5, 5, 1, 0],
                              slope_deg=[3.0, 1.0, 2.0, 9.0, 1.0])
        result = recommend_sites(screen, top_k=5)
        self.assertEqual(result["excluded"]["missing_objective_data"], 1)
        self.assertEqual(result["excluded"]["slope_at_or_above_8_deg"], 1)
        order = [r["longitude_deg"] for r in result["recommendations"]]
        # Candidates 0 and 1 tie on every objective: the gentler slope (1) first.
        self.assertLess(order.index(1), order.index(0))
        self.assertTrue(all(r["pareto_rank"] == 0 for r in result["recommendations"]))

    def test_weights_are_validated_and_reported(self) -> None:
        screen = self._screen(mean_sun_disk_percent=[50, 90], earth_los_percent=[100, 10],
                              longest_darkness_hours=[1, 1])
        with self.assertRaises(ValueError):
            recommend_sites(screen, weights={"psr_distance_m": 1.0})
        weighted = recommend_sites(screen, weights={"earth_los_percent": 1.0})
        self.assertEqual(weighted["ranking_mode"], "planner_weighted")
        self.assertEqual(weighted["recommendations"][0]["longitude_deg"], 0)

    def test_crowding_and_slope_classes(self) -> None:
        self.assertTrue(np.isinf(crowding_distance(np.array([[0.0], [1.0]]))).all())
        self.assertEqual([slope_class(s) for s in (3, 8, 12.5)], ["nominal", "caution", "critical"])


if __name__ == "__main__":
    unittest.main()
