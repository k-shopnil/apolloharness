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
