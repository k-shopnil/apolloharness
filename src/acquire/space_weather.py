"""Space weather during each tracked mission's analysis window (NASA DONKI).

Source: NASA CCMC DONKI (Space Weather Database Of Notifications, Knowledge,
Information) through the NASA API portal (``/DONKI/SEP`` and ``/DONKI/CME``;
needs ``NASA_API_KEY``, see ``.env.example``). For every mission with a
precomputed track, the catalogued events inside the same window the UI scrubs
(``window_start_utc`` + ``duration_days``) are summarised:

* **SEP**: solar energetic particle events, the radiation-relevant quantity
  for surface operations. Each has the detecting instruments and a DONKI link.
* **CME**: coronal mass ejections that started in the window, with the speed
  of DONKI's most accurate analysis.

What this is not: a dose or flux at the landing site. DONKI events are
detected by near-Earth or heliospheric spacecraft (listed per event); the
Moon is within ~0.003 AU of Earth but spends part of each month inside
Earth's magnetotail. The UI may say "N SEP events were catalogued during
this window", never "the site received X".

Coverage: the DONKI catalogue begins in April 2010 (first CME 2010-04-03),
so Apollo windows report ``before_donki_coverage`` instead of a misleading 0.
Flares (``/DONKI/FLR``) are recorded as unavailable: api.nasa.gov returned
HTTP 404 for that endpoint on 2026-11-13 while SEP and CME worked.

    python -m src.acquire.space_weather      # -> data/space_weather/donki_mission_windows.json
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .nasa_api import NasaApiError, get_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACK_INDEX = PROJECT_ROOT / "data" / "precomputed" / "tracks" / "index.json"
CATALOG = PROJECT_ROOT / "data" / "missions.json"
OUTPUT = PROJECT_ROOT / "data" / "space_weather" / "donki_mission_windows.json"
DONKI_COVERAGE_START = datetime(2010, 4, 1, tzinfo=timezone.utc)
SCHEMA = "apolloharness.space_weather_windows.v1"

SOURCE = {
    "organization": "NASA Community Coordinated Modeling Center (CCMC)",
    "title": "DONKI: Space Weather Database Of Notifications, Knowledge, Information",
    "url": "https://kauai.ccmc.gsfc.nasa.gov/DONKI/",
    "access": "NASA API portal https://api.nasa.gov (DONKI/SEP, DONKI/CME; personal API key)",
}
CAVEAT = ("Events are catalogued from near-Earth and heliospheric spacecraft; they are not "
          "a measured dose or flux at the landing site. The Moon spends part of each month "
          "inside Earth's magnetotail.")


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _in_window(stamp: str | None, start: datetime, end: datetime) -> bool:
    return bool(stamp) and start <= _parse(stamp) <= end


def _sep(event: dict[str, Any]) -> dict[str, Any]:
    return {"id": event.get("sepID"), "time_utc": event.get("eventTime"),
            "instruments": [i.get("displayName") for i in event.get("instruments") or []],
            "linked_events": [e.get("activityID") for e in event.get("linkedEvents") or []],
            "link": event.get("link")}


def _cme(event: dict[str, Any]) -> dict[str, Any]:
    analyses = event.get("cmeAnalyses") or []
    best = next((a for a in analyses if a.get("isMostAccurate")), analyses[0] if analyses else {})
    return {"id": event.get("activityID"), "start_utc": event.get("startTime"),
            "speed_km_s": best.get("speed"), "half_angle_deg": best.get("halfAngle"),
            "source_location": event.get("sourceLocation") or None, "link": event.get("link")}


def _query(kind: str, start: datetime, end: datetime) -> tuple[list[dict], dict[str, Any]]:
    params = {"startDate": start.strftime("%Y-%m-%d"), "endDate": end.strftime("%Y-%m-%d")}
    try:
        response = get_json(f"DONKI/{kind}", **params)
    except NasaApiError as error:
        return [], {"status": "unavailable", "http_status": error.status, "request": str(error)}
    return list(response.data or []), {"status": "complete", "request": response.request}


def window_summary(start: datetime, end: datetime, *, now: datetime | None = None
                   ) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if end < DONKI_COVERAGE_START:
        return {"status": "before_donki_coverage", "sep": None, "cme": None}
    if end > now:
        return {"status": "window_not_complete", "sep": None, "cme": None}
    raw_sep, sep_meta = _query("SEP", start, end)
    raw_cme, cme_meta = _query("CME", start, end)
    seps = [_sep(e) for e in raw_sep if _in_window(e.get("eventTime"), start, end)]
    cmes = [_cme(e) for e in raw_cme if _in_window(e.get("startTime"), start, end)]
    speeds = [c["speed_km_s"] for c in cmes if isinstance(c["speed_km_s"], (int, float))]
    status = ("partial" if start < DONKI_COVERAGE_START else
              "complete" if sep_meta["status"] == cme_meta["status"] == "complete" else
              "unavailable")
    return {
        "status": status,
        "sep": {**sep_meta, "count": len(seps) if sep_meta["status"] == "complete" else None,
                "events": seps},
        "cme": {**cme_meta, "count": len(cmes) if cme_meta["status"] == "complete" else None,
                "fastest_speed_km_s": max(speeds) if speeds else None, "events": cmes},
    }


def build(output: Path = OUTPUT) -> dict[str, Any]:
    index = json.loads(TRACK_INDEX.read_text(encoding="utf-8"))
    status_of = {m["id"]: m.get("status")
                 for m in json.loads(CATALOG.read_text(encoding="utf-8"))}
    duration = float(index["duration_days"])
    now = datetime.now(timezone.utc)
    missions = []
    for entry in index["missions"]:
        if entry.get("status") != "complete":
            continue
        start = _parse(entry["window_start_utc"])
        end = start + timedelta(days=duration)
        missions.append({"mission_id": entry["mission_id"], "mission": entry["mission"],
                         "mission_status": status_of.get(entry["mission_id"]),
                         "window_start_utc": _iso(start), "window_end_utc": _iso(end),
                         **window_summary(start, end, now=now)})
    payload = {
        "schema": SCHEMA,
        "generated_utc": _iso(now),
        "source": SOURCE,
        "window_definition": f"precomputed track window: window_start_utc + {duration} days",
        "donki_coverage_start_utc": _iso(DONKI_COVERAGE_START),
        "flares": {"status": "unavailable",
                   "reason": "api.nasa.gov DONKI/FLR returned HTTP 404 on 2026-11-13; "
                             "SEP and CME endpoints worked"},
        "caveat": CAVEAT,
        "missions": missions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    for m in result["missions"]:
        sep = (m.get("sep") or {}).get("count")
        cme = (m.get("cme") or {}).get("count")
        print(f"{m['mission_id']:<28} {m['status']:<22} SEP={sep} CME={cme}")
    print(f"-> {OUTPUT}")
