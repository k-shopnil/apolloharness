"""Build the committed IAU south-polar crater subset used to name PSR host craters.

Source: USGS Astrogeology, Gazetteer of Planetary Nomenclature,
``MOON_nomenclature_center_pts.zip`` (IAU-approved names, centre points and
diameters). The full archive is 24 MB; only craters (named and lettered
satellite craters) south of ``--max-lat`` are kept, which is all the PSR
product (80-90 deg S) can need.

    python -m src.acquire.usgs_nomenclature            # download (cached) + rebuild CSV
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
URL = "https://asc-planetarynames-data.s3.us-west-2.amazonaws.com/MOON_nomenclature_center_pts.zip"
SIZE_BYTES = 23_845_070
SHA256 = "8aa0bafc7760ffb6ff2c55fc696ce92d447678c694687501467db7e44c655491"  # 2026-11-05 release
ARCHIVE = PROJECT_ROOT / "cache" / "usgs" / "moon_nomenclature.zip"
OUTPUT = PROJECT_ROOT / "data" / "psr" / "iau_south_polar_craters.csv"
CRATER_TYPES = {"Crater, craters", "Satellite Feature"}  # satellite features are lettered craters
FIELDS = ["name", "feature_type", "center_lat_deg", "center_lon_deg", "diameter_km", "usgs_url"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_archive(path: Path = ARCHIVE, *, allow_new_release: bool = False) -> Path:
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        request = urllib.request.Request(URL, headers={"User-Agent": "ApolloHarness/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out, 1 << 20)
        partial.replace(path)
    actual = _sha256(path)
    if actual != SHA256 and not allow_new_release:
        raise ValueError(f"{path.name}: sha256 {actual} differs from the pinned release "
                         f"{SHA256}. USGS updates the gazetteer; re-run with "
                         "--allow-new-release and review the CSV diff before committing.")
    return path


def build_subset(archive: Path, output: Path = OUTPUT, *, max_lat_deg: float = -70.0) -> int:
    import geopandas as gpd
    frame = gpd.read_file(f"zip://{archive}!MOON_nomenclature_center_pts.shp")
    frame = frame[frame["type"].isin(CRATER_TYPES) & (frame["approval"] == "Adopted by IAU")
                  & (frame["center_lat"] <= max_lat_deg) & (frame["diameter"] > 0)]
    rows = sorted(({"name": r["clean_name"], "feature_type": r["type"],
                    "center_lat_deg": round(float(r["center_lat"]), 4),
                    "center_lon_deg": round(((float(r["center_lon"]) + 180.0) % 360.0) - 180.0, 4),
                    "diameter_km": round(float(r["diameter"]), 3),
                    "usgs_url": str(r["link"]).replace("http://", "https://")}
                   for _, r in frame.iterrows()), key=lambda row: row["name"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-lat", type=float, default=-70.0)
    parser.add_argument("--allow-new-release", action="store_true")
    args = parser.parse_args(argv)
    count = build_subset(ensure_archive(allow_new_release=args.allow_new_release),
                         max_lat_deg=args.max_lat)
    print(f"{OUTPUT.relative_to(PROJECT_ROOT)}: {count} IAU craters south of {args.max_lat} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
