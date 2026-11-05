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
