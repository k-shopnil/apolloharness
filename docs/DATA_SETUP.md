# Data setup: every external file, where it comes from, where it goes

This page lists every external file the pipeline reads, its authoritative
source, its exact size and SHA-256, where it must sit in the repository, and
how to get it. One command checks all of it:

```sh
python -m src.acquire.verify_data
```

The complete scientific source inventory, processing lineage and human-review
status are maintained in [DATA_SOURCES.md](DATA_SOURCES.md) and
[`data/validation/data_provenance.json`](../data/validation/data_provenance.json).

It exits `0` when every required file is present and byte-exact, and `1`
otherwise, printing the fix command next to each problem. Use it after
cloning, before deploying, and in CI.

## Quick start (new team member)

```sh
# 1. Git LFS, once per machine (https://git-lfs.com)
brew install git-lfs            # macOS;  Ubuntu: sudo apt install git-lfs;  Windows: bundled with Git for Windows
git lfs install

# 2. Clone and fetch the large files (~720 MB)
git clone https://github.com/k-shopnil/apolloharness.git
cd apolloharness
git lfs pull

# 3. Python environment (Python 3.12)
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt

# 4. Verify, then run the tests
python -m src.acquire.verify_data
python -m pytest -q tests
```

Steps 1–4 give you everything except the optional 531 MB global DEM
(see [Optional: global terrain](#optional-global-terrain-531-mb)).

## Resolution and identity rules

`data/missions.json` is the canonical mission catalog used by compute modules.
`offline_fixtures/missions.json` is the canonical offline fixture location;
it may add explicit offline-analysis fields, but its mission IDs must match the
canonical catalog. The CI `data-guard` job and
`python -m src.acquire.verify_data` enforce that ID identity. The old
`demo_fixtures/missions.json` path is accepted only as a compatibility fallback
when the new fixture path is absent.

Large scientific products resolve to the committed paths listed in the
manifest in `src/acquire/verify_data.py`. A real Git LFS object, or a verified
download from its authoritative NASA/NAIF URL, is required; an LFS pointer is
reported as unavailable. Local development uses `git lfs pull` or
`verify_data --fetch`, while CI disables automatic LFS checkout, restores the
cached LFS objects, and runs `git lfs pull` before tests. The manifest's
expected size and SHA-256 establish dataset identity; derived tiles are
validated by their recorded metadata and may be rebuilt.

### No Git LFS, or LFS quota exhausted

GitHub's free LFS bandwidth is about 1 GB per month, and one full pull is
about 720 MB, so the repository's quota can run out. Every LFS file is a copy
of a public NASA/NAIF product, so you can download them from the original
publishers instead:

```sh
python -m src.acquire.verify_data --fetch
```

This downloads each missing or invalid file, checks its size and SHA-256, and
links it into place. Downloads go to `cache/` (git-ignored) and are
symlinked into `data/`, so `git status` will show them as type changes;
do not commit those. On Windows, symlinks need Developer Mode. Otherwise
copy the files from `cache/` to the paths below.

## What a file that "didn't download" looks like

Without `git lfs pull`, each large file is a ~130-byte text **pointer**
starting with `version https://git-lfs.github.com/spec/v1`. The code
recognizes pointers (`src/compute/datafiles.py`) and treats them as missing:

| Product | Behaviour without the real file |
|---|---|
| SPICE kernels, polar DEM | `DataNotInstalledError: ... is a Git LFS pointer, not the data ... run git lfs pull` |
| Annual illumination, PSR polygons | API field `status: "product_not_installed"` with a `fix` hint; the rest of the response is still served |
| Site tiles, global DEM | Terrain falls back to the next source; `horizon_model` says which was used |

`verify_data` reports these files as `LFS_POINTER`. Tests that need the
real data are skipped ("run `git lfs pull`") or fail with the message above.

## File inventory

Paths are relative to the repository root. "LFS" means the file is in the
repository via Git LFS (`git lfs pull`). The fix command restores it from
the original publisher.

### Required

| Path | Size | Source | Get it | Used for |
|---|---|---|---|---|
| `data/spice/naif0012.tls` | 5 KB | [NAIF LSK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls) | Git (text) | UTC ↔ ephemeris time (leap seconds) |
| `data/spice/pck00010.tpc` | 126 KB | [NAIF PCK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00010.tpc) | Git (text) | Body radii and constants |
| `data/spice/moon_080317.tf` | 21 KB | [NAIF FK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf) | Git (text) | `MOON_ME` / `MOON_PA` frame definitions |
| `data/spice/moon_pa_de421_1900-2050.bpc` | 1.8 MB | [NAIF PCK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de421_1900-2050.bpc) | LFS · `nasa_products spice_kernels` | High-precision lunar orientation |
| `data/spice/de430.bsp` | 119.7 MB | [NAIF SPK](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de430.bsp) | LFS · `nasa_products spice_kernels` | Sun/Earth/Moon positions |
| `data/lola/LDEM_80S_80MPP_ADJ.TIF` | 189.2 MB | [NASA PGDA product 90](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF) | LFS · `nasa_products lola_dem_80s_80m` | 80 m terrain and horizons, 80–90°S |
| `data/illumination/AVGVISIB_85S_060M_201608.TIF` | 34.0 MB | [NASA PGDA product 69](https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF) | LFS · `nasa_products annual_illumination_85s_60m` | Long-term sunlight, 85–90°S; validation truth |
| `data/illumination/AVGVISIB_75S_120M_201608.TIF` | 83.1 MB | [NASA PGDA product 69](https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_75S_120M_201608.TIF) | LFS · `nasa_products annual_illumination_75s_120m` | Long-term sunlight, 75–90°S |
| `data/psr/LPSR_80S_20MPP_ADJ.SHP` `.SHX` `.DBF` `.PRJ` | 287.6 MB total | [NASA PGDA product 90](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/) | LFS · `nasa_products psr_shapefile` | 506,349 permanently shadowed regions |
| `data/lola/tiles/*.tif` (11 tiles) | ~1.2 MB each | Derived from the global DEM | LFS · `python -m src.compute.global_terrain` | Real terrain at catalog sites north of 80°S |

Exact sizes and SHA-256 values for every file are in
[`src/acquire/verify_data.py`](../src/acquire/verify_data.py) (`MANIFEST`).
`python -m src.acquire.verify_data --json` prints them as JSON.

### Committed as plain text (no download)

| Path | What it is | Regenerate with |
|---|---|---|
| `data/missions.json` | Sourced mission catalog (16 records) | hand-curated, each fact has a source |
| `data/space_weather/donki_mission_windows.json` | NASA DONKI SEP/CME events per mission analysis window (context only) | `python -m src.acquire.space_weather` (needs `NASA_API_KEY`) |
| `data/artemis_iii_regions.json` | NASA's nine Artemis III candidate regions, anchored to IAU features | `python -m src.acquire.artemis_regions` |
| `data/psr/iau_south_polar_craters.csv` | 176 IAU craters south of 70°S, used to name PSR host craters | `python -m src.acquire.usgs_nomenclature` |
| `data/lola/tiles/index.json` | Tile centres and extents | `python -m src.compute.global_terrain` |
| `data/precomputed/tracks/*.json` | 29.5-day Sun/Earth tracks for 9 sites | `python -m src.compute.precompute_tracks` |
| `offline_fixtures/` | API-identical payloads for offline use (`site_geometry/`, `site_sensitivity/`, `missions.json`) | `python -m src.compute.api_payloads` |
| `data/validation/annual_illumination_validation.json` | Validation results vs NASA | `python -m src.ml.validation` |
| `data/validation/earth_visibility_validation.json` | Earth line-of-sight validation vs NASA's Earth visibility map | `python -m src.ml.earth_validation` |
| `data/validation/horizons/*.txt`, `horizons_crosscheck.json` | Cached JPL Horizons responses and the cross-check result (13 sites × Sun/Earth) | `python -m src.ml.horizons_crosscheck --refresh` |

### Optional: global terrain (531 MB)

| Path | Size | Source | Get it |
|---|---|---|---|
| `cache/nasa/pds/ldem_64.img` | 530.8 MB | [NASA PDS Geosciences, LOLA GDR](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img) | `python -m src.acquire.nasa_products lola_gdr_global_64ppd` |
| `cache/nasa/pds/ldem_64.lbl` | 5 KB | [same directory](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.lbl) | same command |

It is **not** in Git (too large). It is needed only for custom coordinates
north of 80°S that are more than ~55 km from a catalog site, and to rebuild
the site tiles. Without it, those points use a smooth-sphere horizon,
reported as `horizon_model: "spherical_horizon"` in every result, never
silently. Install it on the machine that serves the API. Manual `curl`
steps are in the
[integration guide](TEAM_INTEGRATION_GUIDE.md#downloading-the-global-lola-dem-ldem_64).

### Optional: Earth visibility truth map (25 MB, validation only)

| Path | Size | Source | Get it |
|---|---|---|---|
| `data/illumination/AVGVISIB_85S_060M_201608_EARTH.TIF` | 24.9 MB | [NASA PGDA product 69](https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF) | `python -m src.acquire.nasa_products earth_visibility_85s_60m` |

Not in Git and not read by the API. It is the independent truth for the
Earth line-of-sight validation (`python -m src.ml.earth_validation`). The
committed result, `data/validation/earth_visibility_validation.json`, is
what the tests read, so you only need this file to re-run the validation.
`verify_data --include-optional` checks it.

### Rebuild-only source (not needed to run)

| Path | Size | Source | Get it |
|---|---|---|---|
| `cache/usgs/moon_nomenclature.zip` | 23.8 MB | [USGS Gazetteer of Planetary Nomenclature](https://asc-planetarynames-data.s3.us-west-2.amazonaws.com/MOON_nomenclature_center_pts.zip) | `python -m src.acquire.usgs_nomenclature` (downloads, verifies the pinned SHA-256, rebuilds the crater CSV) |

## NASA API key (optional, `.env`)

Only `python -m src.acquire.space_weather` (rebuilding the committed DONKI
space-weather file) uses a NASA API key. Nothing else, including the API
server, needs one at runtime.

```sh
cp .env.example .env      # .env is git-ignored
# get a free key: https://api.nasa.gov/#signUp, then set NASA_API_KEY=... in .env
```

Without a key the script falls back to `DEMO_KEY` (30 requests/hour; one
rebuild uses about 20). Never commit `.env`, never give the key a `VITE_`
prefix (the frontend bundle is public), and never paste it into issues or
PRs. Details: [DATA_SOURCES.md §9](DATA_SOURCES.md#9-nasa-api-portal-apinasagov-and-the-api-key).

## Built automatically on first use (git-ignored)

You never download these. They are rebuilt when missing or stale, and any
failure falls back to the slower path.

| Path | Built by | Why |
|---|---|---|
| `cache/derived/LPSR_80S_20MPP_ADJ.fgb` (236 MB) | `site_evaluation.warm_up()` or the first PSR query (~5 s) | Spatially indexed PSR copy: 0.05 s per lookup instead of 0.3 s |
| `cache/derived/*` far-field DEM | first horizon query | 4× block-averaged DEM for 20–100 km rays |
| `*.metadata.json` beside downloads | `nasa_products` | Provenance: source URL, size, SHA-256, verification time |

## Deployment checklist (API server)

1. `git lfs pull` (or `verify_data --fetch`).
2. `python -m src.acquire.nasa_products lola_gdr_global_64ppd` (global terrain).
3. `python -m src.acquire.verify_data`. It must print `all required data present and verified`.
4. Call `site_evaluation.warm_up()` at startup. It loads kernels, builds the
   PSR index (~5 s the first time) and the far-field DEM cache.
5. Docker: copy or mount `data/`, `offline_fixtures/` and `cache/`. Mount
   `cache/` as a volume so derived files survive restarts, and run
   `git lfs pull` **before** `docker build`. `COPY` copies pointer files as-is.

## Updating a dataset

Upstream products are versioned by filename (`..._201608.TIF`, `de430`), so
a new release is a new file, never a silent change. To check a batch of
downloaded files against everything the pipeline already pins (by SHA-256,
so renamed copies are still recognised):

```sh
python -m src.acquire.identify_resources FOLDER_OR_FILES   # KNOWN / NEW_VERSION / NEW
```

The event-day procedure built on it is in [EVENT_DAY_PLAN.md](EVENT_DAY_PLAN.md).
To adopt one:

1. Add the product and its checksums to `src/acquire/nasa_products.py` and
   `src/acquire/verify_data.py`.
2. Regenerate the derived outputs listed above.
3. Re-run the validations (`python -m src.ml.validation --product NEW.TIF`,
   `python -m src.ml.earth_validation --product NEW.TIF`) and the tests.
4. Record the change in [SCIENTIFIC_BASIS.md](SCIENTIFIC_BASIS.md).

The gazetteer is the exception: USGS updates it in place, so its SHA-256 is
pinned and a new release is refused until it is reviewed
(`--allow-new-release`).
