<div align="center">

<img src="./harness_mark_white_affiliation.png" alt="HarnessApollo Header" width="700" />

  <br /><br />

  <a href="https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/">
    <img src="https://img.shields.io/badge/NASA_Space_Apps-2026-0B3D91?style=flat-square&logo=nasa&logoColor=white" alt="NASA Space Apps 2026" />
  </a>


  <a href="https://www.spaceappschallenge.org/2026/find-a-team/chhayanautical/">
    <img src="https://img.shields.io/badge/Team-Chhayanautical-18181B?style=flat-square&logo=target&logoColor=white" alt="Team Chhayanautical" />
  </a>

  <a href="https://chhayanautical.web.app">
    <img src="https://img.shields.io/badge/Website-chhayanautical.web.app-2563EB?style=flat-square&logo=googlechrome&logoColor=white" alt="Website" />
  </a>

  <a href="https://youtu.be/aGuu1ngPULE?si=Tqs-8-tjcWd688sj">
    <img src="https://img.shields.io/badge/NASA%20Challenge%20Pitch-Watch%20Now-FF0000?style=flat-square&logo=youtube&logoColor=" alt="Official Pitch" />
  </a>

  <a href="mailto:chhayanautical@gmail.com">
    <img src="https://img.shields.io/badge/Contact-Email-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email" />
  </a>
    <img src="https://img.shields.io/badge/License-MIT-22C55E?style=flat-square" alt="MIT License" />
  </a>

  <br /><br />

  <p align="center">
    <strong>Next-Generation Lunar Mission Intelligence & Environmental Analysis</strong><br>
    <em>Engineered by <strong>Team Chhayanautical</strong> for NASA Space Apps Challenge 2026</em>
  </p>

</div>

---

## The Mission

**HarnessApollo** is an environmental intelligence initiative developed for the **NASA Space Apps Challenge 2026** (*[Lunar Landing Site Navigator](https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/)*).

As commercial missions venture into uncharted lunar territories, navigating extreme polar environments demands transforming raw planetary science into intuitive, high-fidelity mission intelligence.

HarnessApollo bridges planetary data archives with next-generation mission planning interfaces to evaluate lunar surface viability and environmental dynamics.

---

## Official NASA Space Apps Pitch

Experience our official preliminary project presentation submitted for the **NASA Space Apps Challenge 2026**.


<div align="center">

  <a
    href="https://www.youtube.com/watch?v=aGuu1ngPULE"
    target="_blank"
    style="position: relative; display: inline-block; width: 700px; max-width: 100%;" >
    <img
      src="https://i.ibb.co/zhgHb7yk/ytthumbrepo.png"
      alt="HarnessApollo NASA Space Apps Pitch"
      width="700"
      style="width: 100%; display: block;"
    />
  </a>

</div>

---


## Status & Disclosure

> **Under Active Development**

## Planetary data pipeline

Python compute modules live in `src/compute/`; the mission catalog is
`data/missions.json`, and the offline mission catalog is
`offline_fixtures/missions.json`. The current catalog contains sixteen sourced
records: eleven CLPS missions (`category: "clps"`) and five historical and
international reference anchors (`category: "reference_anchor"`: Apollo 11,
Apollo 17, Chandrayaan-3, Chang'e 4, SLIM). Coordinates are references with an explicit `coordinate_type`; a
target or region center must not be interpreted as an achieved landing point.
Dates containing only a year are target years, not exact dates.

### Sources, datasets, and coordinate assumptions

The required SPICE kernels are `data/spice/naif0012.tls` (UTC/leap seconds),
`pck00010.tpc` (body constants), `moon_080317.tf` (lunar frame definitions),
`moon_pa_de421_1900-2050.bpc` (Moon PA orientation), and `de430.bsp` (solar
system ephemerides). All five are in the repository (the two binary kernels via
Git LFS) and are byte-identical to NAIF's generic kernels; every external file,
its source, size, SHA-256 and location is listed in
[docs/DATA_SETUP.md](docs/DATA_SETUP.md), and `python -m src.acquire.verify_data`
checks them all.
The complete source inventory and citation audit is in
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), with structured provenance in
[`data/validation/data_provenance.json`](data/validation/data_provenance.json).
SPICE calculations use `MOON_PA`, east-positive
longitude, planetocentric latitude converted through the Moon radii, and
geometric (no aberration correction) line of sight. Sun and Earth visibility
are tested against the LOLA terrain horizon at the site (`horizon_model:
"lola_terrain_mask"`), falling back to a spherical horizon only where no terrain
is installed, and saying so in the output. They do not include lander antenna
constraints or relay availability.

Terrain analysis uses NASA GSFC PGDA product 90's 80–90°S LOLA DEM at 80 m/pixel,
which covers the Mons Mouton and Shackleton benchmark coordinates.
Outside 80–90°S, terrain comes from the global LOLA GDR `LDEM_64` (~474
m/pixel) through small committed per-site tiles in `data/lola/tiles/`. To
evaluate arbitrary coordinates outside 80–90°S, install the optional 531 MB
global DEM with `python -m src.acquire.nasa_products lola_gdr_global_64ppd`
(manual `curl` and checksum steps:
[docs/TEAM_INTEGRATION_GUIDE.md](docs/TEAM_INTEGRATION_GUIDE.md#downloading-the-global-lola-dem-ldem_64)). The registry
`data/lola/LDEM_80S_80MPP_ADJ.TIF` is in the repository via Git LFS; without
LFS, `python -m src.acquire.verify_data --fetch` downloads it from NASA PGDA into
`cache/nasa/pgda/` and links it there. Product 90
uses south-polar stereographic coordinates in meters referenced to the
MOON_ME/DE421 realization and a 1,737,400 m reference sphere. Product 81 is a
finer 5 m/pixel mosaic covering only 87–90°S, so it does not cover Mons Mouton.
The acquired product-90 TIFF's WKT uses an IAU Moon-2015 ocentric CRS label;
see [SCIENTIFIC_BASIS.md](docs/SCIENTIFIC_BASIS.md) for the metadata discrepancy
and its effect on interpretation.
The horizon output depends on observer height, radial step, and DEM resolution;
incomplete rays remain unavailable rather than implying open sky.

Annual illumination is a distinct strategic product. The registry downloads
NASA PGDA product 69's 85–90°S, 60 m/pixel and 75–90°S, 120 m/pixel GeoTIFFs to
`data/illumination/`. NASA describes these maps as average solar illumination
over hourly samples spanning about one 18.6-year lunar nutation cycle. The
TIFF's scale metadata (0.00004) converts stored int16 values to fraction of
time illuminated; the API converts that to percent. These are average products,
not mission-window predictions. Use the broader 75–90°S product for Mons
Mouton's annual figure comes from the 60 m product too: its square raster
footprint reaches north of 85°S. The 120 m product is used where only it covers
a point.

PSR proximity uses NASA PGDA product 90's full south-polar PSR shapefile. The
four shapefile components are in `data/psr/` via Git LFS (or fetched from NASA
PGDA with `verify_data --fetch`). Distances are calculated in meters
after projection to a south-polar stereographic CRS using the ME reference
sphere, not from latitude/longitude differences.
The acquired NASA vector contains 506,349 polygons, including ten invalid
source geometries. The legacy strict `calculate_psr_distance` rejects the full
source; the interactive `nearest_psr_within` (used by the API) reads only the
polygons near the site, reports `inside_psr`, the PSR ID, area, the nearest
PSR of at least 1 km², and the IAU-named host crater where one exists.

### Offline operation and reproducibility

`src/acquire/safe.py` implements online → `cache/` → committed fixture fallback
for JSON and file downloads. The committed mission JSON fixture keeps the
mission catalog available offline; compute modules that depend on binary
ephemerides still require the local SPICE kernels. NASA science rasters and PSR
vectors are not replaced by fixture values. Fixture outputs are for software
and offline testing and are NOT scientific results. Analysis output includes
its analysis type and source path. For
reproducibility, record the exact source product/version, kernel filenames,
observer coordinate convention, DEM sampling parameters, and mission start and
duration with each result.

Install pinned dependencies with `python -m pip install -r requirements.txt`.
For tests, install `requirements-dev.txt` (adds pytest) and run `python -m pytest -q tests`.
The engine is validated against NASA's independent illumination map (held-out
test R² 0.951, MAE 1.45 pp), NASA's Earth visibility map (R² 0.953, MAE 1.40 pp)
and JPL Horizons sky positions (≤ 0.006°): see [docs/ML_VALIDATION_REPORT.md](docs/ML_VALIDATION_REPORT.md).
Run an offline geometry example from the repository root with:

```sh
python -m src.compute.spice_engine
```

LOLA tactical illumination can be called from Python using
`extract_horizon_mask(...)` and `calculate_mission_illumination(...)`;
annual illumination and PSR distance are exposed as
`calculate_annual_illumination(...)` and `calculate_psr_distance(...)`.
Earlier aliases remain available. The compute API raises a
clear `FileNotFoundError` when its scientific input product is not installed.
Run the included checks with `.venv/bin/python -m unittest discover -s tests -v`
and use `.venv/bin/python -m compileall src` for a syntax check. No benchmark
datasets are committed. The scientific basis document records an attempted
real raster sample and its discrepancy with the brief's reference value;
benchmark values must not be claimed until all matching products and time
windows are identified and run.

For downstream API and frontend field mappings, public function signatures,
units, examples, dataset paths, and validation limitations, see
[docs/DATA_PIPELINE_USAGE.md](docs/DATA_PIPELINE_USAGE.md). For the Issue #8
temporal features (custom coordinates, Sun/Earth countdowns, timeline-scrubber
tracks, launch-slip comparison) with per-team instructions, see
[docs/TEAM_INTEGRATION_GUIDE.md](docs/TEAM_INTEGRATION_GUIDE.md).
Current-epoch SPICE geometry is a kernel-based prediction, not a live lunar
measurement. Registered NASA products expose local cache/integrity status and
verification timestamps; these timestamps do not claim that NASA updated the
underlying historical product. The pipeline does not consume live CLPS
telemetry.

---

## Phase 2 Active Integration Sprint (Issue #8)

> [!IMPORTANT]
> **STALENESS & LIFECYCLE MARKER:**
> * **Anchor Merge Commit:** [`7cb8a02`](https://github.com/k-shopnil/apolloharness/commit/7cb8a02) (*Merge pull request #9: Issue #8 data pipeline*)
> * **Milestone Baseline:** Issue #8 Challenge-Alignment Foundation (NASA-Validated Engine & Grounded Fleet)
> * **Last Updated:** `2026-11-02`
> * **Sprint Status:** **ACTIVE INTEGRATION (Awaiting Backend & Frontend PRs)**
> 
> *Notice for team members: If `git log -n 1 --oneline` shows a commit newer than `7cb8a02` on `main` (such as a merged backend or frontend PR), the checklist and instructions below may be **PARTIALLY OR FULLY STALE**. Check recent PRs before executing pending tasks.*

### What Has Been Accomplished & Merged (at `7cb8a02`)

* **Horizon Event Root-Finder & Operational Countdowns:** `src/compute/spice_engine.py` calculates Sun and Earth rise/set to within 1 s against the 360° LOLA skyline (`find_horizon_events`), producing dynamic hours and `"4d 18h"` countdowns. Added finite disc visible fractions (`disk_visible_fraction`) and CSPICE thread-safety locks.
* **Multi-Day Precomputations:** 29.5-day precomputed hourly tracks generated for 9 missions in `data/precomputed/tracks/` to power the 60 FPS scrubber without runtime backend latency.
* **Arbitrary Coordinates & Global Lunar Terrain:** Bilinear interpolation on polar DEM (`LDEM_80S_80MPP_ADJ.TIF`) with automatic fallback to global LOLA `LDEM_64`. Pre-cut per-site tiles committed via Git LFS. Custom coordinates evaluate in 0.12–0.30 s warm; regional screening runs at ~13 ms/point. PSR proximity inside cold traps fixed (`nearest_psr_within`).
* **Manifest Grounding (Zero Invented Data):** Fictional mock missions (`ls-1`, `PRIME-2`) purged. Added 5 primary-source reference anchors (Apollo 11, Apollo 17, Chandrayaan-3, Chang'e 4, SLIM) and 11 verified CLPS missions with payload summaries in `data/missions.json`. Draper CP-12 marked `terminated`.
* **NASA PGDA Product 69 Validation:** Spatial dev/test validation achieved held-out test $R^2 = 0.951$, MAE = 1.45 pp, resolving the Shackleton crater illumination discrepancy ([docs/ML_VALIDATION_REPORT.md](docs/ML_VALIDATION_REPORT.md)).
* **Regression Suite:** 78 passing unit and physics tests in `tests/`.

---

### Team Execution Guide (How to Carry From Here)

#### 1. Baseline Synchronization (All Teams)
Before writing or running code, fetch the merged LFS assets and engine modules:
```sh
git checkout <your-branch>
git pull origin main
git lfs pull
```
*(Crucial: Terrain GeoTIFF tiles, PSR vectors, and SPICE kernels are Git LFS objects.)*
Then run `python -m src.acquire.verify_data`; it must end with `all required data
present and verified`. Full file list, sources and the no-LFS fallback:
[docs/DATA_SETUP.md](docs/DATA_SETUP.md).

Event days (13–15 November): follow [docs/EVENT_DAY_PLAN.md](docs/EVENT_DAY_PLAN.md).
On day one, check the newly released resources against our data with
`python -m src.acquire.identify_resources <download folder>`.

#### 2. Backend Team (`feature/backend-systems`) — `@ariful305`, `@Eetherr77`
* [ ] **Wire Custom Coordinate Route:** Add `GET /api/v1/sites/custom?lat=...&lon=...&utc=...` calling `src.compute.site_evaluation.evaluate_custom_site`.
* [ ] **Wire Launch-Slip Route:** Add `GET /api/v1/sites/compare-dates?site_id=...&date_a=...&date_b=...` calling `src.compute.site_evaluation.compare_launch_dates`.
* [ ] **Expand Geometry Schema:** Update `/api/v1/sites/geometry` to return the new operational countdown fields (`time_to_sunset_hours`, `time_to_sunset_formatted`, etc.).
* [ ] **Wire Sensitivity Route:** Add `GET /api/v1/sites/sensitivity?lat=...&lon=...&utc=...` calling `src.compute.api_payloads.site_sensitivity` (cache responses; ~3–5 s; 422 north of ~83.5°S).
* [ ] **Wire Artemis III Regions Route:** Add `GET /api/v1/artemis-regions` returning `src.compute.api_payloads.artemis_regions()` (static; regions, not landing points).
* [ ] **Ingest Nested Mission Models:** Adapt backend `Mission` schema to ingest the nested structure in `data/missions.json` (see [docs/TEAM_INTEGRATION_GUIDE.md](docs/TEAM_INTEGRATION_GUIDE.md#backend-endpoint-wiring)).
* [ ] **Regression & PR:** Verify `pytest tests/` passes, push to `feature/backend-systems`, and open a PR targeting `main`. In your PR description, tag `@ASMFahim71` with the finalized response payloads.

#### 3. Frontend Team (`feature/frontend-systems`) — `@ASMFahim71`
* [ ] **Manifest Alignment:** Update `src/data/missions.ts` to match `data/missions.json` (remove `ls-1`/`PRIME-2`, adopt the 5 anchor missions, hide terminated Draper CP-12).
* [ ] **Dual-Mode Header:** Add the Simple Mode vs Scientific Mode switcher in `src/components/Header.tsx`.
* [ ] **Survival Countdown HUD:** Build large countdown indicators ("4d 18h Sunlight Remaining", "Earth Link: Active") in Simple Mode.
* [ ] **29.5-Day Scrubber:** Feed `data/precomputed/tracks/` into `TimelineScrubber.tsx` for 60 FPS orbital playback.
* [ ] **Cesium Click-to-Pin:** In `MoonGlobe.tsx`, add left-click raycasting to grab lat/lon and query `/api/v1/sites/custom`.
* [ ] **Date A vs Date B View:** Add the launch rescheduling comparison tab in `src/components/CompareView.tsx`.
* [ ] **PR:** Once Backend PR merges into `main`, pull `main`, verify end-to-end, and open Frontend PR.

#### 4. Scientific Review (`feature/research`) — `@Thirtha17`
* [ ] **JPL Horizons Ephemeris Spot-Check:** Cross-check SPICE Sun and Earth elevations for Apollo 11, Chandrayaan-3, and IM-2 against NASA JPL Horizons (target Δ < 0.1°).
* [ ] **Documentation Sign-off:** Complete review in `docs/SCIENTIFIC_VALIDATION_REPORT.md`.

#### 5. Deployment / CI Notice
* Automatic CD deployment to live Firebase Hosting is temporarily halted (`workflow 379013184` disabled manually) until the backend and frontend PRs are integrated and full builds pass cleanly.


---

## Team & Contacts

**HarnessApollo** is engineered and maintained by **Team Chhayanautical**.

| Channel | Link / Address | Description |
|----------|----------|----------|
|  **Official Website** | [chhayanautical.web.app](https://chhayanautical.web.app) | Mission portal & live web deployment |
| **NASA Space Apps Team Finder** | [Chhayanautical @ NSAC Finder](https://www.spaceappschallenge.org/2026/find-a-team/chhayanautical/) | Official team registration & participant roster |
| **Contact** | [chhayanautical@gmail.com](mailto:chhayanautical@gmail.com) | Official team contact & inquiries |

---

## License

This project is licensed under the LICENSE © 2026 Team Chhayanautical.
