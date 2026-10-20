"""Acquisition registry for the real NASA south-polar Issue #2 products.

Large downloads are cached under cache/nasa/pgda/ and linked into ignored
``data/`` locations. The repository contains no raster or PSR fixture substitute.
"""
from __future__ import annotations

import hashlib
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
            "LPSR_80S_20MPP_ADJ.SHP": ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.SHP", 161_396_036, "4b20d73123f0b0f99c1e744d64ba23ee4dd29ee5f18e9d64831b702cd4e58023"),
            "LPSR_80S_20MPP_ADJ.SHX": ("https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LPSR_80S_20MPP_ADJ.SHX", 4_050_892, "f58161b50c72339d6a78120f9c3f825e4b87f6112df98ca38358a92fa19273d0"),
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
            cache_file = fetch_file(url, cache_name=f"nasa/pgda/{filename}",
                                    fixture_name=f"nasa-products/{filename}")
            if cache_file.stat().st_size != _size:
                raise IOError(f"Unexpected size for {filename}: {cache_file.stat().st_size} != {_size}")
            if expected_sha and _sha256(cache_file) != expected_sha:
                raise IOError(f"SHA-256 mismatch for {filename}")
            result = _link_cached_file(cache_file, PROJECT_ROOT / "data/psr" / filename)
        return PROJECT_ROOT / spec["destination"]
    cache_file = fetch_file(str(spec["url"]), cache_name=f"nasa/pgda/{spec['filename']}",
                            fixture_name=f"nasa-products/{spec['filename']}")
    if cache_file.stat().st_size != spec["size_bytes"]:
        raise IOError(f"Unexpected size for {spec['filename']}: "
                      f"{cache_file.stat().st_size} != {spec['size_bytes']}")
    expected_sha = spec.get("sha256")
    if expected_sha and _sha256(cache_file) != expected_sha:
        raise IOError(f"SHA-256 mismatch for {spec['filename']}")
    return _link_cached_file(cache_file, Path(spec["destination"]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=sorted(PRODUCTS))
    args = parser.parse_args()
    print(acquire_product(args.product))
