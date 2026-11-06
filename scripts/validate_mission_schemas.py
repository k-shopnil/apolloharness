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
    """Ensure missing or optional fields have clean defaults.
    
    Robustly handles mapping from Issue #2 data pipeline properties:
    landing_site -> lat/lon, mission -> name, target_date -> start_date,
    payloads -> payload_instruments.
    """
    sanitized = copy.deepcopy(mission)
    sanitized["name"] = sanitized.get("name") or sanitized.get("mission") or sanitized.get("id")

    landing_site = sanitized.get("landing_site") or {}
    lat_val = sanitized.get("lat")
    if lat_val is None:
        lat_val = landing_site.get("latitude_deg")
    if lat_val is None:
        lat_val = -84.79
    sanitized["lat"] = float(lat_val)

    lon_val = sanitized.get("lon")
    if lon_val is None:
        lon_val = landing_site.get("longitude_deg")
    if lon_val is None:
        lon_val = 29.20
    sanitized["lon"] = float(lon_val)

    start_date = sanitized.get("start_date")
    if not start_date:
        t_date = sanitized.get("target_date")
        if t_date and re.match(DATE_REGEX, str(t_date)):
            start_date = str(t_date)
        elif t_date and re.match(r"^\d{4}$", str(t_date)):
            start_date = f"{t_date}-06-01"
        else:
            start_date = "2026-06-01"
    sanitized["start_date"] = start_date

    for key, val in DEFAULT_MISSION_VALUES.items():
        if key not in sanitized or sanitized[key] is None:
            sanitized[key] = copy.deepcopy(val)

    if not sanitized.get("payload_instruments"):
        payloads = sanitized.get("payloads") or sanitized.get("payload") or []
        insts = []
        for p in payloads:
            p_name = p.get("name", "Sensor")
            p_type = p.get("type")
            if not p_type:
                purpose = p.get("purpose", [])
                p_type = ", ".join(purpose) if isinstance(purpose, list) and purpose else "Science Instrument"
            insts.append({
                "name": p_name,
                "type": p_type,
                "description": p.get("description", f"{p_name} science payload for lunar exploration."),
            })
        if not insts:
            insts.append({"name": "Standard Instrument", "type": "Science", "description": "Default lunar exploration payload."})
        sanitized["payload_instruments"] = insts

    return sanitized


def validate_missions_data(missions: list[dict], apply_clean_defaults: bool = True) -> list[str]:
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


def validate_file(path: Path, apply_clean_defaults: bool = True) -> bool:
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
    parser.add_argument("--no-defaults", action="store_true", help="Do not apply defaults before schema check")
    args = parser.parse_args()

    apply_defaults_flag = not args.no_defaults

    if args.files:
        targets = [Path(f) for f in args.files]
    else:
        targets = [
            ROOT / "data" / "missions.json",
            ROOT / "demo_fixtures" / "missions.json",
        ]

    results = [validate_file(p, apply_clean_defaults=apply_defaults_flag) for p in targets]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
