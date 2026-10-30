"""Issue #8 data-pipeline contracts: custom coordinates, horizon events, tracks."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from src.compute.spice_engine import (
    calculate_geometry, calculate_geometry_track, calculate_hourly_geometry,
    find_horizon_events, format_countdown, load_kernels, unload_kernels,
)
from src.compute.terrain import (
    MOON_GEOGRAPHIC, MOON_SPS, HorizonMask, evaluate_site_terrain, extract_horizon_mask,
    extract_horizon_mask_fast, interpolate_elevation,
)


def _write_dem(path: Path, values: np.ndarray, lat: float, lon: float, pixel: float = 100.0) -> None:
    """Explicitly synthetic DEM centred (pixel-centre) on the given coordinate."""
    x, y = Transformer.from_crs(MOON_GEOGRAPHIC, MOON_SPS, always_xy=True).transform(lon, lat)
    rows, cols = values.shape
    transform = from_origin(x - cols * pixel / 2, y + rows * pixel / 2, pixel, pixel)
    with rasterio.open(path, "w", driver="GTiff", height=rows, width=cols, count=1,
                       dtype="float32", crs=MOON_SPS, transform=transform, nodata=-9999) as ds:
        ds.write(values.astype(np.float32), 1)


class TerrainInterpolationTests(unittest.TestCase):
    def test_bilinear_elevation_is_exact_on_a_linear_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_plane.tif"
            cols = np.arange(41, dtype=float)
            _write_dem(path, np.tile(cols * 10.0, (41, 1)), -84.79, 29.2)
            centre = interpolate_elevation(-84.79, 29.2, path)
            # Pixel centre of column 20 holds 200 m; the observer sits there.
            self.assertAlmostEqual(centre["elevation_m"], 200.0, places=3)
            self.assertEqual(centre["status"], "complete")
            self.assertEqual(centre["interpolation"], "bilinear")
            outside = interpolate_elevation(0.67, 23.47, path)
        self.assertIsNone(outside["elevation_m"])
        self.assertEqual(outside["status"], "outside_dem_coverage")

    def test_fast_mask_matches_reference_on_flat_terrain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_flat.tif"
            _write_dem(path, np.zeros((41, 41)), -84.79, 29.2)
            reference = extract_horizon_mask(path, -84.79, 29.2, max_distance_m=1000,
                                             radial_step_m=100, azimuth_step_deg=90)
            fast = extract_horizon_mask_fast(path, -84.79, 29.2, max_distance_m=1000,
                                             radial_step_m=100, azimuth_step_deg=90)
        np.testing.assert_allclose(fast.elevation_deg, reference.elevation_deg, atol=1e-9)

    def test_fast_mask_recovers_known_wall_angle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_wall.tif"
            values = np.zeros((61, 61))
            values[:, 40:] = 100.0  # observer at column 30; wall starts ~1 km away
            _write_dem(path, values, -84.79, 29.2)
            mask = extract_horizon_mask_fast(path, -84.79, 29.2, max_distance_m=2000,
                                             radial_step_m=10, azimuth_step_deg=1,
                                             observer_height_m=0.0)
        # Map "east" at this longitude is not grid +x, so locate the wall's peak.
        peak = float(np.nanmax(mask.elevation_deg))
        self.assertAlmostEqual(peak, np.degrees(np.arctan2(100.0, 950.0)), delta=0.6)
        self.assertLess(float(np.nanmin(mask.elevation_deg)), 0.1)

    def test_rays_crossing_nodata_are_unknown_not_flat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_half_nodata.tif"
            values = np.zeros((41, 41)); values[:, :15] = -9999
            _write_dem(path, values, -84.79, 29.2)
            mask = extract_horizon_mask_fast(path, -84.79, 29.2, max_distance_m=1000,
                                             radial_step_m=50, azimuth_step_deg=10)
        self.assertTrue(np.isnan(mask.elevation_deg).any())
        self.assertTrue(np.isfinite(mask.elevation_deg).any())
        self.assertIn(None, mask.to_dict()["elevation_deg"])

    def test_pole_observer_has_complete_rays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_pole.tif"
            _write_dem(path, np.zeros((41, 41)), -90.0, 0.0)
            mask = extract_horizon_mask_fast(path, -90.0, 0.0, max_distance_m=1500,
                                             radial_step_m=100, azimuth_step_deg=10)
        self.assertTrue(np.isfinite(mask.elevation_deg).all())

    def test_site_terrain_degrades_to_spherical_outside_dem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_flat.tif"
            _write_dem(path, np.zeros((21, 21)), -84.79, 29.2)
            result = evaluate_site_terrain(20.19, 30.77, path, global_terrain=False)
        self.assertIsNone(result["horizon_mask"])
        self.assertEqual(result["horizon_model"], "spherical_horizon")


class HorizonEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_kernels()

    @classmethod
    def tearDownClass(cls) -> None:
        unload_kernels()

    def test_format_countdown(self) -> None:
        self.assertEqual(format_countdown(114.2), "4d 18h")
        self.assertEqual(format_countdown(5.2), "5h 12m")
        self.assertIsNone(format_countdown(None))
        self.assertIsNone(format_countdown(-1.0))

    def test_events_are_true_horizon_crossings(self) -> None:
        result = find_horizon_events(-84.79, 29.2, "2026-11-15T12:00:00Z", 29.5, horizon_mask=None)
        self.assertEqual(result["horizon_model"], "spherical_horizon")
        sun_events = [e for e in result["events"] if e["body"] == "sun"]
        self.assertTrue(sun_events)
        for event in result["events"]:
            geo = calculate_geometry(-84.79, 29.2, event["utc"])
            elevation = geo.sun_elevation_deg if event["body"] == "sun" else geo.earth_elevation_deg
            # 1 s bisection tolerance, reported at whole-second UTC precision.
            self.assertLess(abs(elevation), 0.01, event)
        kinds = [e["kind"] for e in sun_events]
        self.assertTrue(all(a != b for a, b in zip(kinds, kinds[1:])))

    def test_countdown_matches_first_set_event(self) -> None:
        result = find_horizon_events(-84.79, 29.2, "2026-11-15T12:00:00Z", 29.5, horizon_mask=None)
        sun = result["sun"]
        self.assertTrue(sun["is_lit"])
        first_set = next(e for e in result["events"] if e["body"] == "sun" and e["kind"] == "set")
        self.assertAlmostEqual(sun["time_to_sunset_hours"], first_set["hours_from_start"], places=3)
        self.assertEqual(sun["time_to_sunset_formatted"], format_countdown(sun["time_to_sunset_hours"]))
        self.assertIsNone(sun["time_to_sunrise_hours"])
        earth = result["earth"]
        for key in ("azimuth_deg", "elevation_deg", "direct_los", "time_to_earthset_hours",
                    "time_to_earthset_formatted"):
            self.assertIn(key, earth)
        self.assertGreater(earth["round_trip_light_time_s"], 2.3)
        self.assertLess(earth["round_trip_light_time_s"], 2.8)

    def test_farside_earth_never_rises_and_is_not_extrapolated(self) -> None:
        result = find_horizon_events(-45.457, 177.589, "2019-01-03T02:26:00Z", 29.5, horizon_mask=None)
        earth = result["earth"]
        self.assertFalse(earth["direct_los"])
        self.assertIsNone(earth["time_to_earthrise_hours"])
        self.assertEqual(earth["countdown_status"], "no_earthrise_within_window")
        self.assertEqual(earth["fraction_of_window_up"], 0.0)

    def test_apollo_11_touchdown_sun_is_low_morning_sun(self) -> None:
        # Historical landing was planned for a ~10-11 deg morning Sun.
        result = find_horizon_events(0.67416, 23.47314, "1969-07-20T20:17:40Z", 2.0, horizon_mask=None)
        self.assertGreater(result["sun"]["elevation_deg"], 9.5)
        self.assertLess(result["sun"]["elevation_deg"], 12.0)
        self.assertTrue(result["earth"]["direct_los"])

    def test_default_auto_mask_uses_lola_terrain(self) -> None:
        result = find_horizon_events(-84.79, 29.2, "2026-11-15T12:00:00Z", 1.0)
        self.assertEqual(result["horizon_model"], "lola_terrain_mask")
        self.assertNotEqual(result["sun"]["terrain_horizon_deg"], 0.0)
        with self.assertRaises(ValueError):
            find_horizon_events(-84.79, 29.2, "2026-11-15T12:00:00Z", 1.0, horizon_mask="flat")

    def test_terrain_mask_blocks_low_sun_and_unknown_sector_is_explicit(self) -> None:
        wall = HorizonMask(np.arange(0.0, 360.0, 1.0), np.full(360, 45.0))
        blocked = find_horizon_events(-84.79, 29.2, "2026-11-15T12:00:00Z", 2.0, horizon_mask=wall)
        self.assertFalse(blocked["sun"]["is_lit"])
        self.assertEqual(blocked["horizon_model"], "lola_terrain_mask")
        unknown = HorizonMask(np.arange(0.0, 360.0, 1.0), np.full(360, np.nan))
        result = find_horizon_events(-84.79, 29.2, "2026-11-15T12:00:00Z", 2.0, horizon_mask=unknown)
        self.assertIsNone(result["sun"]["is_lit"])
        self.assertIsNone(result["sun"]["time_to_sunset_hours"])
        self.assertEqual(result["sun"]["countdown_status"], "terrain_horizon_incomplete")

    def test_hourly_geometry_supports_sub_hour_steps(self) -> None:
        default = calculate_hourly_geometry(-84.79, 29.2, "2026-11-15T12:00:00Z", 3)
        fine = calculate_hourly_geometry(-84.79, 29.2, "2026-11-15T12:00:00Z", 3, step_minutes=15)
        self.assertEqual(len(default), 3)
        self.assertEqual(len(fine), 12)
        self.assertEqual(fine[4].utc, default[1].utc)

    def test_track_columns_are_parallel_and_physical(self) -> None:
        track = calculate_geometry_track(-84.79, 29.2, "2026-11-15T12:00:00Z", 1.0)
        columns = track["columns"]
        self.assertEqual(track["samples"], 25)
        self.assertTrue(all(len(v) == 25 for v in columns.values()))
        for vector in columns["sun_unit_moon_pa"] + columns["earth_unit_moon_pa"]:
            self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=3)
        self.assertEqual(columns["sun_lit"][0], columns["sun_elevation_deg"][0] > 0)
        json.dumps(track)  # must be serializable for the API/frontend


class SiteEvaluationTests(unittest.TestCase):
    def test_psr_inside_polygon_reports_zero_distance(self) -> None:
        import geopandas as gpd
        from shapely.geometry import Point
        from src.compute.proximity import nearest_psr_within
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic_psr.shp"
            centre = gpd.GeoSeries([Point(29.2, -84.79)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
            gpd.GeoDataFrame({"psr_id": ["P1"]}, geometry=[centre.buffer(500.0)],
                             crs=MOON_SPS).to_file(path)
            inside = nearest_psr_within(-84.79, 29.2, 5_000.0, path)
            far = nearest_psr_within(-85.5, 29.2, 5_000.0, path)
        self.assertEqual(inside["distance_m"], 0.0)
        self.assertTrue(inside["inside_psr"])
        self.assertEqual(inside["nearest_psr_id"], "P1")
        self.assertIsNone(far["distance_m"])
        self.assertEqual(far["min_distance_m"], 5_000.0)

    def test_custom_site_and_launch_slip_contracts(self) -> None:
        from src.compute.site_evaluation import compare_launch_dates, evaluate_custom_site
        with tempfile.TemporaryDirectory() as tmp:
            dem = Path(tmp) / "synthetic_flat.tif"
            _write_dem(dem, np.zeros((21, 21)), -84.79, 29.2)
            try:
                site = evaluate_custom_site(20.1911, 30.7723, "1972-12-11T19:54:57Z",
                                            duration_days=2.0, dem_path=dem, global_terrain=False)
                slip = compare_launch_dates(20.1911, 30.7723, "2026-11-15T00:00:00Z",
                                            "2026-11-18T00:00:00Z", duration_days=1.0, dem_path=dem,
                                            global_terrain=False)
            finally:
                unload_kernels()
        self.assertEqual(site["horizon_model"], "spherical_horizon")
        self.assertIsNone(site["terrain"]["elevation_m"])
        self.assertEqual(site["psr"]["status"], "not_requested")
        self.assertIn("time_to_sunset_hours", site["sun"])
        self.assertIn("time_to_earthset_hours", site["earth"])
        a, b = slip["date_a"]["track"], slip["date_b"]["track"]
        self.assertEqual(a["columns"]["hours_from_start"], b["columns"]["hours_from_start"])
        self.assertIn("sunlit_percent", slip["delta_b_minus_a"])
        json.dumps(slip)


class ManifestGroundingTests(unittest.TestCase):
    def test_reference_anchors_are_sourced_and_no_placeholders_remain(self) -> None:
        manifest = json.loads(Path("data/missions.json").read_text(encoding="utf-8"))
        ids = {m["id"] for m in manifest}
        self.assertFalse({"ls-1", "prime-2", "PRIME-2"} & ids)
        anchors = [m for m in manifest if m["category"] == "reference_anchor"]
        self.assertEqual({m["mission"] for m in anchors},
                         {"Apollo 11", "Apollo 17", "Chandrayaan-3", "Chang'e 4", "SLIM"})
        for mission in anchors:
            self.assertRegex(mission["touchdown_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertTrue(mission["sources"])
            self.assertIsNotNone(mission["landing_site"]["latitude_deg"])
        for mission in manifest:
            self.assertEqual(mission["payload_summary"],
                             ", ".join(p["name"] for p in mission["payloads"]))
        self.assertTrue(all(m["category"] in {"clps", "reference_anchor"} for m in manifest))


if __name__ == "__main__":
    unittest.main()
