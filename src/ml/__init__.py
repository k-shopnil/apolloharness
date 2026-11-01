"""Leakage-safe, physics-informed lunar site intelligence utilities.

The deterministic science engine remains authoritative. No model is trained
or loaded by importing this package: ``recommend`` ranks exact-physics
screens transparently, and ``validation`` measures the engine against NASA's
independent illumination product.
"""

from .features import (
    FEATURE_SCHEMA_VERSION,
    assert_spatial_buffered_splits,
    build_site_feature_record,
)
from .recommend import pareto_ranks, recommend_sites

__all__ = ["FEATURE_SCHEMA_VERSION", "build_site_feature_record",
           "assert_spatial_buffered_splits", "recommend_sites", "pareto_ranks"]
