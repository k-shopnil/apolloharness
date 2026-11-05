"""PSR identifiers and IAU host-crater names."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from src.compute.proximity import DEFAULT_PSR, nearest_psr_within
from src.compute.psr_names import GAZETTEER_SUBSET, host_crater
from src.compute.terrain import MOON_GEOGRAPHIC, MOON_SPS

REAL_PSR = DEFAULT_PSR.is_file() and DEFAULT_PSR.stat().st_size > 10_000


def _gazetteer(path: Path, rows: list[tuple[str, float, float, float]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "center_lat_deg", "center_lon_deg", "diameter_km", "usgs_url"])
        for name, lat, lon, diameter in rows:
            writer.writerow([name, lat, lon, diameter, f"https://example.test/{name}"])
    return path


class HostCraterTests(unittest.TestCase):
    def test_smallest_containing_crater_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _gazetteer(Path(tmp) / "g.csv", [("Big", -89.0, 0.0, 100.0),
                                                     ("Small", -89.0, 0.0, 10.0),
                                                     ("Elsewhere", -80.0, 90.0, 5.0)])
            self.assertEqual(host_crater(-89.0, 0.0, gazetteer=path)["name"], "Small")
            # ~30 km from the centre: outside Small's 5 km radius, inside Big's 50 km.
            self.assertEqual(host_crater(-88.0, 0.0, gazetteer=path)["name"], "Big")
            self.assertIsNone(host_crater(-70.0, 180.0, gazetteer=path))

    def test_polygon_host_needs_majority_of_area(self) -> None:
        from src.compute.psr_names import host_crater_for_polygon
        with tempfile.TemporaryDirectory() as tmp:
            # Small crater at the pole inside a large one; both centred on the pole.
            path = _gazetteer(Path(tmp) / "g.csv", [("Big", -89.9, 0.0, 60.0),
                                                     ("Small", -89.9, 0.0, 6.0)])
            pole = gpd.GeoSeries([Point(0.0, -89.9)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
            inside_small = pole.buffer(2_000.0)            # 100 % inside Small
            spills_out = pole.buffer(10_000.0)             # only 9 % inside Small, 100 % in Big
            outside_all = Point(pole.x + 200_000, pole.y).buffer(1_000.0)
            self.assertEqual(host_crater_for_polygon(inside_small, MOON_SPS, gazetteer=path)["name"], "Small")
            big = host_crater_for_polygon(spills_out, MOON_SPS, gazetteer=path)
            self.assertEqual(big["name"], "Big")
            self.assertGreaterEqual(big["psr_area_fraction_inside_rim"], 0.99)
            self.assertIsNone(host_crater_for_polygon(outside_all, MOON_SPS, gazetteer=path))

    def test_missing_gazetteer_degrades_to_none(self) -> None:
        self.assertIsNone(host_crater(-89.5, 0.0, gazetteer=Path("/nonexistent.csv")))

    def test_pgda_name_column_is_used_as_identifier(self) -> None:
        # PGDA's product stores its stable ID in "name"; "gid" is only a row number.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "psr.shp"
            centre = gpd.GeoSeries([Point(29.2, -84.79)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
            gpd.GeoDataFrame({"gid": [7], "area_km2": [0.8], "name": ["HNP_TEST"]},
                             geometry=[centre.buffer(500.0)], crs=MOON_SPS).to_file(path)
            result = nearest_psr_within(-84.79, 29.2, 5_000.0, path)
        self.assertEqual(result["nearest_psr_id"], "HNP_TEST")
        self.assertAlmostEqual(result["nearest_psr_area_km2"], 0.8)

    def test_nearest_large_psr_skips_micro_cold_traps(self) -> None:
        # NASA stores area_km2 as text; a 0.001 km2 trap is nearer than the large one.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "psr.shp"
            centre = gpd.GeoSeries([Point(29.2, -84.79)], crs=MOON_GEOGRAPHIC).to_crs(MOON_SPS).iloc[0]
            micro = Point(centre.x + 300.0, centre.y).buffer(15.0)
            large = Point(centre.x + 5_000.0, centre.y).buffer(1_000.0)
            gpd.GeoDataFrame({"name": ["MICRO", "LARGE"], "area_km2": ["0.001", "3.142"]},
                             geometry=[micro, large], crs=MOON_SPS).to_file(path)
            result = nearest_psr_within(-84.79, 29.2, 20_000.0, path)
        self.assertEqual(result["nearest_psr_id"], "MICRO")
        large_result = result["nearest_large_psr"]
        self.assertEqual(large_result["status"], "complete")
        self.assertEqual(large_result["id"], "LARGE")
        self.assertAlmostEqual(large_result["distance_m"], 4_000.0, delta=5.0)


@unittest.skipUnless(REAL_PSR and GAZETTEER_SUBSET.is_file(),
                     "PGDA PSR product or gazetteer subset not present")
class RealPsrNamingTests(unittest.TestCase):
    def test_known_south_polar_craters(self) -> None:
        # Well-known cold traps: a site on each crater floor must name its host.
        for name, lat, lon in (("Shackleton", -89.67, 129.78), ("Haworth", -87.45, -5.17),
                               ("Faustini", -87.18, 84.31)):
            host = host_crater(lat, lon)
            self.assertIsNotNone(host, name)
            self.assertEqual(host["name"], name)

    def test_gazetteer_agrees_with_catalog_target_feature(self) -> None:
        import json
        from src.compute.terrain import DATA_DIR
        missions = json.loads((DATA_DIR / "missions.json").read_text(encoding="utf-8"))
        griffin = next(m for m in missions if "griffin" in m["id"])["target_feature"]
        nobile = host_crater(griffin["latitude_deg"], griffin["longitude_deg"])
        self.assertEqual(nobile["name"], "Nobile")
        self.assertLess(nobile["distance_from_center_km"], 0.5)

    def test_real_psr_result_carries_id_and_host(self) -> None:
        result = nearest_psr_within(-89.67, 129.78)  # Shackleton floor: inside a PSR
        self.assertTrue(result["inside_psr"])
        self.assertTrue(result["nearest_psr_id"].startswith("HNP_"))
        self.assertEqual(result["nearest_psr_label"], "PSR in Shackleton crater")


if __name__ == "__main__":
    unittest.main()
