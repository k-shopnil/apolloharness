"""Backend bridge payloads (Issue #8 §4.2): shape, provenance and JSON validity."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from src.compute.api_payloads import (
    CATALOG, TRACK_DIR, catalog_records, mission_geometry, site_geometry,
)

POLAR_DEM = Path("data/lola/LDEM_80S_80MPP_ADJ.TIF")
REAL_DEM = POLAR_DEM.exists() and POLAR_DEM.stat().st_size > 10_000


class CatalogTests(unittest.TestCase):
    def test_every_record_is_flattened_without_invented_values(self) -> None:
        raw = {r["id"]: r for r in json.loads(CATALOG.read_text(encoding="utf-8"))}
        flat = catalog_records()
        self.assertEqual([r["id"] for r in flat], list(raw))
        for record in flat:
            site = raw[record["id"]].get("landing_site") or {}
            self.assertEqual(record["lat"], site.get("latitude_deg"))
            self.assertEqual(record["lon"], site.get("longitude_deg"))
            self.assertEqual(record["landing_ellipse"], raw[record["id"]].get("landing_ellipse_km"))
            self.assertIn(record["category"], ("clps", "reference_anchor"))
            self.assertEqual(record["has_precomputed_track"],
                             (TRACK_DIR / f"{record['id']}.json").is_file())
        griffin = next(r for r in flat if "griffin" in r["id"])
        self.assertIsNone(griffin["lat"])  # no published coordinate: stays null

    def test_start_date_only_from_full_dates(self) -> None:
        for record in catalog_records():
            if record["start_date"] is not None:
                self.assertRegex(record["start_date"], r"^\d{4}-\d{2}-\d{2}$")


class MissionGeometryTests(unittest.TestCase):
    def test_precomputed_payload_shape(self) -> None:
        payload = mission_geometry("clps-prime-1-im2")
        self.assertEqual(payload["source"], "precomputed_track")
        for body in ("sun", "earth"):
            vector = np.array(payload[body]["unit_vector_moon_pa"])
            self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=3)
        self.assertIn("direct_los", payload["earth"])
        self.assertIn("is_lit", payload["sun"])
        json.dumps(payload, allow_nan=False)

    def test_errors_map_to_http_codes(self) -> None:
        with self.assertRaises(ValueError):
            mission_geometry("../missions")
        with self.assertRaises(LookupError):
            mission_geometry("not-a-mission")
        griffin = next(r["id"] for r in catalog_records() if "griffin" in r["id"])
        with self.assertRaisesRegex(LookupError, "no precomputed track"):
            mission_geometry(griffin)


class FixtureSyncTests(unittest.TestCase):
    def test_offline_fixtures_equal_api_payloads(self) -> None:
        # The frontend's offline fallback must be byte-for-byte the API's answer.
        from src.compute.api_payloads import FIXTURE_DIR
        for record in catalog_records():
            fixture = FIXTURE_DIR / f"{record['id']}.json"
            self.assertEqual(fixture.is_file(), record["has_precomputed_track"], record["id"])
            if fixture.is_file():
                self.assertEqual(json.loads(fixture.read_text(encoding="utf-8")),
                                 json.loads(json.dumps(mission_geometry(record["id"]))),
                                 f"{record['id']}: run `python -m src.compute.api_payloads`")
        self.assertEqual(json.loads((FIXTURE_DIR / "missions.json").read_text(encoding="utf-8")),
                         json.loads(json.dumps(catalog_records())))

    def test_polar_tracks_carry_psr_context(self) -> None:
        for site_id in ("clps-prime-1-im2", "clps-to2-im-im1"):
            psr = mission_geometry(site_id)["psr"]
            self.assertEqual(psr["status"], "complete")
            self.assertTrue(psr["nearest_psr_id"].startswith("HNP_"))
            self.assertIn(psr["nearest_large_psr"]["status"], ("complete", "none_within_search_radius"))
        self.assertEqual(mission_geometry("anchor-apollo-11")["psr"]["status"], "outside_product_coverage")


@unittest.skipUnless(REAL_DEM, "80 m polar DEM not present (run `git lfs pull`)")
class SiteGeometryTests(unittest.TestCase):
    def test_engine_payload_matches_track_at_same_epoch(self) -> None:
        track = mission_geometry("clps-prime-1-im2")
        live = site_geometry(track["site"]["latitude_deg"], track["site"]["longitude_deg"],
                             track["utc"], include_psr=False)
        self.assertEqual(live["source"], "engine")
        for body in ("sun", "earth"):
            self.assertAlmostEqual(live[body]["elevation_deg"], track[body]["elevation_deg"], places=3)
            np.testing.assert_allclose(live[body]["unit_vector_moon_pa"],
                                       track[body]["unit_vector_moon_pa"], atol=1e-4)  # tracks round to 4 dp
        self.assertTrue(2.3 <= live["earth"]["round_trip_light_time_s"] <= 2.8)
        json.dumps(live, allow_nan=False)


if __name__ == "__main__":
    unittest.main()


class SensitivityHelperTests(unittest.TestCase):
    def test_distance_and_bearing(self) -> None:
        from src.compute.sensitivity import _compass, _distance_bearing
        # 0.01 deg of latitude northward on a 1737.4 km sphere ~ 303.2 m, bearing 0.
        d, b = _distance_bearing(-85.0, 30.0, np.array([-84.99]), np.array([30.0]))
        self.assertAlmostEqual(float(d[0]), 1_737_400 * np.radians(0.01), places=3)
        self.assertAlmostEqual(float(b[0]) % 360.0, 0.0, places=6)
        self.assertEqual([_compass(x) for x in (0, 44, 46, 180, 337.6)], ["N", "NE", "NE", "S", "N"])

    def test_bad_input_is_value_error(self) -> None:
        from src.compute.sensitivity import site_sensitivity
        for kwargs in ({"radius_m": 0}, {"radius_m": 6000}, {"spacing_m": 10},
                       {"slip_days": 30}, {"duration_days": 0.5}):
            with self.assertRaises(ValueError):
                site_sensitivity(-85.0, 30.0, "2026-12-01T00:00:00Z", **kwargs)


SENSITIVITY_FIXTURES = Path("offline_fixtures/site_sensitivity")


@unittest.skipUnless(REAL_DEM, "80 m polar DEM not present (run `git lfs pull`)")
class SiteSensitivityTests(unittest.TestCase):
    def test_small_grid_invariants(self) -> None:
        from src.compute.api_payloads import site_sensitivity
        r = site_sensitivity(-89.45, -137.31, "2026-12-01T00:00:00Z", radius_m=300,
                             spacing_m=100, duration_days=3, slip_days=1)
        self.assertEqual(r["schema"], "apolloharness.site_sensitivity.v1")
        json.dumps(r, allow_nan=False)
        self.assertEqual([row["slip_days"] for row in r["arrival_date"]], [-1, 0, 1])
        for key, block in r["position"].items():
            best = block["best_neighbour"]
            self.assertEqual(block["centre_is_best"], best is None, key)
            if best:
                self.assertGreater(best["improvement"], 0, key)
                self.assertLessEqual(best["distance_m"], 300 * 1.01, key)
                self.assertLessEqual(best["regional_slope_deg"], 15.0, key)
                self.assertIn(best["direction"], block["headline"])
        # Raising the observer can only lower the horizon: visibility never decreases.
        heights = r["observer_height"]
        for body in ("sunlit_percent", "earth_los_percent"):
            values = [row[body] for row in heights]
            self.assertEqual(values, sorted(values), body)

    def test_refuses_sites_whose_horizon_leaves_the_polar_dem(self) -> None:
        from src.compute.api_payloads import site_sensitivity
        with self.assertRaisesRegex(ValueError, "83.5"):
            site_sensitivity(-80.13, 1.44, "2026-12-01T00:00:00Z", radius_m=200, spacing_m=100,
                             duration_days=2, slip_days=0)

    def test_offline_fixture_equals_live_payload(self) -> None:
        from src.compute.api_payloads import mission_geometry, site_sensitivity
        files = sorted(SENSITIVITY_FIXTURES.glob("*.json"))
        self.assertTrue(files, "run python -m src.compute.api_payloads")
        fixture = json.loads(files[0].read_text(encoding="utf-8"))
        geometry = mission_geometry(fixture["site_id"])
        live = site_sensitivity(geometry["site"]["latitude_deg"],
                                geometry["site"]["longitude_deg"], geometry["utc"])
        live = json.loads(json.dumps(live))
        self.assertEqual({k: v for k, v in fixture.items() if k not in ("site_id", "mission")},
                         live)


class ArtemisRegionTests(unittest.TestCase):
    NASA_2024_REGIONS = ["Peak near Cabeus B", "Haworth", "Malapert Massif", "Mons Mouton Plateau",
                         "Mons Mouton", "Nobile Rim 1", "Nobile Rim 2", "de Gerlache Rim 2",
                         "Slater Plain"]

    def test_regions_are_labelled_as_regions_not_points(self) -> None:
        from src.compute.api_payloads import artemis_regions
        payload = artemis_regions()
        self.assertEqual(payload["schema"], "apolloharness.artemis_iii_regions.v1")
        self.assertEqual([r["name"] for r in payload["regions"]], self.NASA_2024_REGIONS)
        ids = [r["id"] for r in payload["regions"]]
        self.assertEqual(len(ids), len(set(ids)))
        for region in payload["regions"]:
            self.assertEqual(region["kind"], "candidate_region")
            self.assertIs(region["is_landing_point"], False)
            self.assertEqual(region["coordinate_basis"], "iau_feature_centre")
            self.assertLess(region["anchor"]["center_lat_deg"], -80.0)
            self.assertTrue(region["anchor"]["usgs_url"].startswith(
                "https://planetarynames.wr.usgs.gov/Feature/"))
        rims = [r for r in payload["regions"] if "Rim" in r["name"]]
        self.assertTrue(all("not at its centre" in r["anchor_relation"] for r in rims))

    def test_anchor_matches_committed_gazetteer_subset(self) -> None:
        import csv
        from src.compute.api_payloads import artemis_regions
        craters = {row["name"]: row for row in csv.DictReader(
            open("data/psr/iau_south_polar_craters.csv", encoding="utf-8"))}
        for region in artemis_regions()["regions"]:
            anchor = region["anchor"]
            if anchor["iau_name"] in craters:  # mountains are not in the crater subset
                row = craters[anchor["iau_name"]]
                self.assertAlmostEqual(float(row["center_lat_deg"]), anchor["center_lat_deg"], 3)
                self.assertAlmostEqual(float(row["center_lon_deg"]), anchor["center_lon_deg"], 3)

    def test_im2_is_linked_to_mons_mouton(self) -> None:
        from src.compute.api_payloads import artemis_regions
        mouton = next(r for r in artemis_regions()["regions"] if r["name"] == "Mons Mouton")
        self.assertIn("clps-prime-1-im2", [s["id"] for s in mouton["catalog_sites_near_anchor"]])


@unittest.skipUnless(REAL_DEM, "80 m polar DEM not present (run `git lfs pull`)")
class SiteGeometryTrackAndSlopeTests(unittest.TestCase):
    def test_include_track_adds_track_without_changing_the_readout(self) -> None:
        args = (-84.79, 29.2, "2026-12-01T00:00:00Z")
        plain = site_geometry(*args, include_psr=False)
        tracked = site_geometry(*args, include_psr=False, include_track=True, duration_days=3)
        self.assertNotIn("track", plain)
        self.assertEqual(set(tracked) - set(plain), {"track", "track_summary"})
        for key in ("sun", "earth", "terrain", "horizon_model", "utc", "schema"):
            self.assertEqual(plain[key] if key not in ("sun", "earth") else plain[key]["elevation_deg"],
                             tracked[key] if key not in ("sun", "earth")
                             else tracked[key]["elevation_deg"], key)
        columns = tracked["track"]["columns"]
        self.assertEqual(len(columns["sun_unit_moon_pa"]), len(columns["utc"]))
        self.assertEqual(set(tracked["track_summary"]),
                         {"sunlit_percent", "earth_los_percent", "mean_sun_disk_visible_fraction"})
        json.dumps(tracked, allow_nan=False)

    def test_regional_slope_is_labelled_and_matches_vectorized_engine(self) -> None:
        from src.compute.regional import DemArray
        from src.compute.terrain import regional_slope
        dem = DemArray()
        for lat, lon in ((-84.79, 29.2), (-85.3, 53.3), (-89.45, -137.31)):
            single = regional_slope(lat, lon)
            self.assertEqual(single["regional_slope_baseline_m"], 160.0)
            self.assertAlmostEqual(single["regional_slope_deg"],
                                   float(dem.slope_deg(np.array([lat]), np.array([lon]))[0]), places=2)
        terrain = site_geometry(-84.79, 29.2, "2026-12-01T00:00:00Z", include_psr=False)["terrain"]
        self.assertEqual(terrain["regional_slope_baseline_m"], 160.0)
        self.assertNotIn("slope_deg", terrain)  # never an unlabelled "slope" a UI could misread

    def test_missing_polar_dem_falls_back_to_site_tiles(self) -> None:
        import tempfile
        from src.compute.terrain import evaluate_site_terrain
        with tempfile.TemporaryDirectory() as tmp:
            pointer = Path(tmp) / "LDEM_80S_80MPP_ADJ.TIF"
            pointer.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:0\nsize 1\n",
                               encoding="utf-8")
            result = evaluate_site_terrain(20.1911, 30.7723, pointer)  # Apollo 17 tile
        self.assertEqual(result["dem_product"], "LOLA GDR LDEM_64")
        self.assertEqual(result["horizon_model"], "lola_terrain_mask")
        self.assertIsNotNone(result["regional_slope_deg"])


class SpaceWeatherTests(unittest.TestCase):
    def test_committed_windows_are_context_not_dose(self) -> None:
        from src.compute.api_payloads import mission_space_weather
        im1 = mission_space_weather("clps-to2-im-im1")
        self.assertEqual(im1["schema"], "apolloharness.space_weather_windows.v1")
        self.assertIn("not a measured dose", im1["caveat"])
        self.assertEqual(im1["status"], "complete")
        self.assertEqual(im1["sep"]["count"], len(im1["sep"]["events"]))
        from datetime import datetime

        def when(stamp: str) -> datetime:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        start, end = when(im1["window_start_utc"]), when(im1["window_end_utc"])
        for event in im1["sep"]["events"]:
            self.assertTrue(start <= when(event["time_utc"]) <= end, event["id"])
            self.assertTrue(event["link"].startswith("https://"))
        apollo = mission_space_weather("anchor-apollo-17")
        self.assertEqual(apollo["status"], "before_donki_coverage")
        self.assertIsNone(apollo["sep"])  # unknown, never 0
        with self.assertRaises(LookupError):
            mission_space_weather("clps-to20a-griffin-1")

    def test_requests_are_recorded_without_the_key(self) -> None:
        text = Path("data/space_weather/donki_mission_windows.json").read_text(encoding="utf-8")
        self.assertNotIn("api_key", text)


class NasaApiClientTests(unittest.TestCase):
    def test_key_precedence_and_redaction(self) -> None:
        import os
        import tempfile
        from unittest import mock
        from src.acquire import nasa_api
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("# comment\nNASA_API_KEY= file-key-123 \n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"NASA_API_KEY": ""}):
                self.assertEqual(nasa_api.api_key(env), ("file-key-123", ".env"))
            with mock.patch.dict(os.environ, {"NASA_API_KEY": "env-key-456"}):
                self.assertEqual(nasa_api.api_key(env), ("env-key-456", "environment"))
            with mock.patch.dict(os.environ, {"NASA_API_KEY": ""}):
                self.assertEqual(nasa_api.api_key(Path(tmp) / "missing"), ("DEMO_KEY", "DEMO_KEY"))
            self.assertEqual(nasa_api.redact("x file-key-123 y", "file-key-123"), "x *** y")

    def test_http_errors_never_contain_the_key(self) -> None:
        import io
        import os
        import tempfile
        import urllib.error
        from unittest import mock
        from src.acquire import nasa_api
        secret = "SECRET-KEY-789"
        error = urllib.error.HTTPError(f"https://api.nasa.gov/DONKI/FLR?api_key={secret}", 404,
                                       "Not Found", {}, io.BytesIO(b""))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"NASA_API_KEY": secret}), \
                mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(nasa_api.NasaApiError) as caught:
                nasa_api.get_json("DONKI/FLR", env_file=Path(tmp) / ".env", startDate="2024-01-01")
        self.assertEqual(caught.exception.status, 404)
        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("DONKI/FLR?startDate=2024-01-01", str(caught.exception))
