"""Identify newly released challenge resources against the data we already use.

Built for event day (see ``docs/EVENT_DAY_PLAN.md``): NASA publishes the
challenge's resource list when the hackathon opens. Download the files into
one folder, then:

    python -m src.acquire.identify_resources ~/Downloads/challenge_resources
    python -m src.acquire.identify_resources FILE_OR_DIR ... --json > report.json

Every file is classified by content (SHA-256), not by name:

* ``KNOWN``        byte-identical to a file the pipeline already uses: nothing to do.
* ``NEW_VERSION``  same filename as a known file, different bytes: a new
  release. Review it before adopting (docs/DATA_SETUP.md, "Updating a dataset").
* ``NEW``          not something we use. The report describes it (raster grid,
  CRS, resolution, whether it covers the south pole; vector feature count and
  fields; table columns) so the team can decide in minutes whether it matters.

Files are only read, never executed. Archives are listed, not extracted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .nasa_products import PRODUCTS
from .usgs_nomenclature import SHA256 as USGS_SHA256, SIZE_BYTES as USGS_SIZE, URL as USGS_URL
from .verify_data import MANIFEST, PROJECT_ROOT, TEXT_FILES

RASTER_SUFFIXES = {".tif", ".tiff", ".img", ".jp2", ".vrt", ".cub", ".nc"}
VECTOR_SUFFIXES = {".shp", ".gpkg", ".geojson", ".kml", ".kmz", ".fgb"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


@dataclass(frozen=True)
class Known:
    name: str
    size: int
    sha256: str
    used_as: str


@dataclass
class Finding:
    path: str
    size_bytes: int
    sha256: str
    status: str
    matches: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def known_files() -> list[Known]:
    """Every external file the pipeline pins, with where we use it."""
    known: dict[str, Known] = {}
    for entry in MANIFEST:
        known[entry.sha256] = Known(Path(entry.path).name, entry.size, entry.sha256, entry.path)
    for product, spec in PRODUCTS.items():
        files = spec.get("files") or {}
        if "sha256" in spec:
            files = {spec["filename"]: (spec["url"], spec["size_bytes"], spec["sha256"])}
        for name, (url, size, sha) in files.items():
            known.setdefault(sha, Known(str(name), int(size), str(sha), f"nasa_products:{product}"))
    for relative in TEXT_FILES:  # committed derived files (catalog, crater subset, ...)
        path = PROJECT_ROOT / relative
        if path.is_file():
            sha = _sha256(path)
            known.setdefault(sha, Known(path.name, path.stat().st_size, sha, relative))
    known.setdefault(USGS_SHA256, Known(Path(USGS_URL).name, USGS_SIZE, USGS_SHA256,
                                        "usgs_nomenclature (IAU gazetteer)"))
    return list(known.values())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _covers_south_pole(crs: Any, bounds: tuple[float, float, float, float]) -> bool | None:
    try:
        from src.compute.terrain import MOON_GEOGRAPHIC, cached_transformer
        x, y = cached_transformer(MOON_GEOGRAPHIC, crs).transform(0.0, -89.999)
    except Exception:  # noqa: BLE001 - foreign CRS (e.g. Earth); answer "unknown"
        return None
    left, bottom, right, top = bounds
    return bool(left <= x <= right and bottom <= y <= top)


def describe_raster(path: Path) -> dict[str, Any]:
    import rasterio
    with rasterio.open(path) as ds:
        bounds = tuple(ds.bounds)
        return {"kind": "raster", "driver": ds.driver, "width": ds.width, "height": ds.height,
                "bands": ds.count, "dtype": ds.dtypes[0], "nodata": ds.nodata,
                "crs": ds.crs.to_string() if ds.crs else None,
                "resolution": [abs(ds.res[0]), abs(ds.res[1])], "bounds": list(bounds),
                "scales": list(ds.scales), "tags": dict(list(ds.tags().items())[:20]),
                "covers_south_pole": _covers_south_pole(ds.crs, bounds) if ds.crs else None}


def describe_vector(path: Path) -> dict[str, Any]:
    import pyogrio
    info = pyogrio.read_info(path)
    return {"kind": "vector", "features": int(info["features"]),
            "geometry_type": info.get("geometry_type"), "crs": info.get("crs"),
            "fields": list(info["fields"])[:40],
            "bounds": list(info["total_bounds"]) if info.get("total_bounds") is not None else None}


def describe_table(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    return {"kind": "table", "columns": header[:60], "rows": rows}


def describe_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(data, dict):
        return {"kind": "json", "top_level_keys": list(data)[:40]}
    return {"kind": "json", "array_length": len(data) if isinstance(data, list) else None}


def describe_archive(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        members = [{"name": m.filename, "size_bytes": m.file_size}
                   for m in archive.infolist() if not m.is_dir()]
    return {"kind": "archive", "members": members[:200], "member_count": len(members),
            "note": "not extracted; extract into its own folder and run this tool on it"}


def describe(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    try:
        if suffix in RASTER_SUFFIXES:
            return describe_raster(path)
        if suffix in VECTOR_SUFFIXES:
            return describe_vector(path)
        if suffix in {".csv", ".tsv"}:
            return describe_table(path)
        if suffix == ".json":
            return describe_json(path)
        if suffix == ".zip":
            return describe_archive(path)
    except Exception as error:  # noqa: BLE001 - report, never crash on an odd file
        return {"kind": "unreadable", "error": f"{type(error).__name__}: {error}"}
    if suffix in {".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".txt"}:
        return {"kind": "document", "note": "read manually and log it in the event-day notes"}
    return {"kind": "other"}


def identify(path: Path, known: list[Known]) -> Finding:
    sha = _sha256(path)
    size = path.stat().st_size
    by_sha = {k.sha256: k for k in known}
    if sha in by_sha:
        return Finding(str(path), size, sha, "KNOWN", by_sha[sha].used_as)
    same_name = [k for k in known if k.name.lower() == path.name.lower()]
    if same_name:
        details = describe(path)
        details["previous"] = {"size_bytes": same_name[0].size, "sha256": same_name[0].sha256}
        return Finding(str(path), size, sha, "NEW_VERSION", same_name[0].used_as, details)
    return Finding(str(path), size, sha, "NEW", None, describe(path))


def _walk(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files += sorted(p for p in target.rglob("*")
                            if p.is_file() and p.name not in SKIP_NAMES
                            and not any(part.startswith(".") for part in p.relative_to(target).parts))
        elif target.is_file():
            files.append(target)
        else:
            raise FileNotFoundError(target)
    return files


def run(targets: list[Path]) -> list[Finding]:
    known = known_files()
    return [identify(path, known) for path in _walk(targets)]


def _summary_line(finding: Finding) -> str:
    d = finding.details
    if finding.status == "KNOWN":
        extra = f"identical to {finding.matches}"
    elif finding.status == "NEW_VERSION":
        extra = f"new release of {finding.matches}: review before adopting"
    elif d.get("kind") == "raster":
        extra = (f"raster {d['width']}x{d['height']} @ {d['resolution'][0]:g}, "
                 f"south pole: {d['covers_south_pole']}")
    elif d.get("kind") == "vector":
        extra = f"vector, {d['features']} features, fields {d['fields'][:6]}"
    elif d.get("kind") == "table":
        extra = f"table, {d['rows']} rows, columns {d['columns'][:6]}"
    else:
        extra = d.get("kind", "")
    return f"{finding.status:<11} {finding.size_bytes:>13,}  {finding.path}  ({extra})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path, help="files or folders to identify")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)
    findings = run(args.paths)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=1, default=str))
    else:
        for finding in findings:
            print(_summary_line(finding))
        counts = {s: sum(f.status == s for f in findings) for s in ("KNOWN", "NEW_VERSION", "NEW")}
        print(f"\n{len(findings)} files: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
