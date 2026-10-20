"""Smoke and contract tests for the offline scientific data APIs."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.acquire import safe
from src.compute.illumination_annual import annual_illumination
from src.compute.proximity import nearest_psr
from src.compute.spice_engine import (
    calculate_geometry, load_kernels, unload_kernels,
)
from src.compute.terrain import HorizonMask


class AcquisitionTests(unittest.TestCase):
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


class ComputeContractTests(unittest.TestCase):
    def test_horizon_mask_interpolates_azimuth(self) -> None:
        mask = HorizonMask(np.array([0.0, 90.0, 180.0, 270.0]),
                           np.array([1.0, 2.0, 3.0, 4.0]))
        self.assertEqual(mask.elevation_at(90.0), 2.0)
        self.assertAlmostEqual(mask.elevation_at(360.0), 1.0)

    def test_raster_and_vector_missing_data_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.tif"
            with self.assertRaises(FileNotFoundError):
                annual_illumination(-84.79, 29.20, missing)
            with self.assertRaises(FileNotFoundError):
                nearest_psr(-84.79, 29.20, missing)

    def test_spice_geometry_is_finite_for_benchmark_coordinate(self) -> None:
        load_kernels()
        try:
            result = calculate_geometry(-84.79, 29.20, "2026-10-20T00:00:00Z")
            values = [result.earth_elevation_deg, result.earth_azimuth_deg,
                      result.sun_elevation_deg, result.sun_azimuth_deg]
            self.assertTrue(np.isfinite(values).all())
            self.assertGreaterEqual(result.earth_azimuth_deg, 0.0)
            self.assertLess(result.earth_azimuth_deg, 360.0)
        finally:
            unload_kernels()


if __name__ == "__main__":
    unittest.main()
