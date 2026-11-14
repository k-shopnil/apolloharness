"""Backend API contract: engine pass-through, canonical IDs, no invented values.

Uses the precomputed tracks and the catalog only (no SPICE call), so it runs in
seconds. The app's lifespan (kernel load + warm-up) is not started here.
"""
import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app

ROOT = Path(__file__).resolve().parents[1]
CATALOG_IDS = {m["id"] for m in json.loads((ROOT / "data/missions.json").read_text(encoding="utf-8"))}
INVENTED_KEYS = ("composite_viability_score", "viability_score", "total_viability_score", "tactical_mission_sunlight")

client = TestClient(app)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _walk_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk_keys(inner)


class MissionsRouteTests(unittest.TestCase):
    def test_serves_only_canonical_ids(self) -> None:
        res = client.get("/api/v1/missions")
        self.assertEqual(res.status_code, 200)
        ids = {m["id"] for m in res.json()}
        self.assertTrue(ids)
        self.assertLessEqual(ids, CATALOG_IDS)  # never an ID that isn't in data/missions.json

    def test_unpublished_values_stay_null(self) -> None:
        griffin = next(m for m in client.get("/api/v1/missions").json() if m["id"] == "clps-to20a-griffin-1")
        self.assertIsNone(griffin["lat"])  # no published landing point
        self.assertIsNone(griffin["lon"])


class GeometryRouteTests(unittest.TestCase):
    def test_catalog_site_is_engine_payload_without_invented_scores(self) -> None:
        res = client.get("/api/v1/sites/geometry", params={"site_id": "clps-prime-1-im2"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["schema"], "apolloharness.site_geometry.v1")
        self.assertEqual(body["source"], "precomputed_track")
        self.assertIn("horizon_model", body)
        keys = set(_walk_keys(body))
        for key in INVENTED_KEYS:
            self.assertNotIn(key, keys)

    def test_far_side_anchor_has_no_direct_earth_link(self) -> None:
        body = client.get("/api/v1/sites/geometry", params={"site_id": "anchor-change-4"}).json()
        self.assertIs(body["earth"]["direct_los"], False)
        self.assertEqual(body["earth"]["countdown_status"], "no_earthrise_within_window")

    def test_unknown_and_alias_ids_are_rejected(self) -> None:
        # "bg-2" used to be aliased to the terminated Draper CP-12; only canonical IDs are accepted.
        for site_id in ("bg-2", "im-2", "ls-1", "not-a-mission"):
            with self.subTest(site_id=site_id):
                self.assertEqual(client.get("/api/v1/sites/geometry", params={"site_id": site_id}).status_code, 404)

    def test_mission_without_coordinate_is_404_not_a_guess(self) -> None:
        res = client.get("/api/v1/sites/geometry", params={"site_id": "clps-to20a-griffin-1"})
        self.assertEqual(res.status_code, 404)

    def test_missing_location_is_422(self) -> None:
        self.assertEqual(client.get("/api/v1/sites/geometry").status_code, 422)


class RetiredRoutesTests(unittest.TestCase):
    def test_heuristic_score_and_comms_routes_are_gone(self) -> None:
        for path in ("/api/v1/sites/score", "/api/v1/sites/scores", "/api/v1/sites/comms"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path, params={"lat": -85, "lon": 0}).status_code, 404)


class CorsTests(unittest.TestCase):
    def test_hosted_frontend_origin_is_allowed(self) -> None:
        res = client.get("/api/v1/missions", headers={"Origin": "https://apolloharness.web.app"})
        self.assertEqual(res.headers.get("access-control-allow-origin"), "https://apolloharness.web.app")


if __name__ == "__main__":
    unittest.main()
