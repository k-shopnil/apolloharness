import json
import copy
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

with open(ROOT / "data" / "missions.json", encoding="utf-8") as f:
    raw_data = json.load(f)

missions = raw_data.get("missions", raw_data) if isinstance(raw_data, dict) else raw_data

enhanced = []
for m in missions:
    item = copy.deepcopy(m)
    # Name
    item["name"] = item.get("name") or item.get("mission") or item.get("id")
    # Lat/Lon
    ls = item.get("landing_site") or {}
    lat = item.get("lat")
    if lat is None:
        lat = ls.get("latitude_deg")
    if lat is None:
        lat = -84.79  # Mons Mouton default for Griffin
    item["lat"] = float(lat)

    lon = item.get("lon")
    if lon is None:
        lon = ls.get("longitude_deg")
    if lon is None:
        lon = 29.20  # Mons Mouton default for Griffin
    item["lon"] = float(lon)

    # Dates
    start_date = item.get("start_date")
    if not start_date:
        t_date = item.get("target_date")
        if t_date and re.match(r"^\d{4}-\d{2}-\d{2}$", str(t_date)):
            start_date = str(t_date)
        elif t_date and re.match(r"^\d{4}$", str(t_date)):
            start_date = f"{t_date}-06-01"
        else:
            start_date = "2026-06-01"
    item["start_date"] = start_date
    item.setdefault("end_date", None)

    target_name = item.get("target_site") or "Moon"
    item.setdefault("target", target_name)
    item.setdefault("description", item.get("region") or f"NASA CLPS landing mission targeting {target_name}.")

    # Landing Ellipse
    if "landing_ellipse" not in item or not item["landing_ellipse"]:
        el_km = item.get("landing_ellipse_km") or {}
        maj = el_km.get("major_axis_km") or el_km.get("semi_major_km") or 4.0
        min_ax = el_km.get("minor_axis_km") or el_km.get("semi_minor_km") or 2.5
        item["landing_ellipse"] = {
            "semi_major_km": float(maj if maj is not None and maj > 0 else 4.0),
            "semi_minor_km": float(min_ax if min_ax is not None and min_ax > 0 else 2.5),
            "azimuth_deg": 0.0,
        }

    # Payload instruments
    if "payload_instruments" not in item or not item["payload_instruments"]:
        payloads = item.get("payloads") or []
        insts = []
        for p in payloads:
            p_name = p.get("name", "Sensor")
            p_type = p.get("type")
            if not p_type:
                purpose = p.get("purpose", [])
                p_type = ", ".join(purpose) if isinstance(purpose, list) and purpose else "Scientific Instrument"
            insts.append({
                "name": p_name,
                "type": p_type,
                "description": f"{p_name} science payload for lunar exploration.",
            })
        if not insts:
            insts.append({"name": "LOLA-Sensor", "type": "Altimetry", "description": "Surface topography sensor."})
        item["payload_instruments"] = insts

    enhanced.append(item)

# Write to data/missions.json
with open(r"C:\Users\Ariful\AppData\Local\Temp\enhanced.json", "w", encoding="utf-8") as f:
    json.dump(enhanced, f, indent=2)

offline_fixtures = []
for m in enhanced:
    mock_item = copy.deepcopy(m)
    if not mock_item["id"].startswith("mock-"):
        mock_item["id"] = f"mock-{mock_item['id']}"
    offline_fixtures.append(mock_item)

with open(r"C:\Users\Ariful\AppData\Local\Temp\offline_fixtures.json", "w", encoding="utf-8") as f:
    json.dump(offline_fixtures, f, indent=2)

print("Generated enhanced and offline_fixtures JSONs successfully")
