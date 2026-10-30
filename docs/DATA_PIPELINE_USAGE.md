# Issue #2 data pipeline usage contract

This document defines the Issue #2 outputs that the backend and frontend work
can consume. It documents integration only; it does not define or implement
backend routes, application scoring, or UI behavior.

## Files and responsibilities

- `data/missions.json`: source-curated catalog of eight CLPS missions and five
  reference anchors (see `category`).
- `demo_fixtures/missions.json`: deterministic offline mission catalog. It has
  mission metadata and provenance. Each fixture record includes a `demo_analysis`
  object with stable metric keys set to `null` and an explicit status explaining
  the missing scientific products; these are unavailable values, not zeroes or
  fabricated analysis results.
- `src/acquire/safe.py`: `fetch_json`, `fetch_file`, and
  `copy_fixture_to_cache`, using online → cache → fixture fallback.
- `src/compute/spice_engine.py`: SPICE hourly geometry and geometric Earth LOS
  summary, including current-UTC ephemeris geometry.
- `src/compute/terrain.py`: LOLA DEM horizon profile and azimuth lookup;
  bilinear elevation at any coordinate and a fast vectorized horizon mask.
- `src/compute/site_evaluation.py`: one-call custom-site evaluation and
  launch-date (Date A vs Date B) comparison.
- `src/compute/precompute_tracks.py`: offline scrubber tracks written to
  `data/precomputed/tracks/`.

Issue #8 functions, schemas and per-team usage are documented in
[TEAM_INTEGRATION_GUIDE.md](TEAM_INTEGRATION_GUIDE.md).
- `src/compute/illumination_mission.py`: tactical mission-window sunlight.
- `src/compute/illumination_annual.py`: annual/secular polar illumination
  raster extraction.
- `src/compute/proximity.py`: metric distance to PSR boundaries.
- `src/ml/features.py`: stable feature records and leakage/split audit helpers;
  it does not train or load a model.

The JSON files use the existing Issue #2 field names to avoid breaking current
consumers: `id`, `task_order`, and nested `landing_site`. `coordinate_type`
qualifies the nested coordinate and must be carried through serialization.
Coordinates are not all confirmed landing fixes. In particular, `site_reference`,
`landing_region_reference`, `target_region_reference`, and `basin_reference`
are visualization/analysis references only. The source links on each record
support mission identity, task, destination, and payload metadata; the current
catalog does not provide independent provenance for every numeric reference
coordinate or every target date. Treat those values as provisional until the
coordinate/time source is recorded.

## Conventions and units

| Field or result | Convention |
|---|---|
| Latitude | Degrees, −90 to +90; south is negative |
| Longitude | Degrees, −180 to +180; east is positive |
| Time | ISO 8601 UTC; include `Z` or an explicit offset |
| Mission/map frame | `MOON_ME` coordinates for NASA PGDA ME/DE421 rasters; ME→PA orientation transform at each SPICE epoch |
| SPICE geometry frame | `MOON_PA`; SPICE ET conversion uses the loaded LSK |
| Elevation/azimuth | Degrees; azimuth is clockwise from lunar north (0° north, 90° east) |
| Illumination | Percent, 0–100 |
| Communications | Percent uptime and hours; geometric visibility means spherical-horizon LOS |
| PSR distance | Meters, with kilometers as a convenience field; computed in `MOON_SPS` |
| Terrain DEM | Projected lunar coordinates with meter axes; dataset frame/datum must be checked |

A year-only `target_date` is not an exact landing date. A reference coordinate
must never be displayed as an actual landing location.

## Public compute functions

Run calls from the repository root after installing `requirements.txt` and
placing the required kernels/products in their documented locations. Callers
may use `load_kernels()` once around batches of geometry work and call
`unload_kernels()` when finished. Tactical analysis manages kernels by default;
pass `manage_kernels=False` when an application already manages the SPICE
session. The kernel loader does not unload kernels that another caller had
already loaded.

### Hourly geometry and communications

```python
from dataclasses import asdict
from src.compute.spice_engine import (
    load_kernels, unload_kernels,
    calculate_hourly_geometry, summarize_communications,
)

load_kernels()
try:
    hours = calculate_hourly_geometry(
        latitude_deg=-84.79,
        longitude_deg=29.20,
        start_utc="2026-10-20T00:00:00Z",
        hours=24,
    )
    geometry_rows = [asdict(row) for row in hours]
    comms = summarize_communications(hours).to_dict()
finally:
    unload_kernels()
```

Each geometry row has `utc`, `earth_elevation_deg`, `earth_azimuth_deg`,
`sun_elevation_deg`, `sun_azimuth_deg`, and `earth_visible`. The communication
summary has `visibility_model: "spherical_horizon_geometric_los"`,
`communications_uptime_percent`, `longest_blackout_hours`, `total_hours`,
`visible_hours`, and half-open UTC `blackout_intervals` (`start_utc`, `end_utc`).
The older `.uptime_percent` attribute is retained as a compatibility alias.

For the current UTC instant, `calculate_current_geometry(latitude_deg,
longitude_deg)` returns the same `HourlyGeometry` fields and stamps the result
with the exact UTC calculation epoch. It uses the installed SPICE kernels and
is an ephemeris-based prediction, not a live surface observation or telemetry
feed. Callers must load the kernels first and preserve the returned `utc` with
the result.

Serialized result shape (nulls below are schema placeholders, not observations):

```json
{
  "visibility_model": "spherical_horizon_geometric_los",
  "communications_uptime_percent": null,
  "longest_blackout_hours": null,
  "total_hours": null,
  "visible_hours": null,
  "blackout_intervals": []
}
```

This is geometric LOS to Earth's center above a spherical horizon. It is not
terrain-masked communications visibility and does not account for the finite
Earth disc, antenna elevation limits, relay networks, or link budgets. Issue #3
may combine it with separately calculated terrain horizons, but should label
that derived result distinctly.

### LOLA terrain horizon

```python
from src.compute.terrain import extract_horizon_mask

horizon = extract_horizon_mask(
    "data/lola/LDEM_80S_80MPP_ADJ.TIF",
    latitude_deg=-84.79,
    longitude_deg=29.20,
    max_distance_m=20_000,
    radial_step_m=100,
    azimuth_step_deg=1,
)
terrain_elevation_deg = horizon.elevation_at(azimuth_deg=45.0)
```

`HorizonMask.azimuth_deg` and `elevation_deg` are aligned arrays; lookup accepts
north-clockwise azimuth and interpolates across 0/360 degrees. The radial
sampler uses the DEM's declared CRS, but its geographic-to-projected transform
uses a 1,737,400 m spherical lunar radius. Verify that the selected GeoTIFF's
frame, projection, axis convention, pixel registration, and vertical units
match before interpreting results. The loader uses a single DEM opened for one
mask extraction; cache/reuse the resulting small `HorizonMask` for repeated
hourly calculations rather than reopening the raster per hour.

NASA's PGDA [south-pole LOLA products](https://pgda.gsfc.nasa.gov/products/90)
include projected COG DEMs and LPSR shapefiles. The `LDEM_80S_80MPP_ADJ.TIF`
product is listed at 181 MB; finer products can be multiple gigabytes. Download
the relevant DEM and keep it at `data/lola/` (ignored by Git). For the alternate
5 m mosaic, see the [South Pole LOLA DEM Mosaic](https://pgda.gsfc.nasa.gov/products/81).

### Tactical mission illumination

```python
from src.compute.illumination_mission import calculate_mission_illumination

mission_light = calculate_mission_illumination(
    latitude_deg=-84.79,
    longitude_deg=29.20,
    mission_start_utc="2026-10-20T00:00:00Z",
    duration_days=10,
    horizon_mask=horizon,
)
```

`calculate_mission_illumination` is the stable public name; the earlier
`calculate_tactical_illumination` remains available. Results use
`analysis_type: "tactical_mission_window"`,
`tactical_sunlight_percent`, `illuminated_hours`, `total_hours`,
`longest_darkness_hours`, `darkness_intervals` (also exposed as
`blackout_intervals`), and `hourly`. Each hourly record contains UTC, Sun
azimuth/elevation in degrees, local terrain horizon in degrees, and
`illuminated`. The criterion is `sun_elevation_deg > terrain_horizon_deg`,
not just above zero degrees. Do not reuse this mission-window percentage as
annual illumination.

### Annual/strategic illumination

```python
from src.compute.illumination_annual import calculate_annual_illumination

annual = calculate_annual_illumination(
    latitude_deg=-89.54,
    longitude_deg=0.0,
    raster_path="data/illumination/AVGVISIB_85S_060M_201608.TIF",
)
```

The result has `analysis_type: "annual_strategic_illumination"`,
`annual_sunlight_percent`, coordinates, source raster path, and CRS. The
compatibility alias `annual_illumination` remains. This function samples an
already-produced annual raster; it does not synthesize a secular product from
tactical SPICE samples. Use an annual solar illumination product in the 80°S to
90°S polar stereographic coverage. NASA PGDA's [lunar polar illumination
catalog](https://pgda.gsfc.nasa.gov/products/69) lists average-solar products
and documents their long-term averaging. Preserve the product label/version
and scaling metadata alongside the raster. Product files are local and ignored
by Git; use the acquisition registry to download them.

### PSR proximity

```python
from src.compute.proximity import calculate_psr_distance

psr = calculate_psr_distance(
    latitude_deg=-89.54,
    longitude_deg=0.0,
    dataset_path="data/psr/LPSR_80S_20MPP_ADJ.SHP",
)
```

`calculate_psr_distance` (alias `nearest_psr`) returns `distance_m`,
`distance_km`, `nearest_psr`, source path, and analysis CRS. It reprojects the
source vector to the module's lunar south-polar stereographic CRS before
measuring distance to polygon boundaries; it never subtracts latitude and
longitude values. NASA's [LOLA south-pole product 90](https://pgda.gsfc.nasa.gov/products/90)
provides `LPSR_80S_20MPP_ADJ_1km2.SHP` (about 20 MB, PSRs over 1 km²) and the
full `LPSR_80S_20MPP_ADJ.SHP` (about 154 MB). Download and unpack all sidecar
files into `data/psr/`; pass the `.shp` path or convert to GeoPackage. This
module requires the vector file to declare a CRS. The selected 1 km² product
omits smaller PSRs, so it can overstate nearest-boundary distance.

## Acquisition, offline behavior, and scientific status

Run `.venv/bin/python -m src.acquire.nasa_products --help` to see registered
products, then use a product key such as
`.venv/bin/python -m src.acquire.nasa_products lola_dem_80s_80m`. Downloads are
cached under `cache/nasa/pgda/` and linked into ignored `data/` directories.
After byte-size and registered-hash checks (where an upstream expected hash is
available), acquisition writes an ignored per-file `*.metadata.json` record
with the NASA source URL, product key, local SHA-256, file mtime, and local verification time. Existing valid cache files are reused
without downloading them again. Inspect presence and integrity with
`.venv/bin/python -m src.acquire.nasa_products lola_dem_80s_80m --status`.
The status response reports local verification age and leaves
`upstream_freshness_status` as `UNKNOWN` unless the source provides a usable
update timestamp. `last_verified_utc` describes when this checkout checked its
local file; it is not an upstream NASA update timestamp. These LOLA/illumination datasets are
historical products, not real-time surface measurements. The CLPS manifest is
source-curated from NASA pages; no stable NASA real-time CLPS telemetry API is
currently integrated. Refreshing mission status requires an authoritative
source update and must not infer new facts from an arbitrary page scrape.
The registry covers the product-90 80–90°S LOLA DEM, product-69 85–90°S and
75–90°S annual illumination TIFFs, and the full product-90 PSR shapefile. Use
the 75–90°S illumination coverage for Mons Mouton. See
[SCIENTIFIC_BASIS.md](SCIENTIFIC_BASIS.md) for source semantics, CRS/frame
definitions, units, limitations, and reproducibility requirements. The 85–90°S
illumination raster does not cover Mons Mouton; use the registered 75–90°S
product there.

JSON mission metadata supports online → cache → committed fixture fallback.
Scientific binaries have no fabricated fixture fallback. Fixture outputs are
for software and offline testing and are NOT scientific results. Missing
science inputs must be reported unavailable. Keep source product identity,
kernel versions, coordinate frame, UTC window, input checksums, and sampling
parameters with reproducible output.

## Mission object and downstream mapping

A source object currently looks like:

```json
{
  "id": "clps-to20a-griffin-1",
  "task_order": "TO20A",
  "provider": "Astrobotic",
  "mission": "Griffin Mission 1",
  "target_site": "Mons Mouton / Nobile Region",
  "region": "south_pole",
  "status": "planned",
  "target_date": null,
  "landing_site": {
    "latitude_deg": -84.79,
    "longitude_deg": 29.2,
    "coordinate_type": "site_reference"
  },
  "payloads": [],
  "sources": []
}
```

The excerpt omits payload/source details and is illustrative of field shape. The
actual record in `data/missions.json` is authoritative for the current catalog.
Consumers should map rather than rename in place:

| Pipeline field | Consumer-facing concept |
|---|---|
| `id` | `mission_id` |
| `task_order` | `clps_task` |
| `landing_site.latitude_deg` | latitude in degrees |
| `landing_site.longitude_deg` | east-positive longitude in degrees |
| `landing_site.coordinate_type` | coordinate provenance/type discriminator |
| `landing_ellipse_km` | target ellipse dimensions when known; null means unknown |
| `payloads[].purpose` | payload purpose/category tags |
| `sources[]` | provenance references for mission/task/site/payload metadata |

Do not coerce a `null` target date to an exact date or a non-actual
`coordinate_type` to an actual landing fix.

## Issue #3 backend integration (contract only)

- A mission-list handler can read `data/missions.json` and return the catalog;
  for offline development, call `fetch_json` with the mission JSON URL, cache
  key, and `fixture_name="missions.json"`.
- A site-scoring handler can join results by mission `id` and expose
  `tactical_sunlight_percent`, `annual_sunlight_percent`,
  `communications_uptime_percent`, `longest_blackout_hours`, and `distance_m`
  (or map it to the consumer's `psr_distance_m` field).
- A communications handler can serialize each hourly geometry row and the
  geometric visibility intervals. Include `visibility_model` so downstream
  consumers do not mistake spherical-horizon LOS for terrain-aware contact.
- A backend can serialize dictionaries directly. For SPICE dataclasses use
  `dataclasses.asdict`; use `CommunicationsSummary.to_dict()` for the stable
  summary schema.
- Missing datasets raise `FileNotFoundError`; represent the corresponding
  analysis as unavailable/null in API output rather than substituting a
  synthetic scientific number.

No `/api/v1/...` endpoints or project scoring are implemented by Issue #2.

## Physics-informed ML contract (not trained)

The deterministic SPICE, terrain, annual-raster, communications, and PSR
calculations remain authoritative. `src/ml/features.py` only combines already
computed products into a schema-versioned candidate-site feature record. It
preserves unavailable numbers as `null`, exposes data-quality fractions and
source metadata separately, rejects benchmark locations by default, and labels
the ML result `NOT_TRAINED`. It does not create scores, recommendations, or
surrogate outputs.

The stable feature schema is `apollo-lunar-site-v1`; numeric model features
exclude target/label, physics score, rank, risk score, and benchmark expected
values. Features include coordinate, terrain elevation/slope/roughness,
tactical and annual illumination, time-window Sun statistics, geometric Earth
visibility, and PSR distance. Temporal window bounds and per-source status and
provenance remain metadata, not silently imputed predictors. Quality fractions
and overall completeness are kept outside the physics score. Unsupported
features stay `null`; there is no zero-fill path.

The module provides deterministic 5-degree latitude/longitude block IDs,
checks that train/validation/test block sets do not overlap, and by default can
reject adjacent blocks across partitions with a one-cell buffer (a conservative
5-degree screening guard, not a geodesic distance buffer). It also offers an
optional strict chronological split check and an audit report for missingness,
duplicate rows/coordinates, sample count, and groups. These are guardrails, not evidence
that a dataset is suitable for training. An approved training corpus must be
generated from real, version-pinned science inputs at independent candidate
sites. The Shackleton rim and Mons Mouton benchmarks (and a sourced deep-crater
site once specified) must remain evaluation-only, including a spatial buffer
around each location.

`audit_dataset` fails closed by default unless each training row has real or
derived-real status for terrain, tactical illumination, annual illumination,
communications, PSR, and SPICE; it also rejects benchmark coordinates, missing
spatial groups, target leakage, and null targets. The emitted completeness
percentage is a six-source availability indicator with sample-validity
fractions retained alongside it; it is not a scientific suitability score.

No training target is currently defined. A future target could be a documented
physics-derived multi-objective utility, but it must be generated independently
from model inputs and clearly labeled `PHYSICS_DERIVED_TARGET`; target-derived
scores cannot enter the feature matrix. There is no trained model or evaluation
metric: this repository currently has no installed scikit-learn, XGBoost,
LightGBM, or CatBoost, and there are no legitimate independent generated
physics samples. Do not train on the mission metadata rows, temporary
synthetic test fixtures, or the held-out benchmark coordinates. Install and
pin an estimator only after a leakage-audited corpus and training protocol are
approved; split first, then fit imputation/scaling on training data only.

If a compatible model is later introduced, downstream output should retain
separate `physics`, `ml`, and `data_quality` objects. ML status must be
`UNAVAILABLE`, `INSUFFICIENT_DATA`, `FEATURE_MISMATCH`, or
`OUT_OF_DISTRIBUTION` instead of returning a fabricated score. An ML estimate
must never overwrite deterministic outputs. Explainability, confidence,
calibration, regression/ranking metrics, and comparison with a simple baseline
are required before reporting model performance. No surrogate is currently
justified; any future surrogate must be checked against new deterministic
physics runs in independent spatial regions before candidate screening.

## Issue #4 frontend integration (contract only)

The frontend should consume backend/API mission objects and analysis results.
It should display mission name, task, provider, status, target site, payloads,
landing ellipse, and coordinates with their `coordinate_type`. For a reference
coordinate, label it as a target/site reference rather than showing “landed”.
Display tactical and annual sunlight as separate metrics with separate labels;
show communications uptime as geometric unless the backend adds a documented
terrain-aware model; show PSR distance with units and the PSR dataset/version.
The frontend should not independently calculate SPICE geometry, terrain
horizon, annual sunlight, or projected PSR distance.

## Issue #6 scientific validation hooks

The benchmark locations and expected ranges are references for validation,
not values to seed into fixtures. Compare outputs only with matching dataset
versions, resolution, CRS/frame, observer height, coordinate convention,
mission-window start/end, sampling cadence, and boundary definition. The
Shackleton annual benchmark depends on a specified long-term illumination
product; Mons Mouton tactical illumination depends on the exact date window and
LOLA horizon method. The NASA product-69 85–90°S raster has been sampled at the
brief's Shackleton reference coordinate and returned 11.26%, which differs from
the approximate 89.4% reference; see [SCIENTIFIC_BASIS.md](SCIENTIFIC_BASIS.md)
for the file checksum and unresolved comparison. This raster does not cover
Mons Mouton. The real product-90 DEM has been acquired and produces complete
terrain rays at both benchmark coordinates; its embedded CRS metadata differs
from the NASA product-page frame description, so those diagnostic horizons are
provisional. The PSR vector is installed (506,349 polygons), but ten source
geometries are invalid and the strict proximity API rejects the full dataset;
no nearest-PSR distance is reported. Tactical sunlight cannot be compared to
the brief without its active-window UTC start/duration, and the deep-crater
comparison remains pending. A deep-crater negative
control must use a sourced site and real DEM, then verify zero terrain-visible
hours before a downstream hard gate is validated.

## Data acquisition, kernels, environment, and tests

Install the pinned Python dependencies from `requirements.txt` in Python 3.12.
The geometry engine requires these files under `data/spice/`:

- `naif0012.tls`: leap seconds / UTC conversion.
- `pck00010.tpc`: lunar constants and radii.
- `moon_080317.tf`: lunar frame definitions.
- `moon_pa_de421_1900-2050.bpc`: Moon PA orientation.
- `de430.bsp`: solar-system ephemerides.

The large binary kernels are Git-ignored. Obtain the matching kernels from the
NAIF generic-kernel archive; do not silently substitute different kernel
versions. Small text kernels are source inputs. The engine uses `MOON_PA`,
east-positive longitude, and a planetocentric coordinate direction intersected
with the reference ellipsoid. Mission map coordinates use MOON_ME for PGDA
product-90 DEM/PSR and are transformed to MOON_PA at the requested SPICE epoch.
The product-90 DEM GeoTIFF's WKT labels its projection IAU Moon-2015, although
the PGDA product page describes the grid as MOON_ME/DE421; see the scientific
basis note. The sampler currently uses ME coordinates per the product page.
The product-69 raster has a Moon2000 CRS label but no explicit DE421 frame
realization in its page metadata. Earth LOS currently uses Earth's center and a
spherical horizon; it omits the finite Earth disc and terrain mask.

`safe.fetch_json(url, cache_name=..., fixture_name=..., timeout=...)` and
`safe.fetch_file(...)` use the configured `cache/` directory and fall back to
`demo_fixtures/`. Fixtures contain mission metadata and explicit null analysis
fields, not sourced scientific raster/vector products. If every tier fails, `SafeFetchError` is raised. Cache
contents and large datasets are local and ignored by Git.

For example, retrieve the catalog from the feature branch with an offline
fixture fallback:

```python
from src.acquire.safe import fetch_json

missions = fetch_json(
    "https://raw.githubusercontent.com/k-shopnil/apolloharness/feature/data-pipeline/data/missions.json",
    cache_name="missions.json",
    fixture_name="missions.json",
    timeout=5,
)
```

Run checks from the repository root:

```sh
python -m compileall src tests
python -m json.tool data/missions.json >/dev/null
python -m json.tool demo_fixtures/missions.json >/dev/null
python -m unittest discover -s tests -v
python -m pytest -q tests  # requires pytest in the environment
```

The tests use small, generated temporary geospatial fixtures for API and CRS
contract checks. Those temporary geometries are not lunar science data and are
not used as benchmark evidence. Real annual illumination and PSR analysis
requires installing real products at the paths above.
