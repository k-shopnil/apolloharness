"""LDEM_64 global-terrain contracts: height convention, tiles, fallback, edge fill."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin

from src.acquire import nasa_products
from src.compute import global_terrain as gt
from src.compute.terrain import evaluate_site_terrain, interpolate_elevation

TILES = Path("data/lola/tiles")


def _write_synthetic_global(path: Path, dn: np.ndarray, *, scale: float = 0.5,
                            offset: float = 1_737_400.0) -> None:
    """Explicitly synthetic 1 pixel/degree grid in the LDEM_64 projection/scaling."""
    crs = CRS.from_proj4("+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=180 +x_0=0 +y_0=0 "
                         "+R=1737400 +units=m +no_defs")
    res = 2 * np.pi * 1_737_400.0 / 360.0
    rows, cols = dn.shape
    transform = from_origin(-cols * res / 2, rows * res / 2, res, res)
    with rasterio.open(path, "w", driver="GTiff", height=rows, width=cols, count=1,
                       dtype="int16", crs=crs, transform=transform, nodata=-32768) as ds:
        ds.write(dn.astype(np.int16), 1)
        ds.scales, ds.offsets = (scale,), (offset,)


def _is_real_tile(path: Path) -> bool:
    # Without `git lfs pull` the file is a ~130-byte pointer, not a GeoTIFF.
    return path.is_file() and path.stat().st_size > 10_000


class TileConversionTests(unittest.TestCase):
    def test_heights_use_scale_only_never_the_radius_offset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic_global.tif"
            _write_synthetic_global(source, np.full((180, 360), 2000))
            tile = gt.build_site_tile(20.0, 30.0, Path(tmp) / "tile.tif", global_dem=source,
                                      half_width_m=200_000, resolution_m=5_000)
            result = interpolate_elevation(20.0, 30.0, tile)
        self.assertAlmostEqual(result["elevation_m"], 1000.0, places=3)

    def test_tile_is_exact_across_the_zero_longitude_seam(self) -> None:
        # A flat synthetic map cannot reveal a misplaced seam, so heights vary
        # with longitude: DN = 20000 * sin(lon) -> height = 10000 m * sin(lon).
        lon_centres = (np.arange(360) + 0.5)
        dn = np.tile(20000 * np.sin(np.radians(lon_centres)), (180, 1))
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic_global.tif"
            _write_synthetic_global(source, dn)
            for lon in (0.3, -0.7, 179.6, -179.6):
                tile = gt.build_site_tile(10.0, lon, Path(tmp) / f"seam_{lon}.tif",
                                          global_dem=source, half_width_m=150_000,
                                          resolution_m=5_000)
                with self.subTest(lon=lon):
                    height = interpolate_elevation(10.0, lon, tile)["elevation_m"]
                    # Bilinear interpolation of a 1-degree sine: error << 1 m.
                    self.assertAlmostEqual(height, 10000 * np.sin(np.radians(lon)), delta=2.0)

    def test_polar_tile_spanning_most_longitudes_is_not_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic_global.tif"
            _write_synthetic_global(source, np.full((180, 360), 800))
            tile = gt.build_site_tile(-80.13, 1.44, Path(tmp) / "polar.tif", global_dem=source,
                                      half_width_m=160_000, resolution_m=5_000)
            with rasterio.open(tile) as ds:
                values = ds.read(1)
        self.assertTrue(np.isfinite(values).all())
        np.testing.assert_allclose(values, 400.0, atol=1e-3)

    def test_unexpected_scaling_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "synthetic_global.tif"
            _write_synthetic_global(source, np.zeros((180, 360)), scale=1.0)
            with self.assertRaisesRegex(ValueError, "scaling"):
                gt.build_site_tile(0.0, 0.0, None, global_dem=source)

    def test_committed_tile_lookup_requires_full_ray_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "a.tif").write_bytes(b"x")
            (directory / gt.TILE_INDEX).write_text(json.dumps({"tiles": [{
                "file": "a.tif", "center_lat_deg": 20.0, "center_lon_deg": 30.0,
                "half_width_m": 80_000.0}]}), encoding="utf-8")
            self.assertEqual(gt.find_committed_tile(20.0, 30.0, max_ray_m=50_000.0,
                                                    tile_dir=directory), directory / "a.tif")
            # ~1 deg = 30 km away: 30 km + 50 km rays exceed the 78.4 km usable radius.
            self.assertIsNone(gt.find_committed_tile(21.0, 30.0, max_ray_m=50_000.0,
                                                     tile_dir=directory))


class FallbackTests(unittest.TestCase):
    def test_outside_polar_dem_uses_global_product(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "synthetic_global.tif"
            _write_synthetic_global(source, np.full((180, 360), 600))
            polar = root / "missing_polar.tif"
            polar.write_bytes(b"")
            with patch.object(gt, "GLOBAL_DEM", source), patch.object(gt, "TILE_DIR", root):
                with patch("src.compute.terrain.interpolate_elevation",
                           wraps=interpolate_elevation) as spy:
                    spy.side_effect = lambda lat, lon, path: (
                        {"status": "outside_dem_coverage", "elevation_m": None}
                        if path == polar else interpolate_elevation(lat, lon, path))
                    result = evaluate_site_terrain(20.0, 30.0, polar)
        self.assertEqual(result["dem_product"], gt.PRODUCT_NAME)
        self.assertEqual(result["horizon_model"], "lola_terrain_mask")
        self.assertAlmostEqual(result["elevation_m"], 300.0, places=2)
        self.assertEqual(result["horizon_incomplete_azimuths"], 0)

    def test_without_any_terrain_source_result_is_spherical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(gt, "GLOBAL_DEM", root / "absent.lbl"), \
                    patch.object(gt, "TILE_DIR", root), \
                    patch("src.compute.terrain.interpolate_elevation",
                          return_value={"status": "outside_dem_coverage", "elevation_m": None}):
                result = evaluate_site_terrain(35.0, -20.0, root / "polar.tif")
        self.assertEqual(result["horizon_model"], "spherical_horizon")
        self.assertIsNone(result["dem_product"])


class RegistryTests(unittest.TestCase):
    def test_pds_product_status_reads_its_own_cache_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache" / "nasa" / "pds"
            cache.mkdir(parents=True)
            (cache / "x.img").write_bytes(b"data")
            spec = {"pds_test": {"files": {"x.img": ("https://example.invalid/x.img", 4, "")},
                                 "cache_subdir": "nasa/pds", "link": False,
                                 "destination": cache / "x.img", "product": "test"}}
            with patch.object(nasa_products, "PROJECT_ROOT", root), \
                    patch.object(nasa_products, "PRODUCTS", spec):
                status = nasa_products.get_product_status("pds_test")
        self.assertEqual(status["status"], "CACHED")
        self.assertEqual(status["files"][0]["path"], str(cache / "x.img"))

    def test_global_dem_is_registered_with_checksums(self) -> None:
        spec = nasa_products.PRODUCTS["lola_gdr_global_64ppd"]
        self.assertFalse(spec["link"])
        for _url, size, sha in spec["files"].values():
            self.assertGreater(size, 0)
            self.assertRegex(sha, r"^[0-9a-f]{64}$")


@unittest.skipUnless(_is_real_tile(TILES / "anchor-slim.tif"),
                     "committed LDEM_64 tiles not present (run `git lfs pull`)")
class CommittedTileScienceTests(unittest.TestCase):
    """Independent checks against published elevations; real NASA data only."""

    def test_slim_elevation_matches_lroc(self) -> None:
        # LROC/NASA report SLIM at -912 m (NAC M1460739214L context).
        result = interpolate_elevation(-13.3160, 25.2510, TILES / "anchor-slim.tif")
        self.assertAlmostEqual(result["elevation_m"], -912.0, delta=30.0)

    def test_change_4_elevation_matches_published_value(self) -> None:
        # Liu et al. (2019, Nat. Commun.) report -5935 m; ~470 m pixels smooth it.
        result = interpolate_elevation(-45.457, 177.589, TILES / "anchor-change-4.tif")
        self.assertAlmostEqual(result["elevation_m"], -5935.0, delta=50.0)

    def test_chandrayaan_3_elevation_matches_lroc(self) -> None:
        # LROC reports 69.3741S, 32.32E at 532 m elevation.
        result = interpolate_elevation(-69.3741, 32.32, TILES / "anchor-chandrayaan-3.tif")
        self.assertAlmostEqual(result["elevation_m"], 532.0, delta=30.0)

    @unittest.skipUnless(Path("data/lola/LDEM_80S_80MPP_ADJ.TIF").stat().st_size > 10_000
                         if Path("data/lola/LDEM_80S_80MPP_ADJ.TIF").exists() else False,
                         "80 m polar DEM not present (run `git lfs pull`)")
    def test_im1_elevation_matches_lroc(self) -> None:
        # LROC reports Odysseus at 80.13S, 1.44E, 2579 m elevation (80 m DEM).
        result = interpolate_elevation(-80.13, 1.44)
        self.assertAlmostEqual(result["elevation_m"], 2579.0, delta=30.0)

    def test_every_committed_tile_is_complete(self) -> None:
        index = json.loads((TILES / gt.TILE_INDEX).read_text(encoding="utf-8"))
        for tile in index["tiles"]:
            with self.subTest(tile=tile["file"]), rasterio.open(TILES / tile["file"]) as ds:
                self.assertTrue(np.isfinite(ds.read(1)).all())
                self.assertGreaterEqual(tile["half_width_m"], 150_000.0 + 5_000.0)

    def test_taurus_littrow_massifs_mask_the_horizon_but_mare_is_open(self) -> None:
        with patch.object(gt, "GLOBAL_DEM", Path("/nonexistent")):
            valley = evaluate_site_terrain(20.1911, 30.7723)
            mare = evaluate_site_terrain(0.67416, 23.47314)
        self.assertEqual(valley["source_dataset"], "anchor-apollo-17.tif")
        self.assertGreater(float(np.nanmax(valley["horizon_mask"].elevation_deg)), 8.0)
        self.assertLess(float(np.nanmax(mare["horizon_mask"].elevation_deg)), 2.0)


if __name__ == "__main__":
    unittest.main()
