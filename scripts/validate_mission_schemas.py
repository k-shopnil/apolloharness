"""Validate mission catalogs against the schema expected by frontend and downstream systems."""
import argparse
import copy
import json
import re
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

# Default values for optional fields
DEFAULT_MISSION_VALUES = {
    "target": "Moon",
    "description": "",
    "end_date": None,
    "landing_ellipse": {
        "semi_major_km": 5.0,
        "semi_minor_km": 2.5,
        "azimuth_deg": 0.0,
    },
    "payload_instruments": [],
}

DATE_REGEX = r"^\d{4}-\d{2}-\d{2}$"

LANDING_ELLIPSE_SCHEMA = {
    "type": "object",
    "required": ["semi_major_km", "semi_minor_km"],
    "properties": {
        "semi_major_km": {"type": "number", "exclusiveMinimum": 0},
        "semi_minor_km": {"type": "number", "exclusiveMinimum": 0},
        "azimuth_deg": {"type": "number", "minimum": -360, "maximum": 360},
    },
    "additionalProperties": True,
}

PAYLOAD_INSTRUMENT_SCHEMA = {
    "type": "object",
    "required": ["name", "type"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "type": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
    },
    "additionalProperties": True,
}

MISSION_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "required": [
            "id",
            "name",
            "lat",
            "lon",
            "start_date",
            "landing_ellipse",
            "payload_instruments",
        ],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "lat": {"type": "number", "minimum": -90, "maximum": 90},
            "lon": {"type": "number", "minimum": -180, "maximum": 180},
            "start_date": {"type": "string", "pattern": DATE_REGEX},
            "end_date": {"type": ["string", "null"], "pattern": DATE_REGEX},
            "target": {"type": "string", "minLength": 1},
            "description": {"type": "string"},
            "landing_ellipse": LANDING_ELLIPSE_SCHEMA,
            "payload_instruments": {
                "type": "array",
                "items": PAYLOAD_INSTRUMENT_SCHEMA,
            },
        },
        "additionalProperties": True,
    },
}


def apply_defaults(mission: dict) -> dict:
    """Ensure missing or optional fields have clean defaults."""
    sanitized = copy.deepcopy(mission)
    for key, val in DEFAULT_MISSION_VALUES.items():
        if key not in sanitized or sanitized[key] is None:
            sanitized[key] = copy.deepcopy(val)
    # If payload is provided instead of payload_instruments, map it
    if "payload" in sanitized and not sanitized.get("payload_instruments"):
        sanitized["payload_instruments"] = copy.deepcopy(sanitized["payload"])
    return sanitized


def validate_missions_data(missions: list[dict], apply_clean_defaults: bool = False) -> list[str]:
    """Validate a list of mission dictionaries against the mission schema."""
    if apply_clean_defaults:
        missions = [apply_defaults(m) for m in missions]

    validator = Draft202012Validator(MISSION_SCHEMA)
    errors = []
    for err in sorted(validator.iter_errors(missions), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "<root>"
        errors.append(f"@{loc}: {err.message}")

    # Additional semantic validation: end_date >= start_date if both present
    for idx, m in enumerate(missions):
        start = m.get("start_date")
        end = m.get("end_date")
        if start and end and re.match(DATE_REGEX, start) and re.match(DATE_REGEX, end):
            if end < start:
                errors.append(f"@{idx}/end_date: end_date '{end}' cannot be before start_date '{start}'")

    return errors


def validate_file(path: Path, apply_clean_defaults: bool = False) -> bool:
    """Validate a JSON mission catalog file."""
    if not path.exists():
        print(f"SKIP {path.relative_to(ROOT)} (not found)")
        return True

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"FAIL {path.relative_to(ROOT)}: Invalid JSON ({e})")
        return False

    missions = content.get("missions", []) if isinstance(content, dict) else content
    if not isinstance(missions, list):
        print(f"FAIL {path.relative_to(ROOT)}: Expected list of missions")
        return False

    errors = validate_missions_data(missions, apply_clean_defaults=apply_clean_defaults)
    if not errors:
        print(f"OK   {path.relative_to(ROOT)} ({len(missions)} missions verified)")
        return True

    for err in errors:
        print(f"FAIL {path.relative_to(ROOT)} {err}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mission catalogs against expected JSON schema.")
    parser.add_argument("--files", nargs="*", help="Optional specific paths to validate")
    parser.add_argument("--apply-defaults", action="store_true", help="Apply clean defaults before schema check")
    args = parser.parse_args()

    if args.files:
        targets = [Path(f) for f in args.files]
    else:
        targets = [
            ROOT / "data" / "missions.json",
            ROOT / "demo_fixtures" / "missions.json",
        ]

    results = [validate_file(p, apply_clean_defaults=args.apply_defaults) for p in targets]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
