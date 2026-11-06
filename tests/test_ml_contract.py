"""Leakage and missing-data contracts for the untrained ML layer."""
from __future__ import annotations

import unittest

from src.ml.features import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    assert_chronological_splits,
    assert_disjoint_spatial_splits,
    assert_spatial_buffered_splits,
    audit_dataset,
    build_site_feature_record,
    is_benchmark_site,
    model_unavailable,
    spatial_group,
)


class MLContractTests(unittest.TestCase):
    def test_feature_builder_preserves_unavailable_as_null_and_separates_quality(self) -> None:
        row = build_site_feature_record(
            -86.0, 12.0,
            terrain={"data_status": "PROVISIONAL", "valid_fraction": 0.75},
            annual_illumination={"annual_sunlight_percent": None, "data_status": "UNAVAILABLE"},
            provenance={"spice_status": "REAL"},
            analysis_start_utc="2026-10-20T00:00:00+00:00",
        )
        self.assertEqual(row["feature_schema_version"], FEATURE_SCHEMA_VERSION)
        self.assertIsNone(row["features"]["annual_sunlight_percent"])
        self.assertEqual(row["data_quality"]["terrain_valid_fraction"], 0.75)
        self.assertAlmostEqual(row["data_quality"]["data_completeness_percent"], 100 * 1.75 / 6)
        self.assertEqual(row["ml"]["status"], "NOT_TRAINED")

    def test_benchmark_locations_are_excluded_by_default(self) -> None:
        self.assertTrue(is_benchmark_site(-89.54, 0.0))
        with self.assertRaisesRegex(ValueError, "evaluation-only"):
            build_site_feature_record(-89.54, 0.0)
        self.assertFalse(is_benchmark_site(-86.0, 12.0))

    def test_spatial_groups_and_overlap_checks(self) -> None:
        self.assertEqual(spatial_group(0, 180), spatial_group(0, -180))
        assert_disjoint_spatial_splits(["lat00_lon00"], ["lat10_lon10"], ["lat20_lon20"])
        assert_spatial_buffered_splits(["lat00_lon00"], ["lat10_lon10"], ["lat20_lon20"])
        with self.assertRaisesRegex(ValueError, "overlap"):
            assert_disjoint_spatial_splits(["lat00_lon00"], ["lat00_lon00"], ["lat20_lon20"])
        with self.assertRaisesRegex(ValueError, "adjacency buffer"):
            assert_spatial_buffered_splits(["lat10_lon10"], ["lat11_lon10"], ["lat20_lon20"])

    def test_chronological_split_rejects_future_leakage(self) -> None:
        assert_chronological_splits(["2020-01-01T00:00:00Z"],
                                    ["2021-01-01T00:00:00Z"],
                                    ["2022-01-01T00:00:00Z"])
        with self.assertRaisesRegex(ValueError, "chronological"):
            assert_chronological_splits(["2021-01-01T00:00:00Z"],
                                        ["2020-01-01T00:00:00Z"],
                                        ["2022-01-01T00:00:00Z"])

    def test_dataset_audit_blocks_target_leakage_and_benchmark_records(self) -> None:
        with self.assertRaisesRegex(ValueError, "leakage"):
            audit_dataset([{"site_utility_score": 1}],
                          feature_columns=["site_utility_score"],
                          target_column="site_utility_score")
        with self.assertRaisesRegex(ValueError, "Benchmark"):
            audit_dataset([{}], benchmark_flags=[True])
        statuses = {key: "REAL" for key in (
            "terrain_data_status", "illumination_data_status",
            "annual_illumination_data_status", "communications_data_status",
            "psr_data_status", "spice_status")}
        report = audit_dataset([{"latitude_deg": 1, "longitude_deg": 2,
                                 "spatial_group": "lat18_lon36",
                                 "data_quality": statuses}],
                               feature_columns=FEATURE_COLUMNS)
        self.assertEqual(report["total_samples"], 1)
        self.assertEqual(report["unique_spatial_groups"], 1)
        self.assertIsNone(report["target_distribution"])
        with self.assertRaisesRegex(ValueError, "non-real"):
            audit_dataset([{"latitude_deg": 1, "longitude_deg": 2,
                            "spatial_group": "lat18_lon36",
                            "data_quality": {**statuses, "psr_data_status": "UNAVAILABLE"}}])

    def test_model_unavailable_contract(self) -> None:
        result = model_unavailable("Model not fitted")
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["prediction"])
        self.assertEqual(result["feature_schema_version"], FEATURE_SCHEMA_VERSION)

    def test_sunlight_variance_uses_observed_illumination_states(self) -> None:
        row = build_site_feature_record(
            -86.0, 12.0,
            tactical_illumination={
                "tactical_sunlight_percent": 50.0,
                "hourly": [
                    {"sun_elevation_deg": 5.0, "illuminated": True},
                    {"sun_elevation_deg": -2.0, "illuminated": False},
                ],
            },
        )
        self.assertEqual(row["features"]["sunlight_variance"], 0.25)

    def test_feature_window_requires_ordered_timezone_aware_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "offset"):
            build_site_feature_record(-86.0, 12.0, analysis_start_utc="2026-10-20T00:00:00")
        with self.assertRaisesRegex(ValueError, "later"):
            build_site_feature_record(-86.0, 12.0,
                                      analysis_start_utc="2026-10-20T01:00:00Z",
                                      analysis_end_utc="2026-10-20T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
