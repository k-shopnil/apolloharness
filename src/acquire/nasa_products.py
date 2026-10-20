"""Acquisition registry for the real NASA south-polar Issue #2 products.

Large downloads are cached under cache/nasa/pgda/ and linked into ignored
``data/`` locations. The repository contains no raster or PSR fixture substitute.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .safe import fetch_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PRODUCTS: dict[str, dict[str, object]] = {
    "lola_dem_80s_80m": {
        "url": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF",
        "filename": "LDEM_80S_80MPP_ADJ.TIF",
        "destination": PROJECT_ROOT / "data/lola/LDEM_80S_80MPP_ADJ.TIF",
        "size_bytes": 189_158_392,
        "sha256": "82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a",
        "product": "NASA GSFC PGDA product 90 LDEM, 80–90°S, 80 m/pixel",
    },
    "annual_illumination_85s_60m": {
        "url": "https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF",
        "filename": "AVGVISIB_85S_060M_201608.TIF",
        "destination": PROJECT_ROOT / "data/illumination/AVGVISIB_85S_060M_201608.TIF",
        "size_bytes": 33_994_464,
        "sha256": "ccf67d4f39e0a970c111196da7d6551ffcf50d075470b93067fb3904c0b05806",
        "product": "NASA PGDA product 69 average solar illumination, 85–90°S, 60 m/pixel, 201608 release; TIFF scale 0.00004 converts int16 to fraction",
    },
    "annual_illumination_75s_120m": {
        "url": "https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_75S_120M_201608.TIF",
        "filename": "AVGVISIB_75S_120M_201608.TIF",
        "destination": PROJECT_ROOT / "data/illumination/AVGVISIB_75S_120M_201608.TIF",
        "size_bytes": 83_052_039,
        "sha256": "d539467f16ccc5f51b6a904af6be5d16c9b2f194afe619b9f1f81841d9fec0bb",
        "product": "NASA PGDA product 69 average solar illumination, 75–90°S, 120 m/pixel, 201608 release; TIFF scale 0.00004 converts int16 to fraction",
    },
    "psr_shapefile": {
        "files": {
            "LPSR_80S_20MPP_ADJ.SHP": ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.SHP", 161_396_036, "fe11dbc98b4054ff2f72510955b33f775f6f5b8e0a6f5ac4a03dfd8de5625606"),
            "LPSR_80S_20MPP_ADJ.SHX": ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.SHX", 4_050_892, "dc9e84bb280793c69ed5e4fca7422f798111efb3d629a2430804e2559aba73af"),
            "LPSR_80S_20MPP_ADJ.DBF": ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.DBF", 122_030_239, ""),
            "LPSR_80S_20MPP_ADJ.PRJ": ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.PRJ", 368, ""),
        },
        "destination": PROJECT_ROOT / "data/psr/LPSR_80S_20MPP_ADJ.SHP",
        "product": "NASA GSFC PGDA product 90 full south-polar PSR vector, 506,349 features, 20 m map grid",
    },
}


def _link_cached_file(cache_file: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() and destination.resolve() == cache_file.resolve():
        return destination
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    destination.symlink_to(cache_file.resolve())
    return destination


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_product_provenance(product_name: str, filename: str, cache_file: Path,
                              source_url: str, product_description: str) -> Path:
    """Write a local verification record without changing the science raster."""
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, timezone.utc)
    record = {
        "status": "CACHED",
        "publisher": "NASA GSFC PGDA",
        "product_key": product_name,
        "product": product_description,
        "filename": filename,
        "source_url": source_url,
        "local_path": str(cache_file.resolve()),
        "size_bytes": cache_file.stat().st_size,
        "sha256": _sha256(cache_file),
        "local_file_mtime_utc": file_mtime.isoformat().replace("+00:00", "Z"),
        "last_verified_utc": checked_at,
        "freshness_note": "Historical science product; timestamp records local verification, not upstream update time.",
    }
    metadata_path = cache_file.with_name(cache_file.name + ".metadata.json")
    temporary = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(metadata_path)
    return metadata_path


def get_product_status(name: str) -> dict[str, object]:
    """Return installed/verified status records for a registered NASA product."""
    if name not in PRODUCTS:
        raise KeyError(f"Unknown NASA product {name!r}; choose from {sorted(PRODUCTS)}")
    spec = PRODUCTS[name]
    files = spec.get("files")
    entries = []
    if files:
        expected = [(filename, info[1], info[2]) for filename, info in files.items()]
    else:
        expected = [(str(spec["filename"]), int(spec["size_bytes"]), str(spec.get("sha256", "")))]
    integrity_states = []
    for filename, expected_size, expected_sha in expected:
        path = PROJECT_ROOT / "cache/nasa/pgda" / filename
        record_path = path.with_name(path.name + ".metadata.json")
        entry: dict[str, object] = {
            "filename": filename,
            "expected_size_bytes": expected_size,
            "path": str(path),
            "status": "UNAVAILABLE",
        }
        if path.is_file() and path.stat().st_size == expected_size:
            entry["status"] = "CACHED"
            entry["size_bytes"] = path.stat().st_size
            integrity = "UNVERIFIED"
            if expected_sha:
                integrity = "VERIFIED" if _sha256(path) == expected_sha else "INVALID"
            if record_path.is_file():
                try:
                    provenance = json.loads(record_path.read_text(encoding="utf-8"))
                    entry["provenance"] = provenance
                    try:
                        verified_at = datetime.fromisoformat(
                            provenance["last_verified_utc"].replace("Z", "+00:00"))
                        entry["verification_age_seconds"] = max(
                            0.0, (datetime.now(timezone.utc) - verified_at).total_seconds())
                    except (KeyError, TypeError, ValueError):
                        entry["provenance_status"] = "INVALID"
                    recorded_mtime = provenance.get("local_file_mtime_utc")
                    current_mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
                    if (not expected_sha and provenance.get("size_bytes") == path.stat().st_size
                            and recorded_mtime == current_mtime
                            and provenance.get("sha256") == _sha256(path)):
                        integrity = "VERIFIED"
                except (OSError, json.JSONDecodeError):
                    entry["provenance_status"] = "INVALID"
            else:
                entry["provenance_status"] = "UNAVAILABLE"
            if integrity == "INVALID":
                entry["status"] = "INVALID"
            entry["integrity_status"] = integrity
            integrity_states.append(integrity)
        elif path.is_file():
            entry["status"] = "INVALID"
            entry["size_bytes"] = path.stat().st_size
            entry["integrity_status"] = "INVALID"
            integrity_states.append("INVALID")
        else:
            integrity_states.append("UNAVAILABLE")
        entries.append(entry)
    statuses = [entry["status"] for entry in entries]
    overall = "CACHED" if all(status == "CACHED" for status in statuses) else (
        "INVALID" if "INVALID" in statuses else "PARTIAL" if "CACHED" in statuses else "UNAVAILABLE"
    )
    integrity = "VERIFIED" if integrity_states and all(value == "VERIFIED" for value in integrity_states) else (
        "INVALID" if "INVALID" in integrity_states else "UNVERIFIED"
    )
    return {"product_key": name, "product": spec["product"], "status": overall,
            "integrity_status": integrity, "upstream_updated_utc": None,
            "upstream_freshness_status": "UNKNOWN", "files": entries}


def acquire_product(name: str) -> Path:
    """Fetch or reuse one registered product via online → cache → fixture logic.

    Product binaries are never placed in the mission demo fixture directory.
    A missing network resource and missing cache raises ``SafeFetchError``.
    """
    if name not in PRODUCTS:
        raise KeyError(f"Unknown NASA product {name!r}; choose from {sorted(PRODUCTS)}")
    spec = PRODUCTS[name]
    if name == "psr_shapefile":
        result = None
        for filename, (url, _size, expected_sha) in spec["files"].items():
            cache_file = PROJECT_ROOT / "cache/nasa/pgda" / filename
            if not cache_file.is_file() or cache_file.stat().st_size != _size:
                cache_file = fetch_file(url, cache_name=f"nasa/pgda/{filename}",
                                        fixture_name=f"nasa-products/{filename}")
            if cache_file.resolve() != (PROJECT_ROOT / "cache/nasa/pgda" / filename).resolve():
                raise IOError(f"Scientific product fixtures are not supported: {filename}")
            if cache_file.stat().st_size != _size:
                raise IOError(f"Unexpected size for {filename}: {cache_file.stat().st_size} != {_size}")
            if expected_sha and _sha256(cache_file) != expected_sha:
                raise IOError(f"SHA-256 mismatch for {filename}")
            _write_product_provenance(name, filename, cache_file, url, str(spec["product"]))
            result = _link_cached_file(cache_file, PROJECT_ROOT / "data/psr" / filename)
        return PROJECT_ROOT / spec["destination"]
    cache_file = PROJECT_ROOT / "cache/nasa/pgda" / str(spec["filename"])
    if not cache_file.is_file() or cache_file.stat().st_size != spec["size_bytes"]:
        cache_file = fetch_file(str(spec["url"]), cache_name=f"nasa/pgda/{spec['filename']}",
                                fixture_name=f"nasa-products/{spec['filename']}")
    if cache_file.resolve() != (PROJECT_ROOT / "cache/nasa/pgda" / str(spec["filename"])).resolve():
        raise IOError(f"Scientific product fixtures are not supported: {spec['filename']}")
    if cache_file.stat().st_size != spec["size_bytes"]:
        raise IOError(f"Unexpected size for {spec['filename']}: "
                      f"{cache_file.stat().st_size} != {spec['size_bytes']}")
    expected_sha = spec.get("sha256")
    if expected_sha and _sha256(cache_file) != expected_sha:
        raise IOError(f"SHA-256 mismatch for {spec['filename']}")
    _write_product_provenance(name, str(spec["filename"]), cache_file,
                              str(spec["url"]), str(spec["product"]))
    return _link_cached_file(cache_file, Path(spec["destination"]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=sorted(PRODUCTS))
    parser.add_argument("--status", action="store_true", help="report cached product and provenance status")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(get_product_status(args.product), indent=2))
    else:
        print(acquire_product(args.product))
