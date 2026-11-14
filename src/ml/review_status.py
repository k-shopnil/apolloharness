"""Human scientific review status for the validation artifacts.

Sign-offs live in ``data/validation/human_review.json``, not in generator
code, so re-running a validation script keeps the reviewer's decision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REVIEW_PATH = Path(__file__).resolve().parents[2] / "data" / "validation" / "human_review.json"
DEFAULT_REVIEWER = "@Thirtha17"
STATUSES = {"pending", "accepted"}


def review_fields(key: str, path: Path = REVIEW_PATH) -> dict[str, Any]:
    """Return ``human_review_*`` fields for one artifact (``pending`` if unrecorded)."""
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))["reviews"].get(key, {})
    except (OSError, ValueError, KeyError):
        entry = {}
    status = entry.get("status", "pending")
    if status not in STATUSES:
        raise ValueError(f"{path}: review status for {key!r} must be one of {sorted(STATUSES)}")
    fields: dict[str, Any] = {
        "human_review_status": status,
        "human_reviewer": entry.get("reviewer", DEFAULT_REVIEWER),
    }
    if entry.get("date"):
        fields["human_review_date"] = entry["date"]
    return fields
