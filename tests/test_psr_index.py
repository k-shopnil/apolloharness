"""The derived PSR search index is a real file, reused across processes, built by streaming.

Regression: the temporary name used to end in ".partial", so GDAL's FlatGeobuf
driver wrote a directory; the is_file() reuse check never matched and every
process rebuilt the index (~900 MB peak, which crashed a 512 MB host).
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon

from src.compute import proximity


def _square(x: float, y: float, size: float = 1.0) -> Polygon:
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


class PsrIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "psr.shp"
        # Mixed Polygon / MultiPolygon, like the NASA product.
        gpd.GeoDataFrame(
            {"area_km2": [1.0, 2.5, 0.2]},
            geometry=[_square(0, 0), MultiPolygon([_square(5, 5), _square(8, 8)]), _square(-3, -3, 0.5)],
            crs="EPSG:4326",
        ).to_file(self.source)
        self.derived = root / "derived"
        patches = [mock.patch.object(proximity, "DERIVED_DIR", self.derived),
                   mock.patch.object(proximity, "INDEX_MIN_BYTES", 0)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_index_is_a_file_with_every_feature_and_no_leftovers(self) -> None:
        target = proximity.indexed_psr_path(self.source)
        self.assertEqual(target, self.derived / "psr.fgb")
        self.assertTrue(target.is_file(), "index must be a file, not a directory")
        self.assertEqual([p.name for p in self.derived.iterdir()], ["psr.fgb"])  # no .partial leftovers
        built = gpd.read_file(target)
        self.assertEqual(len(built), 3)
        self.assertEqual(sorted(built["area_km2"]), [0.2, 1.0, 2.5])
        self.assertEqual(sorted(built.geom_type.unique()), ["MultiPolygon", "Polygon"])

    def test_second_call_reuses_the_index(self) -> None:
        first = proximity.indexed_psr_path(self.source)
        stamp = first.stat().st_mtime_ns
        with mock.patch("pyogrio.write_arrow", side_effect=AssertionError("rebuilt")):
            again = proximity.indexed_psr_path(self.source)
        self.assertEqual(again, first)
        self.assertEqual(again.stat().st_mtime_ns, stamp)

    def test_bbox_reads_match_the_source(self) -> None:
        bbox = (4.0, 4.0, 10.0, 10.0)
        via_index = gpd.read_file(proximity.indexed_psr_path(self.source), bbox=bbox)
        via_source = gpd.read_file(self.source, bbox=bbox)
        self.assertEqual(list(via_index["area_km2"]), list(via_source["area_km2"]))
        self.assertTrue(via_index.geometry.iloc[0].equals(via_source.geometry.iloc[0]))


if __name__ == "__main__":
    unittest.main()
