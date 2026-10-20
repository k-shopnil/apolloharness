"""Contract tests using temporary, explicitly synthetic geospatial test data."""
from __future__ import annotations
import json
import io
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point
from pyproj import Transformer

from src.acquire import safe
from src.compute.illumination_annual import calculate_annual_illumination
from src.compute.illumination_mission import calculate_mission_illumination
from src.compute.proximity import calculate_psr_distance
from src.compute.spice_engine import (
    HourlyGeometry, calculate_geometry, load_kernels, unload_kernels,
    summarize_communications, _observer_position, _observer_position_me,
)
from src.compute.terrain import (
    MOON_GEOGRAPHIC, MOON_SPS, HorizonMask, extract_horizon_mask,
)


class AcquisitionTests(unittest.TestCase):
    def test_online_fetch_writes_then_reads_cache(self) -> None:
        response = io.BytesIO(b'{"source":"online"}')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(safe, "CACHE_DIR", root / "cache"), patch.object(
                safe, "FIXTURE_DIR", root / "fixtures"
            ), patch("src.acquire.safe.urllib.request.urlopen", return_value=response) as open_url:
                first = safe.fetch_json("https://example.invalid/data", cache_name="item.json",
                                        fixture_name="missing.json", timeout=0.01)
                self.assertTrue((root / "cache" / "item.json").is_file())
                open_url.side_effect = OSError("network offline")
                second = safe.fetch_json("https://example.invalid/data", cache_name="item.json",
                                         fixture_name="missing.json", timeout=0.01)
        self.assertEqual(first, {"source": "online"})
        self.assertEqual(second, first)

    def test_binary_fetch_streams_to_cache(self) -> None:
        response = io.BytesIO(b"large scientific file bytes")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(safe, "CACHE_DIR", root / "cache"), patch.object(
                safe, "FIXTURE_DIR", root / "fixtures"
            ), patch("src.acquire.safe.urllib.request.urlopen", return_value=response):
                path = safe.fetch_file("https://example.invalid/data.tif",
                                       cache_name="dataset/data.tif",
                                       fixture_name="missing/data.tif")
            self.assertEqual(path.read_bytes(), b"large scientific file bytes")
            self.assertFalse(path.with_suffix(".tif.tmp").exists())

    def test_unreachable_url_uses_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fixtures").mkdir()
            (root / "fixtures" / "missions.json").write_text(
                json.dumps([{"mission": "Peregrine Mission 1"}]), encoding="utf-8")
            with patch.object(safe, "CACHE_DIR", root / "cache"), patch.object(
                safe, "FIXTURE_DIR", root / "fixtures"
            ):
                result = safe.fetch_json(
                    "http://127.0.0.1:1/unreachable", cache_name="missions.json",
                    fixture_name="missions.json", timeout=0.1)
        self.assertEqual(result[0]["mission"], "Peregrine Mission 1")

    def test_committed_mission_fixture_has_eight_sourced_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(safe, "CACHE_DIR", Path(tmp) / "cache"):
                missions = safe.fetch_json(
                    "http://127.0.0.1:1/unreachable",
                    cache_name="missions.json",
                    fixture_name="missions.json",
                    timeout=0.1,
                )
        self.assertEqual(len(missions), 8)
        self.assertEqual(missions[0]["mission"], "Peregrine Mission 1")
        self.assertTrue(all(record["sources"] for record in missions))
        self.assertTrue(all(record["demo_analysis"]["analysis_status"] ==
                            "not_computed_missing_scientific_products" for record in missions))


class ComputeContractTests(unittest.TestCase):
    def test_horizon_mask_interpolates_azimuth(self) -> None:
        mask = HorizonMask(np.array([0.0, 90.0, 180.0, 270.0]),
                           np.array([1.0, 2.0, 3.0, 4.0]))
        self.assertEqual(mask.elevation_at(90.0), 2.0)
        self.assertAlmostEqual(mask.elevation_at(360.0), 1.0)

    def test_lola_raster_generates_horizon_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_test_dem.tif"
            x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(29.2, -84.79)
            transform = from_origin(x - 450, y + 450, 100, 100)
            with rasterio.open(path, "w", driver="GTiff", height=9, width=9,
                               count=1, dtype="float32", crs=MOON_SPS, transform=transform) as ds:
                ds.write(np.zeros((9, 9), dtype=np.float32), 1)
            mask = extract_horizon_mask(path, -84.79, 29.2, max_distance_m=300,
                                        radial_step_m=100, azimuth_step_deg=90)
        self.assertEqual(len(mask.azimuth_deg), 4)
        self.assertTrue(np.isfinite(mask.elevation_deg).all())

    def _write_test_dem(self, path: Path, values: np.ndarray) -> None:
        x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(29.2, -84.79)
        transform = from_origin(x - values.shape[1] * 50, y + values.shape[0] * 50, 100, 100)
        with rasterio.open(path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1],
                           count=1, dtype="float32", crs=MOON_SPS, transform=transform,
                           nodata=-9999) as ds:
            ds.write(values.astype(np.float32), 1)

    def test_horizon_marks_incomplete_rays_nan_and_rejects_all_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full = root / "full.tif"
            self._write_test_dem(full, np.zeros((41, 41)))
            complete = extract_horizon_mask(full, -84.79, 29.2, max_distance_m=300,
                                            radial_step_m=100, azimuth_step_deg=90)
            self.assertTrue(np.isfinite(complete.elevation_deg).all())
            partial = root / "partial.tif"
            values = np.zeros((41, 41)); values[20, 21:] = -9999
            self._write_test_dem(partial, values)
            incomplete = extract_horizon_mask(partial, -84.79, 29.2, max_distance_m=300,
                                              radial_step_m=100, azimuth_step_deg=90)
            self.assertTrue(np.isnan(incomplete.elevation_deg[1]))
            self.assertTrue(np.isfinite(incomplete.elevation_deg[0]))
            self.assertTrue(np.isnan(incomplete.elevation_at(45)))
            all_missing = root / "all_missing_rays.tif"
            all_values = np.full((41, 41), -9999.0); all_values[20, 20] = 0
            self._write_test_dem(all_missing, all_values)
            with self.assertRaisesRegex(ValueError, "No complete terrain rays"):
                extract_horizon_mask(all_missing, -84.79, 29.2, max_distance_m=300,
                                     radial_step_m=100, azimuth_step_deg=90)

    def test_moon_me_polar_projection_matches_known_pole_geometry(self) -> None:
        tx = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True)
        x0, y0 = tx.transform(0, -90)
        x1, y1 = tx.transform(0, -89)
        self.assertAlmostEqual(x0, 0, delta=1e-8)
        self.assertAlmostEqual(y0, 0, delta=1e-8)
        self.assertGreater(y1, 0)
        self.assertAlmostEqual(np.hypot(x1, y1), 30_324.12, delta=1)

    def test_tactical_rule_compares_against_terrain_horizon(self) -> None:
        records = [
            HourlyGeometry("2026-10-20T00:00:00Z", 1, 0, -1, 0, True),
            HourlyGeometry("2026-10-20T01:00:00Z", 1, 0, 2, 180, True),
        ]
        mask = HorizonMask(np.array([0.0, 180.0]), np.array([-2.0, 3.0]))
        with patch("src.compute.illumination_mission.load_kernels"), patch(
            "src.compute.illumination_mission.unload_kernels"
        ), patch("src.compute.illumination_mission.calculate_geometry", side_effect=records):
            result = calculate_mission_illumination(-84.79, 29.2,
                "2026-10-20T00:00:00Z", 2 / 24, mask)
        self.assertEqual(result["tactical_sunlight_percent"], 50.0)
        self.assertTrue(result["hourly"][0]["illuminated"])
        self.assertFalse(result["hourly"][1]["illuminated"])

    def test_annual_raster_sample_has_separate_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_test_annual.tif"
            x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(0, -89.54)
            transform = from_origin(x - 450, y + 450, 100, 100)
            values = np.full((9, 9), 89.4, dtype=np.float32)
            with rasterio.open(path, "w", driver="GTiff", height=9, width=9,
                               count=1, dtype="float32", crs=MOON_SPS, transform=transform) as ds:
                ds.write(values, 1)
            result = calculate_annual_illumination(-89.54, 0.0, path)
        self.assertAlmostEqual(result["annual_sunlight_percent"], 89.4, places=4)
        self.assertEqual(result["analysis_type"], "annual_strategic_illumination")

    def test_annual_nodata_is_unavailable_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "annual_nodata.tif"
            x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(0, -89.54)
            transform = from_origin(x - 450, y + 450, 100, 100)
            with rasterio.open(path, "w", driver="GTiff", height=9, width=9, count=1,
                               dtype="float32", crs=MOON_SPS, transform=transform, nodata=-9999) as ds:
                ds.write(np.full((9, 9), -9999, dtype=np.float32), 1)
            with self.assertRaisesRegex(ValueError, "outside valid"):
                calculate_annual_illumination(-89.54, 0.0, path)

    def test_annual_scaled_fraction_becomes_percent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scaled_annual.tif"
            x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(0, -89.54)
            transform = from_origin(x - 450, y + 450, 100, 100)
            with rasterio.open(path, "w", driver="GTiff", height=9, width=9,
                               count=1, dtype="int16", crs=MOON_SPS, transform=transform,
                               nodata=-32768) as ds:
                ds.write(np.full((9, 9), 22350, dtype=np.int16), 1)
                ds.scales = [0.00004]
                ds.offsets = [0.0]
            result = calculate_annual_illumination(-89.54, 0.0, path)
        self.assertAlmostEqual(result["annual_sunlight_percent"], 89.4, places=4)

    def test_psr_distance_is_metric_and_returns_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_test_psr.gpkg"
            x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(0, -89.54)
            frame = gpd.GeoDataFrame({"psr_id": ["TEST_ONLY"]},
                geometry=[Point(x, y).buffer(2000)], crs=MOON_SPS)
            frame.to_file(path, driver="GPKG")
            result = calculate_psr_distance(-89.54, 0.0, path)
        # A 64-segment buffer approximates a circle; its nearest vertex is
        # slightly inside the requested 2 km radius.
        self.assertAlmostEqual(result["distance_m"], 2000.0, delta=3.0)
        self.assertEqual(result["nearest_psr"], "TEST_ONLY")

    def test_communications_intervals_are_half_open_hour_bins(self) -> None:
        start = datetime(2026, 10, 20, tzinfo=timezone.utc)
        rows = [HourlyGeometry((start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               0, 0, 0, 0, visible)
                for i, visible in enumerate([False, False, True, False])]
        summary = summarize_communications(rows)
        result = summary.to_dict()
        self.assertEqual(result["communications_uptime_percent"], 25.0)
        self.assertEqual(result["longest_blackout_hours"], 2.0)
        self.assertEqual(result["blackout_intervals"][-1]["end_utc"], "2026-10-20T04:00:00Z")

    def test_raster_and_vector_missing_data_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.tif"
            with self.assertRaises(FileNotFoundError):
                calculate_annual_illumination(-84.79, 29.20, missing)
            with self.assertRaises(FileNotFoundError):
                calculate_psr_distance(-84.79, 29.20, missing)

    def test_spice_kernel_loading_is_idempotent_and_geometry_finite(self) -> None:
        load_kernels()
        try:
            import spiceypy as spice
            count = spice.ktotal("ALL")
            load_kernels()
            self.assertEqual(spice.ktotal("ALL"), count)
            result = calculate_geometry(-84.79, 29.20, "2026-10-20T00:00:00Z")
            values = [result.earth_elevation_deg, result.earth_azimuth_deg,
                      result.sun_elevation_deg, result.sun_azimuth_deg]
            self.assertTrue(np.isfinite(values).all())
            self.assertGreaterEqual(result.earth_azimuth_deg, 0.0)
            self.assertLess(result.earth_azimuth_deg, 360.0)
        finally:
            unload_kernels()

    def test_spice_observer_coordinates_transform_from_me_to_pa(self) -> None:
        import spiceypy as spice
        load_kernels()
        try:
            et = spice.str2et("2026-10-20T00:00:00Z")
            mean_earth = _observer_position_me(-84.79, 29.20)
            principal_axes = _observer_position(-84.79, 29.20, et)
            expected = spice.mxv(spice.pxform("MOON_ME", "MOON_PA", et), mean_earth)
            np.testing.assert_allclose(principal_axes, expected, rtol=0, atol=1e-9)
            # SPICE body radii and positions are in km; the DE421 frame offset
            # is sub-km here, consistent with NASA's ~875 m global figure.
            self.assertGreater(float(np.linalg.norm(principal_axes - mean_earth)), 0.5)
        finally:
            unload_kernels()

    def test_spice_rejects_invalid_coordinates_and_naive_utc(self) -> None:
        load_kernels()
        try:
            for lat, lon in ((91, 0), (-91, 0), (0, 181), (0, -181)):
                with self.subTest(lat=lat, lon=lon), self.assertRaises(ValueError):
                    calculate_geometry(lat, lon, "2026-10-20T00:00:00Z")
            with self.assertRaisesRegex(ValueError, "offset"):
                calculate_geometry(-84.79, 29.2, "2026-10-20T00:00:00")
            result = calculate_geometry(-84.79, 29.2, "2026-10-20T00:00:00+00:00")
            self.assertEqual(result.utc, "2026-10-20T00:00:00Z")
        finally:
            unload_kernels()

    def test_manifest_schema_and_fixture_have_no_science_numbers(self) -> None:
        manifest = json.loads(Path("data/missions.json").read_text(encoding="utf-8"))
        fixtures = json.loads(Path("demo_fixtures/missions.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 8)
        self.assertEqual([m["id"] for m in manifest], [m["id"] for m in fixtures])
        required = {"id", "task_order", "provider", "mission", "target_site", "region",
                    "status", "target_date", "landing_site", "landing_ellipse_km", "payloads", "sources"}
        for mission, fixture in zip(manifest, fixtures):
            self.assertTrue(required.issubset(mission))
            self.assertTrue({"latitude_deg", "longitude_deg", "coordinate_type"}.issubset(mission["landing_site"]))
            self.assertTrue(mission["sources"])
            self.assertEqual(fixture["demo_analysis"]["analysis_status"], "not_computed_missing_scientific_products")
            for key in ("tactical_sunlight_percent", "annual_sunlight_percent", "communications_uptime_percent", "psr_distance_m"):
                self.assertIsNone(fixture["demo_analysis"][key])


if __name__ == "__main__":
    unittest.main()
