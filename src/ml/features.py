"""Stable features and audit helpers for candidate-site intelligence.

This module contains no fitted model and does not synthesize science values.
It combines already-computed deterministic products and preserves unavailable
values as ``None``. Benchmark locations are excluded from training records by
default and must be held out from final evaluation partitions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

FEATURE_SCHEMA_VERSION = "apollo-lunar-site-v1"
MODEL_STATUS_NOT_TRAINED = "NOT_TRAINED"

# Approximate validation locations from the Issue #2 command. These are
# evaluation-only regions, not model training examples.
BENCHMARK_SITES: dict[str, tuple[float, float, float]] = {
    "shackleton_rim": (-89.54, 0.0, 50.0),
    "mons_mouton": (-84.79, 29.20, 50.0),
    # Deep crater location is not sufficiently specified in current inputs.
}

FEATURE_COLUMNS = (
    "latitude_deg",
    "longitude_deg",
    "elevation_m",
    "slope_deg",
    "terrain_roughness_m",
    "tactical_sunlight_percent",
    "mean_sun_elevation_deg",
    "minimum_sun_elevation_deg",
    "maximum_sun_elevation_deg",
    "sunlight_variance",
    "longest_dark_period_hours",
    "annual_sunlight_percent",
    "earth_visibility_percent",
    "mean_earth_elevation_deg",
    "minimum_earth_elevation_deg",
    "maximum_earth_elevation_deg",
    "longest_earth_blackout_hours",
    "psr_distance_km",
)

QUALITY_COLUMNS = ("terrain_valid_fraction", "illumination_valid_fraction",
                   "communication_valid_fraction")

STATUS_COLUMNS = (
    "terrain_data_status",
    "illumination_data_status",
    "annual_illumination_data_status",
    "communications_data_status",
    "psr_data_status",
    "spice_status",
)

FORBIDDEN_FEATURE_NAMES = frozenset({
    "target", "label", "site_utility_score", "physics_score", "ml_score",
    "site_rank", "risk_score", "benchmark_expected_value",
})


def _finite_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Expected a numeric feature or null, got {value!r}") from None
    if not (-float("inf") < number < float("inf")):
        raise ValueError("Feature values must be finite or null")
    return number


def _has_real_provenance(status: Any) -> bool:
    return status in {"REAL", "DERIVED_REAL", "PROVISIONAL", "CACHED"}


def _aggregate_hourly(records: Sequence[Mapping[str, Any]], prefix: str,
                      value_key: str) -> dict[str, Any]:
    values: list[float] = []
    valid_flags: list[bool] = []
    for row in records:
        value = _finite_or_none(row.get(value_key))
        valid = value is not None
        valid_flags.append(valid)
        if valid:
            values.append(value)
    total = len(records)
    return {
        f"mean_{prefix}_elevation_deg": sum(values) / len(values) if values else None,
        f"minimum_{prefix}_elevation_deg": min(values) if values else None,
        f"maximum_{prefix}_elevation_deg": max(values) if values else None,
        f"{prefix}_valid_fraction": (sum(valid_flags) / total) if total else None,
    }


def is_benchmark_site(latitude_deg: float, longitude_deg: float) -> bool:
    """Return true within the configured exclusion radius of a benchmark."""
    lat = _finite_or_none(latitude_deg)
    lon = _finite_or_none(longitude_deg)
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Valid finite lunar latitude/longitude are required")
    # Haversine distance on the 1,737.4 km reference sphere.
    import math

    for benchmark_lat, benchmark_lon, exclusion_radius_km in BENCHMARK_SITES.values():
        p1, p2 = math.radians(lat), math.radians(benchmark_lat)
        delta_p = p2 - p1
        delta_l = math.radians((benchmark_lon - lon + 180.0) % 360.0 - 180.0)
        a = math.sin(delta_p / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(delta_l / 2) ** 2
        distance_km = 2 * 1737.4 * math.asin(min(1.0, math.sqrt(a)))
        if distance_km <= exclusion_radius_km:
            return True
    return False


def build_site_feature_record(
    latitude_deg: float,
    longitude_deg: float,
    *,
    terrain: Mapping[str, Any] | None = None,
    tactical_illumination: Mapping[str, Any] | None = None,
    annual_illumination: Mapping[str, Any] | None = None,
    communications: Mapping[str, Any] | None = None,
    psr: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
    analysis_start_utc: str | None = None,
    analysis_end_utc: str | None = None,
) -> dict[str, Any]:
    """Combine completed physics products into a schema-versioned record.

    Inputs are deterministic result objects; unavailable or invalid products
    should be omitted or carry null values. The result does not calculate a
    score, infer missing data, or claim model predictions.
    """
    lat = _finite_or_none(latitude_deg)
    lon = _finite_or_none(longitude_deg)
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Valid finite lunar latitude/longitude are required")
    if is_benchmark_site(lat, lon):
        raise ValueError("Benchmark sites are evaluation-only and excluded from training records")

    terrain = terrain or {}
    tactical_illumination = tactical_illumination or {}
    annual_illumination = annual_illumination or {}
    communications = communications or {}
    psr = psr or {}
    provenance = dict(provenance or {})

    hourly_sun = list(tactical_illumination.get("hourly") or [])
    hourly_earth = list(communications.get("hourly") or [])
    sun = _aggregate_hourly(hourly_sun, "sun", "sun_elevation_deg")
    earth = _aggregate_hourly(hourly_earth, "earth", "earth_elevation_deg")
    sun_valid_fraction = sun.pop("sun_valid_fraction")

    illumination_valid_fraction = (
        sum(row.get("illuminated") is not None for row in hourly_sun) / len(hourly_sun)
        if hourly_sun else None
    )
    if illumination_valid_fraction is None:
        illumination_valid_fraction = sun_valid_fraction
    tactical_percent = _finite_or_none(tactical_illumination.get("tactical_sunlight_percent"))
    annual_percent = _finite_or_none(annual_illumination.get("annual_sunlight_percent"))
    earth_percent = _finite_or_none(communications.get("communications_uptime_percent"))
    psr_distance = _finite_or_none(psr.get("distance_km"))
    if psr_distance is None and psr.get("distance_m") is not None:
        psr_distance = _finite_or_none(psr.get("distance_m")) / 1000.0

    observed_illumination = [float(row["illuminated"]) for row in hourly_sun
                             if isinstance(row.get("illuminated"), bool)]
    illumination_variance = (
        sum((v - sum(observed_illumination) / len(observed_illumination)) ** 2
            for v in observed_illumination) / len(observed_illumination)
        if observed_illumination else None
    )
    feature_values = {
        "latitude_deg": lat,
        "longitude_deg": lon,
        "elevation_m": _finite_or_none(terrain.get("elevation_m")),
        "slope_deg": _finite_or_none(terrain.get("slope_deg")),
        "terrain_roughness_m": _finite_or_none(terrain.get("roughness_m")),
        "tactical_sunlight_percent": tactical_percent,
        **sun,
        "sunlight_variance": illumination_variance,
        "longest_dark_period_hours": _finite_or_none(tactical_illumination.get("longest_darkness_hours")),
        "annual_sunlight_percent": annual_percent,
        "earth_visibility_percent": earth_percent,
        "longest_earth_blackout_hours": _finite_or_none(communications.get("longest_blackout_hours")),
        "psr_distance_km": psr_distance,
    }
    quality = {
        "terrain_valid_fraction": _finite_or_none(terrain.get("valid_fraction")),
        "illumination_valid_fraction": illumination_valid_fraction,
        "communication_valid_fraction": earth["earth_valid_fraction"],
    }
    # Reject implausible ranges rather than letting bad inputs reach future ML.
    for key in ("tactical_sunlight_percent", "annual_sunlight_percent", "earth_visibility_percent"):
        value = feature_values[key]
        if value is not None and not 0.0 <= value <= 100.0:
            raise ValueError(f"{key} must be between 0 and 100 percent")
    for key in ("terrain_valid_fraction", "illumination_valid_fraction",
                "communication_valid_fraction"):
        value = quality.get(key)
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"{key} must be a fraction between 0 and 1")
    status = {
        "terrain_data_status": terrain.get("data_status", "UNAVAILABLE"),
        "illumination_data_status": tactical_illumination.get("data_status", "UNAVAILABLE"),
        "annual_illumination_data_status": annual_illumination.get("data_status", "UNAVAILABLE"),
        "communications_data_status": communications.get("data_status", "UNAVAILABLE"),
        "psr_data_status": psr.get("data_status", "UNAVAILABLE"),
        "spice_status": provenance.get("spice_status", "UNAVAILABLE"),
    }
    observed_components = (
        (quality["terrain_valid_fraction"] or 0.0)
        if _has_real_provenance(status["terrain_data_status"]) else 0.0,
        (quality["illumination_valid_fraction"] or 0.0)
        if _has_real_provenance(status["illumination_data_status"]) else 0.0,
        1.0 if annual_percent is not None and _has_real_provenance(status["annual_illumination_data_status"]) else 0.0,
        (quality["communication_valid_fraction"] or 0.0)
        if _has_real_provenance(status["communications_data_status"]) else 0.0,
        1.0 if psr_distance is not None and _has_real_provenance(status["psr_data_status"]) else 0.0,
        1.0 if provenance.get("spice_status") in {"REAL", "DERIVED_REAL"} else 0.0,
    )
    completeness = 100.0 * sum(observed_components) / len(observed_components)
    dates = {}
    for key, value in (("analysis_start_utc", analysis_start_utc), ("analysis_end_utc", analysis_end_utc)):
        if value is not None:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError(f"{key} must include a UTC offset")
            dates[key] = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if "analysis_start_utc" in dates and "analysis_end_utc" in dates:
        if _parse_timestamp(dates["analysis_end_utc"]) <= _parse_timestamp(dates["analysis_start_utc"]):
            raise ValueError("analysis_end_utc must be later than analysis_start_utc")

    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": feature_values,
        "feature_columns": list(FEATURE_COLUMNS),
        "data_quality": {**status, **quality, "data_completeness_percent": completeness,
                          "source_provenance": provenance},
        "time": dates,
        "source_products": {
            "terrain": terrain.get("source_dataset"),
            "illumination": tactical_illumination.get("source_dataset"),
            "annual_illumination": annual_illumination.get("source_raster"),
            "communications": communications.get("source_kernels"),
            "psr": psr.get("source_dataset"),
        },
        "ml": {"status": MODEL_STATUS_NOT_TRAINED, "prediction": None,
               "confidence": None, "reason": "No leakage-audited training dataset or fitted model is available."},
    }


def spatial_group(latitude_deg: float, longitude_deg: float,
                  block_size_deg: float = 5.0) -> str:
    """Assign coordinates to deterministic equal-angle spatial blocks."""
    lat = _finite_or_none(latitude_deg)
    lon = _finite_or_none(longitude_deg)
    size = _finite_or_none(block_size_deg)
    if lat is None or lon is None or size is None or size <= 0:
        raise ValueError("Finite coordinates and positive block_size_deg are required")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Coordinates out of range")
    # Normalize +180 to -180 so the dateline has one canonical assignment.
    lon = (lon + 180.0) % 360.0 - 180.0
    lat_index = int((lat + 90.0) // size)
    lon_index = int((lon + 180.0) // size)
    return f"lat{lat_index:02d}_lon{lon_index:02d}"


def audit_dataset(rows: Sequence[Mapping[str, Any]], *,
                  feature_columns: Sequence[str] = FEATURE_COLUMNS,
                  target_column: str | None = None,
                  benchmark_flags: Sequence[bool] | None = None,
                  group_column: str = "spatial_group",
                  time_column: str | None = None,
                  require_real_data: bool = True) -> dict[str, Any]:
    """Report data risks and fail closed for target leakage or benchmark rows."""
    columns = set(feature_columns)
    forbidden = sorted(columns & FORBIDDEN_FEATURE_NAMES)
    if target_column and target_column in columns:
        forbidden.append(target_column)
    if forbidden:
        raise ValueError(f"Target/score leakage in feature schema: {sorted(set(forbidden))}")
    if benchmark_flags is not None and (len(benchmark_flags) != len(rows) or any(benchmark_flags)):
        raise ValueError("Benchmark locations must be held out from training data")
    for row in rows:
        feature_row = row.get("features", row)
        lat, lon = feature_row.get("latitude_deg"), feature_row.get("longitude_deg")
        if lat is not None and lon is not None and is_benchmark_site(lat, lon):
            raise ValueError("Benchmark locations must be held out from training data")
    if require_real_data:
        for index, row in enumerate(rows):
            quality = row.get("data_quality", row)
            missing_status = [column for column in STATUS_COLUMNS if column not in quality]
            if missing_status:
                raise ValueError(f"Training row {index} lacks provenance statuses: {missing_status}")
            rejected = [column for column in STATUS_COLUMNS
                        if quality[column] not in {"REAL", "DERIVED_REAL"}]
            if rejected:
                raise ValueError(f"Training row {index} contains non-real/unavailable sources: {rejected}")
    groups = [row.get(group_column) for row in rows]
    if any(group is None for group in groups):
        raise ValueError("Every training row must have a spatial group")
    if target_column and any(row.get(target_column) is None for row in rows):
        raise ValueError("Training rows must have a non-null target")
    if time_column and any(row.get(time_column) is None for row in rows):
        raise ValueError("Temporal evaluation rows must have a time group")
    missing_counts = {
        column: sum(row.get(column) is None for row in rows)
        for column in feature_columns
    }
    coordinates = [(row.get("latitude_deg"), row.get("longitude_deg")) for row in rows]
    duplicated_coordinates = len(coordinates) - len(set(coordinates))
    signatures = [tuple(row.get(column) for column in feature_columns) for row in rows]
    duplicate_rows = len(signatures) - len(set(signatures))
    times = {row.get(time_column) for row in rows} if time_column else set()
    return {
        "total_samples": len(rows),
        "unique_spatial_groups": len({group for group in groups if group is not None}),
        "unique_temporal_groups": len(times - {None}) if time_column else None,
        "feature_count": len(feature_columns),
        "target_column": target_column,
        "target_distribution": None if not target_column else _counts(row.get(target_column) for row in rows),
        "missing_value_counts": missing_counts,
        "duplicate_rows": duplicate_rows,
        "duplicate_coordinates": duplicated_coordinates,
        "benchmark_rows": sum(bool(flag) for flag in benchmark_flags) if benchmark_flags else 0,
    }


def _counts(values: Iterable[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = "<NULL>" if value is None else str(value)
        result[key] = result.get(key, 0) + 1
    return result


def assert_disjoint_spatial_splits(train: Iterable[str], validation: Iterable[str],
                                   test: Iterable[str]) -> None:
    """Reject identical spatial group overlap across model-development partitions."""
    train_set, validation_set, test_set = set(train), set(validation), set(test)
    if train_set & validation_set or train_set & test_set or validation_set & test_set:
        raise ValueError("Spatial groups overlap across train/validation/test splits")


def assert_spatial_buffered_splits(train: Iterable[str], validation: Iterable[str],
                                   test: Iterable[str], *, buffer_blocks: int = 1,
                                   longitude_blocks: int = 72) -> None:
    """Reject adjacent grid groups across partitions to reduce spatial leakage.

    The default one-block buffer on the 5-degree schema excludes adjacent
    latitude/longitude cells (including wrapped longitude at the dateline).
    This is a conservative screening guard, not a geodesic buffer operation.
    """
    if buffer_blocks < 0:
        raise ValueError("buffer_blocks must be non-negative")
    partitions = {"train": set(train), "validation": set(validation), "test": set(test)}
    assert_disjoint_spatial_splits(*partitions.values())
    parsed = {name: [_parse_spatial_group(group) for group in groups]
              for name, groups in partitions.items()}
    names = list(parsed)
    for left_index, left_name in enumerate(names):
        for right_name in names[left_index + 1:]:
            right_cells = set(parsed[right_name])
            for lat_a, lon_a in parsed[left_name]:
                for delta_lat in range(-buffer_blocks, buffer_blocks + 1):
                    for delta_lon in range(-buffer_blocks, buffer_blocks + 1):
                        candidate = (lat_a + delta_lat,
                                     (lon_a + delta_lon) % longitude_blocks)
                        if candidate in right_cells:
                            raise ValueError("Spatial groups violate the configured adjacency buffer")


def _parse_spatial_group(group: str) -> tuple[int, int]:
    try:
        lat_part, lon_part = group.split("_", maxsplit=1)
        if not lat_part.startswith("lat") or not lon_part.startswith("lon"):
            raise ValueError
        return int(lat_part[3:]), int(lon_part[3:])
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f"Invalid spatial group id: {group!r}") from None


def assert_chronological_splits(train_times: Iterable[str], validation_times: Iterable[str],
                                test_times: Iterable[str]) -> None:
    """Reject temporal overlap or backwards ordering for temporal evaluations."""
    train = [_parse_timestamp(value) for value in train_times]
    validation = [_parse_timestamp(value) for value in validation_times]
    test = [_parse_timestamp(value) for value in test_times]
    if not train or not validation or not test:
        raise ValueError("Temporal split partitions must not be empty")
    if max(train) >= min(validation) or max(validation) >= min(test):
        raise ValueError("Temporal splits must be strictly chronological and non-overlapping")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Temporal split timestamps must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def model_unavailable(reason: str, *, feature_schema_version: str = FEATURE_SCHEMA_VERSION) -> dict[str, Any]:
    """Stable downstream result when no compatible, validated model exists."""
    return {"status": "UNAVAILABLE", "prediction": None, "rank": None,
            "confidence": None, "model_version": None,
            "feature_schema_version": feature_schema_version, "reason": reason}
