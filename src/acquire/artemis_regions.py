"""Build the committed Artemis III candidate-region registry.

NASA named nine candidate landing **regions** for Artemis III on
2024-10-28 (release 24-136), "in no priority order". NASA published the
regions as boxes on an image only: no coordinates, boundaries or sizes.
Each region contains several potential sites, and NASA will pick sites
within regions only after it sets the launch dates.

So this registry does **not** invent region centres or landing points.
Each region is tied to the IAU feature that names it, with that feature's
official centre from the USGS Gazetteer of Planetary Nomenclature, and an
explicit ``anchor_relation`` (for example, "Nobile Rim 1" lies on the rim
of Nobile crater, not at its centre). The UI may place a region label at
the anchor and must say "region near <feature>", never "landing site".

    python -m src.acquire.artemis_regions     # rebuild data/artemis_iii_regions.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .usgs_nomenclature import ARCHIVE, PROJECT_ROOT, SHA256, ensure_archive

OUTPUT = PROJECT_ROOT / "data" / "artemis_iii_regions.json"
CATALOG = PROJECT_ROOT / "data" / "missions.json"
MOON_RADIUS_KM = 1737.4
NEARBY_CATALOG_KM = 50.0

SOURCES = [
    {"title": "NASA Provides Update on Artemis III Moon Landing Regions (release 24-136)",
     "publisher": "NASA", "date": "2024-10-28",
     "url": "https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/"},
    {"title": "Artemis III Site Selection Update: Downselection From Thirteen to Nine "
              "Candidate Regions (George, Rubio, Lawrence, Curell; LPSC 2026)",
     "publisher": "NASA NTRS 20250011660", "date": "2026-03-16",
     "url": "https://ntrs.nasa.gov/citations/20250011660"},
    {"title": "Gazetteer of Planetary Nomenclature (IAU WGPSN), Moon centre points",
     "publisher": "USGS Astrogeology", "sha256": SHA256,
     "url": "https://planetarynames.wr.usgs.gov/"},
]

# (region name as NASA writes it, IAU anchor feature, relation of region to anchor)
REGIONS = (
    ("Peak near Cabeus B", "Cabeus B", "region is on a peak near this crater"),
    ("Haworth", "Haworth", "region is named after this crater and lies near it"),
    ("Malapert Massif", "Mons Malapert", "region is on this massif"),
    ("Mons Mouton Plateau", "Mons Mouton", "region is on the plateau of this mountain"),
    ("Mons Mouton", "Mons Mouton", "region is on this mountain"),
    ("Nobile Rim 1", "Nobile", "region is on the rim of this crater, not at its centre"),
    ("Nobile Rim 2", "Nobile", "region is on the rim of this crater, not at its centre"),
    ("de Gerlache Rim 2", "de Gerlache", "region is on the rim of this crater, not at its centre"),
    ("Slater Plain", "Slater", "region is on a plain named after this crater"),
)


def _slug(name: str) -> str:
    return "artemis3-" + "-".join(name.lower().replace("de ", "de-").split())


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * MOON_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def build(archive: Path = ARCHIVE, output: Path = OUTPUT) -> dict:
    import geopandas as gpd
    frame = gpd.read_file(f"zip://{ensure_archive(archive)}!MOON_nomenclature_center_pts.shp")
    frame = frame[frame["approval"] == "Adopted by IAU"]
    missions = json.loads(CATALOG.read_text(encoding="utf-8"))
    regions = []
    for name, anchor, relation in REGIONS:
        rows = frame[frame["clean_name"] == anchor]
        if len(rows) != 1:
            raise LookupError(f"IAU feature {anchor!r} not found exactly once in the gazetteer")
        row = rows.iloc[0]
        lat = round(float(row["center_lat"]), 4)
        lon = round((float(row["center_lon"]) + 180.0) % 360.0 - 180.0, 4)
        nearby = []
        for mission in missions:
            site = mission.get("landing_site") or {}
            if site.get("latitude_deg") is None or site.get("longitude_deg") is None:
                continue
            d = _distance_km(lat, lon, site["latitude_deg"], site["longitude_deg"])
            if d <= NEARBY_CATALOG_KM:
                nearby.append({"id": mission["id"], "mission": mission["mission"],
                               "distance_from_anchor_km": round(d, 1)})
        regions.append({
            "id": _slug(name),
            "name": name,
            "kind": "candidate_region",
            "is_landing_point": False,
            "program": "Artemis III",
            "status": "NASA candidate landing region (announced 2024-10-28)",
            "anchor": {
                "iau_name": anchor, "feature_type": row["type"],
                "center_lat_deg": lat, "center_lon_deg": lon,
                "diameter_km": round(float(row["diameter"]), 3),
                "usgs_url": str(row["link"]).replace("http://", "https://"),
            },
            "anchor_relation": relation,
            "coordinate_basis": "iau_feature_centre",
            "catalog_sites_near_anchor": sorted(nearby, key=lambda r: r["distance_from_anchor_km"]),
        })
    payload = {
        "schema": "apolloharness.artemis_iii_regions.v1",
        "label_rule": ("These are regions, not landing points. Show 'Artemis III candidate "
                       "region near <anchor>'; never place a lander or a site marker here."),
        "coordinate_note": ("NASA published the regions as an image only. Coordinates are the "
                            "official IAU centre of the feature that names each region, so a "
                            "rim region lies roughly one crater radius from its anchor."),
        "sources": SOURCES,
        "regions": regions,
    }
    output.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    print(f"{len(result['regions'])} Artemis III candidate regions -> {OUTPUT}")
