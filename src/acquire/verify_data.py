"""Check (and optionally fetch) every external data file the pipeline needs.

    python -m src.acquire.verify_data              # check all files (sizes + SHA-256)
    python -m src.acquire.verify_data --quick      # sizes and LFS pointers only (~instant)
    python -m src.acquire.verify_data --fetch      # download missing files from NASA/NAIF/USGS

Exit code 0 when every *required* file is valid, 1 otherwise, so the command
works as a CI gate or a deployment preflight. See docs/DATA_SETUP.md.

Each file has an authoritative upstream source. Git LFS is a convenience copy:
``--fetch`` restores files from the original publishers when LFS is not
installed or the repository's LFS bandwidth quota is exhausted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.compute.datafiles import is_lfs_pointer

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DataFile:
    path: str              # relative to the project root
    size: int
    sha256: str
    group: str
    required: bool         # False: optional capability (the code degrades gracefully)
    source: str            # authoritative upstream URL or the generating command
    fix: str               # command that restores the file
    exact_bytes: bool = True  # False for derived files a rebuild may re-encode


def _kernel(name: str, size: int, sha: str, url: str) -> DataFile:
    return DataFile(f"data/spice/{name}", size, sha, "SPICE kernels", True, url,
                    "git lfs pull  |  python -m src.acquire.nasa_products spice_kernels")


_NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
_PGDA = "https://pgda.gsfc.nasa.gov/data/"
_TILE_FIX = "git lfs pull  |  python -m src.compute.global_terrain  (needs the global DEM)"

MANIFEST: tuple[DataFile, ...] = (
    _kernel("naif0012.tls", 5_257, "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b", _NAIF + "lsk/naif0012.tls"),
    _kernel("pck00010.tpc", 126_143, "59468328349aa730d18bf1f8d7e86efe6e40b75dfb921908f99321b3a7a701d2", _NAIF + "pck/pck00010.tpc"),
    _kernel("moon_080317.tf", 21_437, "78732477b96f9863e7b0d65bcee3c22b8707ca5ed0db56d1173319cb2e8c7993", _NAIF + "fk/satellites/moon_080317.tf"),
    _kernel("moon_pa_de421_1900-2050.bpc", 1_770_496, "656f90616403d75a75f0cd6c8830fc5b44f8cb4facb5ccb8915e752b397520cf", _NAIF + "pck/moon_pa_de421_1900-2050.bpc"),
    _kernel("de430.bsp", 119_741_440, "6e1b277c5f07135a84950604b83e56b736be696a7f3560bcddb1d4aeb944fca1", _NAIF + "spk/planets/de430.bsp"),
    DataFile("data/lola/LDEM_80S_80MPP_ADJ.TIF", 189_158_392,
             "82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a", "Polar terrain (80 m)", True,
             _PGDA + "LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF",
             "git lfs pull  |  python -m src.acquire.nasa_products lola_dem_80s_80m"),
    DataFile("data/illumination/AVGVISIB_85S_060M_201608.TIF", 33_994_464,
             "ccf67d4f39e0a970c111196da7d6551ffcf50d075470b93067fb3904c0b05806", "Annual illumination", True,
             _PGDA + "MoonIllumination/AVGVISIB_85S_060M_201608.TIF",
             "git lfs pull  |  python -m src.acquire.nasa_products annual_illumination_85s_60m"),
    DataFile("data/illumination/AVGVISIB_75S_120M_201608.TIF", 83_052_039,
             "d539467f16ccc5f51b6a904af6be5d16c9b2f194afe619b9f1f81841d9fec0bb", "Annual illumination", True,
             _PGDA + "MoonIllumination/AVGVISIB_75S_120M_201608.TIF",
             "git lfs pull  |  python -m src.acquire.nasa_products annual_illumination_75s_120m"),
    *(DataFile(f"data/psr/LPSR_80S_20MPP_ADJ.{ext}", size, sha, "PSR polygons", True,
               _PGDA + f"LOLA_20mpp/LPSR_80S_20MPP_ADJ.{ext}",
               "git lfs pull  |  python -m src.acquire.nasa_products psr_shapefile")
      for ext, size, sha in (
          ("SHP", 161_396_036, "fe11dbc98b4054ff2f72510955b33f775f6f5b8e0a6f5ac4a03dfd8de5625606"),
          ("SHX", 4_050_892, "dc9e84bb280793c69ed5e4fca7422f798111efb3d629a2430804e2559aba73af"),
          ("DBF", 122_030_239, "e0a2304ab2f02b63fbd9c6019643b93ddc9c2826619d1518521a104d47a7aa00"),
          ("PRJ", 368, "793b80952f23fbff90f48f9e13868b6b7fc5dc07ba0b1633b124c3db52462854"))),
    *(DataFile(f"data/lola/tiles/{name}.tif", size, sha, "Site terrain tiles", True,
               "derived: python -m src.compute.global_terrain", _TILE_FIX, exact_bytes=False)
      for name, size, sha in (
          ("anchor-apollo-11", 1_212_236, "603545dfd69dfa5b31f43875036f3dcc0b140a457d94306ecdd42b241b3c45c5"),
          ("anchor-apollo-17", 1_214_309, "aff8ecc5f91bd6e97bbdb5e24c7cb1ffe30eb42fd5d10b63c5c217c23839d481"),
          ("anchor-chandrayaan-3", 1_356_612, "4f6e3d917df45198df8bd6206d0b953933b370c5b3316913ba950a1b36684807"),
          ("anchor-change-4", 1_212_205, "34324ceabd149b9f7a89246a6d3fef6df30669e35c2eff216cc4fbda9cd0997e"),
          ("anchor-slim", 1_324_070, "55bfa71c29071b3f245d3dcbb8f77fa9df5b95d2554f29fe68c279ed7b8dffd5"),
          ("clps-cp11-im3", 1_109_739, "f4b7bdeec044c8cfa7827d99d7b1822ca61d1c153ff0d518162cbc86566957c5"),
          ("clps-cp12-draper", 1_244_971, "99acd95ab1ed35ccaa0a427f251f09d8c150bf7c6462892ffc79dce6a35bf2a6"),
          ("clps-cs3-blue-ghost-2", 1_324_679, "6f007b227e0b3d96e57eb2518ef57ec44377593242d04ad176c983f2422d0ba4"),
          ("clps-to19d-blue-ghost-1", 1_088_619, "dc079d002715a07cc811f16f03bc7ffd7568591ba5c8cef08f0cdc397c3544a2"),
          ("clps-to2-ab-peregrine-1", 1_134_754, "846adc428ebabcb740fbd93b530cb32ad56524d92f3842f1959ebcc33480f11c"),
          ("clps-to2-im-im1", 1_347_527, "f7841300eadce277b576febbf931a11dc67bb947a56140021229b017b11e3b66"))),
    DataFile("data/illumination/AVGVISIB_85S_060M_201608_EARTH.TIF", 24_862_958,
             "d71dc5adfff653e0e924e0a4cbf03795b996caa30b4ace3d5843a70a5ab2f3d2",
             "Validation truth (optional)", False,
             _PGDA + "MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF",
             "python -m src.acquire.nasa_products earth_visibility_85s_60m"),
    DataFile("cache/nasa/pds/ldem_64.img", 530_841_600,
             "1c4958699d4cffd7e777d51421b6044bba300aa0bef286a544309efb082cdbd6", "Global terrain (optional)", False,
             "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img",
             "python -m src.acquire.nasa_products lola_gdr_global_64ppd"),
    DataFile("cache/nasa/pds/ldem_64.lbl", 5_128,
             "4e7a94c76c716a147b21ccf07669d004246b0d1b017b7d63d50befaa1a34142d", "Global terrain (optional)", False,
             "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.lbl",
             "python -m src.acquire.nasa_products lola_gdr_global_64ppd"),
)

# Committed as plain Git text (no LFS): checked for presence and parseability only.
TEXT_FILES = ("data/missions.json", "data/lola/tiles/index.json", "data/psr/iau_south_polar_craters.csv",
              "data/precomputed/tracks/index.json", "offline_fixtures/missions.json",
              "data/artemis_iii_regions.json", "data/space_weather/donki_mission_windows.json")
CATALOG = "data/missions.json"
OFFLINE_CATALOG_CANDIDATES = ("offline_fixtures/missions.json", "demo_fixtures/missions.json")

# Fetch plan: registry product per group (tiles are rebuilt, not downloaded).
_PRODUCT_FOR = {
    "data/spice/": "spice_kernels", "data/lola/LDEM_80S": "lola_dem_80s_80m",
    "data/illumination/AVGVISIB_85S": "annual_illumination_85s_60m",
    "data/illumination/AVGVISIB_75S": "annual_illumination_75s_120m",
    "data/illumination/AVGVISIB_85S_060M_201608_EARTH": "earth_visibility_85s_60m",
    "data/psr/LPSR": "psr_shapefile", "cache/nasa/pds/ldem_64": "lola_gdr_global_64ppd",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check(entry: DataFile, *, quick: bool = False) -> str:
    """OK, MISSING, LFS_POINTER, WRONG_SIZE, WRONG_CHECKSUM, or REBUILT (derived, valid)."""
    path = PROJECT_ROOT / entry.path
    if not path.exists():
        return "MISSING"
    if is_lfs_pointer(path):
        return "LFS_POINTER"
    if path.stat().st_size != entry.size and entry.exact_bytes:
        return "WRONG_SIZE"
    if quick:
        return "OK" if path.stat().st_size == entry.size else "REBUILT"
    if _sha256(path) != entry.sha256:
        return "REBUILT" if not entry.exact_bytes else "WRONG_CHECKSUM"
    return "OK"


def check_text(relative: str) -> str:
    path = PROJECT_ROOT / relative
    if not path.is_file():
        return "MISSING"
    if is_lfs_pointer(path):
        return "LFS_POINTER"
    try:
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        else:
            path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return "UNREADABLE"
    return "OK"


def catalog_ids(relative: str) -> set[str]:
    """Return mission IDs from a catalog JSON file."""
    data = json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("missions", [])
    return {item["id"] for item in items}


def check_catalog_alignment() -> tuple[str, str | None]:
    """Check that the canonical catalog and the available offline fixture agree on IDs."""
    fixture = next((path for path in OFFLINE_CATALOG_CANDIDATES
                    if (PROJECT_ROOT / path).is_file()), None)
    if fixture is None:
        return "MISSING", None
    try:
        return ("OK" if catalog_ids(CATALOG) == catalog_ids(fixture) else "ID_MISMATCH"), fixture
    except (OSError, KeyError, TypeError, ValueError):
        return "UNREADABLE", fixture


def _fetch(entries: list[DataFile]) -> None:
    from .nasa_products import acquire_product
    products = []
    for entry in entries:
        product = next((p for prefix, p in sorted(_PRODUCT_FOR.items(), key=lambda kv: -len(kv[0]))
                        if entry.path.startswith(prefix)), None)
        if product and product not in products:
            products.append(product)
    for product in products:
        print(f"fetching {product} ...", flush=True)
        acquire_product(product)
    if any(e.group == "Site terrain tiles" for e in entries):
        from src.compute.global_terrain import GLOBAL_DEM, main as build_tiles
        if GLOBAL_DEM.is_file():
            print("rebuilding site terrain tiles ...", flush=True)
            build_tiles([])
        else:
            print("site tiles: install the global DEM first "
                  "(python -m src.acquire.nasa_products lola_gdr_global_64ppd)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify external data files (docs/DATA_SETUP.md)")
    parser.add_argument("--quick", action="store_true", help="skip SHA-256 (sizes and LFS pointers only)")
    parser.add_argument("--fetch", action="store_true", help="download missing/invalid files from upstream")
    parser.add_argument("--include-optional", action="store_true",
                        help="with --fetch, also download optional files (531 MB global DEM)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    results = [(entry, check(entry, quick=args.quick)) for entry in MANIFEST]
    bad = [e for e, status in results if status not in ("OK", "REBUILT")]
    if args.fetch:
        wanted = [e for e in bad if e.required or args.include_optional]
        if wanted:
            _fetch(wanted)
            results = [(entry, check(entry, quick=args.quick)) for entry in MANIFEST]
    texts = [(relative, check_text(relative)) for relative in TEXT_FILES]
    catalog_status, catalog_fixture = check_catalog_alignment()

    failed_required = [e for e, s in results if e.required and s not in ("OK", "REBUILT")]
    failed_required += [r for r, s in texts if s != "OK"]
    if args.json:
        print(json.dumps({"ok": not failed_required and catalog_status == "OK",
                          "files": [{"path": e.path, "group": e.group, "required": e.required,
                                     "status": s, "size_bytes": e.size, "sha256": e.sha256,
                                     "source": e.source, "fix": e.fix} for e, s in results]
                          + [{"path": r, "group": "Committed text", "required": True, "status": s}
                             for r, s in texts],
                          "catalog_alignment": {"canonical": CATALOG, "fixture": catalog_fixture,
                                                "status": catalog_status}}, indent=2))
        return 0 if not failed_required and catalog_status == "OK" else 1

    group = None
    for entry, status in results:
        if entry.group != group:
            group = entry.group
            print(f"\n{group}")
        mark = "ok " if status in ("OK", "REBUILT") else ("-- " if not entry.required else "XX ")
        note = "" if status == "OK" else f"  [{status}]  fix: {entry.fix}"
        print(f"  {mark}{entry.path} ({entry.size / 1e6:.1f} MB){note}")
    print("\nCommitted text files")
    for relative, status in texts:
        print(f"  {'ok ' if status == 'OK' else 'XX '}{relative}"
              + ("" if status == "OK" else f"  [{status}]  fix: git checkout -- {relative}"))
    print("\nOffline catalog alignment")
    print(f"  {'ok ' if catalog_status == 'OK' else 'XX '}canonical IDs vs "
          f"{catalog_fixture or 'offline_fixtures/missions.json'} [{catalog_status}]")
    if any(s == "LFS_POINTER" for _, s in results):
        print("\nLFS pointer files found: install Git LFS (https://git-lfs.com), then run "
              "`git lfs install && git lfs pull`. If LFS bandwidth is exhausted, run "
              "`python -m src.acquire.verify_data --fetch` to download from NASA/NAIF instead.")
    optional_missing = [e for e, s in results if not e.required and s != "OK"]
    if optional_missing:
        print("\nOptional files missing: terrain outside 80-90 S falls back to committed site tiles,"
              " then to a smooth-sphere horizon (flagged in every result as horizon_model).")
    failed_checks = len(failed_required) + (catalog_status != "OK")
    print("\nRESULT:", "all required data present and verified" if not failed_checks
          else f"{failed_checks} required check(s) need attention")
    return 0 if not failed_checks else 1


if __name__ == "__main__":
    sys.exit(main())
