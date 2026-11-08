# [Challenge Alignment] Major Issue Press

> **Issue Type**: Architecture & Engineering Epic (Phase 2 Master Sprint)
> **Status (audited 2026-11-05)**: 🟢 Data pipeline **DONE & MERGED** (PR #9, PR #11) · 🔴 Backend **NOT STARTED** · 🔴 Frontend **NOT STARTED** · 🔴 Research **NOT STARTED**
> **Baseline on `main`**: [`4cad12a`](https://github.com/k-shopnil/apolloharness/commit/4cad12a) (includes merge of PR #9 at [`7cb8a02`](https://github.com/k-shopnil/apolloharness/commit/7cb8a02))
> **Carries open work from**: Issue #7 (its backend and frontend items were never built; they are folded into this issue below)
> **Target Branches**: `feature/data-pipeline` (done), `feature/backend-systems`, `feature/frontend-systems`, `feature/research`
> **Assigned Maintainers**: `@0mehedihasan`, `@ariful305`, `@ASMFahim71`, `@Eetherr77`, `@k-shopnil`, `@Thirtha17`, Humayra Akter (role to be confirmed)
> **Governing Benchmark**: NASA Space Apps 2026 — [Lunar Landing Site Navigator](https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/) · event **13–15 Nov 2026**, prep done by **12 Nov**
> **Single sources of truth**: fleet & IDs → [`data/missions.json`](https://github.com/k-shopnil/apolloharness/blob/main/data/missions.json) · response shapes → [`docs/TEAM_INTEGRATION_GUIDE.md`](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md)

---

## 0. Revision note (2026-11-05) — read this first

This issue was rewritten after a cross-branch audit. What changed:

1. **Issue #7 was not "built".** The original version of this issue said the foundation from #7 (`/sites/geometry`, virtual Earth model, DTE laser) already existed. It does not exist on any branch. Those items are now listed below as open work.
2. **The fleet table had facts that were wrong.** The data pipeline corrected IM-1, Griffin/VIPER, Blue Ghost-2 and the SLIM wording from primary sources (see §3). **Build from `data/missions.json`, never from an issue table.**
3. **Backend and frontend branches are stale.** Both last changed on **2026-10-18** and are **30 commits behind `main`**. Rebasing onto `main` is now step one for both.
4. **"Zero Invented Data" currently fails on both branches.** The backend scores sites with fixed latitude-band constants and serves a mock catalog; the frontend hardcodes viability numbers and still lists `ls-1` / `PRIME-2`. Details in §5.
5. **The frontend does not need to wait for the backend.** The scrubber, Earth/Sun vectors and countdowns can all be built today from the static precomputed tracks on `main`.
6. **2026-11-06 addendum:** §8 adds the integration contract, CI, deployment and demo-readiness items found in a follow-up review. Settle §8.1 and §8.2 before writing integration code.
7. **2026-11-06, aligned with PR #11 (merged):** `/missions` is flat, `/sites/geometry` takes `site_id` or `lat`+`lon`, `offline_fixtures/` is now `offline_fixtures/`, PSR names are done, the event dates are known, and `main` now requires a PR, 1 approval and green checks.

---

## 1. Why this issue exists — insights from the official challenge release

Our scientific foundation (NAIF SPICE, LOLA altimetry, 360° terrain horizon ray-tracing, PSR cold traps) matches what NASA is asking for. The final challenge statement reveals four gaps:

1. **Existing NASA tools fail non-specialists.** QuickMap, Moon Trek and JPL Horizons are built for deep analysis. We must serve **both flight planners AND classrooms / the public**.
2. **Mission schedules slip.** Planners must compare **Date A vs Date B at the same site** ("If our launch slips 72 hours, does the ridge fall into shadow?").
3. **Operational countdowns matter most.** Time remaining before **sunset** and **Earthset**, not a static percentage.
4. **Fleet diversity and zero bluff.** Past **Apollo** missions, **international** programs (ISRO, CNSA, JAXA), and **custom coordinates anywhere on the Moon** — with 100% data faithfulness.

```
[ON MAIN TODAY]
NASA products (SPICE, LOLA, PGDA 69, PSR) -> Compute engine (src/compute, src/ml) -> Precomputed 29.5-day tracks (static JSON)
                                                    |
                                   [STILL TO BUILD — THIS ISSUE + CARRY-OVER FROM #7]
                                                    |
   FastAPI: /sites/custom, /sites/compare-dates, /sites/geometry (+countdowns)
                                                    |
   Cesium frontend: virtual Earth/Sun + DTE beam (#7), Simple/Scientific modes, countdown HUD,
                    29.5-day scrubber, click-to-pin, Date A vs Date B
```

---

## 2. Core architectural deliverables

### Deliverable A: Dual-Mode Accessibility (Simple vs. Scientific)

A mode switcher in the main header (`export type UIMode = 'simple' | 'scientific'`). Toggling must change UI density instantly, with no reload.

#### A1. Simple Mode (classrooms, educators, public)
* **Survival countdown clock** in the site card, e.g. **"4d 18h of sunlight remaining"**, **"Direct Earth contact: ACTIVE (round-trip ping 2.69 s)"**. Values come from the engine — the numbers here are examples only.
* **Plain-language status badges**, e.g. `Solar Power: PARTIAL (62% of the Sun visible)`, `Radio Link: CONNECTED`, `Lander Footing: SAFE (3.2° slope)` (⚠️ the engine has no single-site slope yet — see §8.4). Mapping table: [integration guide → Countdown HUD](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md#countdown-hud-simple-mode).
* **STEM micro-sandboxes** *(stretch — after must-haves merge)*:
  1. *The Skater Sun* — Earth's 23.5° tilt vs the Moon's 1.54° tilt.
  2. *Long Shadows* — how a grazing Sun stretches a crater-rim shadow. ⚠️ The original "1° sun on a 2,000 m rim = 50 km shadow" figure is **flagged for science review** (`@Thirtha17`) before it is shown.
  3. *Earth's Cosmic Wobble* — Earth tracing its ~±7° libration path in the sky.
* **"Save the Rover" launch-slip challenge** *(stretch)* — guided use of the timeline scrubber.

#### A2. Scientific Mode (mission planners, flight dynamics, judges)
* **Precision ephemeris telemetry** *(must-have)*: topocentric Sun/Earth elevation and azimuth, terrain horizon at that azimuth, the margin `elevation_deg - terrain_horizon_deg`, `disk_visible_fraction`, unit vectors in `MOON_PA`.
* **LOLA 360° horizon polar plot** *(stretch)*: skyline vs Sun and Earth tracks.
* **Lander slope safety envelope** *(stretch)*: < 8° nominal, 8°–12° caution, > 12° critical.
* **Payload-to-environment compatibility matrix** *(stretch)*.
* **Exportable mission dossier** (JSON + printable PDF) *(stretch)*.

### Deliverable B: Fleet manifest — grounded in primary sources

The canonical fleet lives in **`data/missions.json` on `main`** (16 records: 11 CLPS + 5 reference anchors). Fictional `ls-1` and `PRIME-2` are removed there. Every UI and API must load this file and use its IDs.

**Reference anchors** (all `coordinate_type: actual_landing`, from LROC imagery):

| ID | Mission / Agency | Coordinates (ME) | Baseline it provides |
| :--- | :--- | :--- | :--- |
| `anchor-apollo-11` | Apollo 11, LM Eagle (NASA) · 1969-07-20 | 0.674°N, 23.473°E · Mare Tranquillitatis | Equatorial baseline: high Sun, Earth always in view (computed value shown, not a quoted %) |
| `anchor-apollo-17` | Apollo 17, LM Challenger (NASA) · 1972-12-11 | 20.191°N, 30.772°E · Taurus-Littrow | Mountain valley: massifs mask the horizon (up to 13.6°) |
| `anchor-chandrayaan-3` | Chandrayaan-3, Vikram (ISRO) · 2023-08-23 | 69.374°S, 32.320°E · Shiv Shakti Point | High-latitude transition, grazing Sun |
| `anchor-change-4` | Chang'e 4 + Yutu-2 (CNSA) · 2019-01-03 | 45.457°S, 177.589°E · Von Kármán | Far side: no direct Earth link, relay needed |
| `anchor-slim` | SLIM (JAXA) · 2024-01-19 | 13.316°S, 25.251°E · near Shioli | Tip-over case study. **Wording fixed:** SLIM tipped over because a main engine lost thrust during descent; the slope was a contributing factor, not the cause |

**CLPS fleet** (status and coordinate type are binding; only `actual_landing` is a landing fix):

| ID | Mission | Status | Coordinate in catalog |
| :--- | :--- | :--- | :--- |
| `clps-to2-im-im1` | IM-1 Odysseus (Intuitive Machines) | completed | **80.13°S, 1.44°E** — actual landing near Malapert A |
| `clps-prime-1-im2` | IM-2 Athena (Intuitive Machines) | completed, limited ops | 84.79°S, 29.20°E — Mons Mouton (reported, rounded) |
| `clps-to19d-blue-ghost-1` | Blue Ghost Mission 1 (Firefly) | completed | 18.56°N, 61.81°E — Mare Crisium region centre |
| `clps-to2-ab-peregrine-1` | Peregrine Mission 1 (Astrobotic) | failed to land | target ellipse centre only |
| `clps-to20a-griffin-1` | Griffin Mission One (Astrobotic) | planned, **no VIPER** | **none published** — Nobile region named only |
| `clps-cs7-blue-origin-viper` | **VIPER delivery** on Blue Origin Blue Moon MK1 (CS-7) | planned, late 2027 | none published — south pole region |
| `clps-blue-moon-mk1-endurance` | Blue Moon MK1 Pathfinder "Endurance" | planned, no date | none published — Shackleton Connecting Ridge named |
| `clps-cs3-blue-ghost-2` | Blue Ghost Mission 2 (Firefly) | planned, NET 2027 | **Nassau Crater** (far side), crater centre 24.91°S, 177.34°E as reference only |
| `clps-cp11-im3` | IM-3 (Intuitive Machines) | planned, 2026 | Reiner Gamma target reference |
| `clps-cp22-im4` | IM-4 (Intuitive Machines) | planned, 2027 | south-pole site reference |
| `clps-cp12-draper` | Draper CP-12 (Schrödinger Basin) | **terminated** | hide from the active fleet |

**Corrections vs the original version of this issue:**

| Original claim | Correct value | Source |
| :--- | :--- | :--- |
| IM-1 at 86.00°S, 4.00°E | 80.13°S, 1.44°E | NASA / LROC |
| Griffin-1 carries VIPER, at 84.90°S, 31.60°W | Griffin flies without VIPER; no landing coordinate is published. VIPER was revived on Blue Origin (CS-7) | [NASA release 25-064](https://www.nasa.gov/news-release/nasa-selects-blue-origin-to-deliver-viper-rover-to-moons-south-pole/) |
| Blue Ghost-2 at Schrödinger Basin, 75.00°S, 132.40°E | Blue Ghost-2 targets Nassau Crater; Schrödinger was Draper CP-12, now terminated | [Firefly mission page](https://fireflyspace.com/missions/blue-ghost-mission-2/) |
| SLIM "proved the need for slope envelopes" | Engine thrust loss caused the tip-over; slope contributed | JAXA |
| Apollo 11 "> 98% Earth visibility" | Show the computed value (geometrically 100%) | Pipeline |

Full evidence: [integration guide → Known issues and open decisions](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md#known-issues-and-open-decisions).

### Deliverable C: Custom coordinates (globe click + manual entry)
1. **Pin-drop on the Cesium globe** — left-click anywhere, drop a beacon, open the telemetry drawer.
2. **Coordinate modal** — latitude (−90° to +90°), longitude (−180° to +180°), optional UTC.

Engine call: `site_evaluation.evaluate_custom_site` — measured **0.12–0.30 s warm** (call `warm_up()` at startup).

### Deliverable D: Temporal dynamics & rescheduling
* **29.5-day lunation scrubber** at the bottom of the globe viewport: sweeps the Sun along the horizon, animates Earth's libration, updates the DTE beam.
* **Launch-slip comparison** in `CompareView.tsx`: `[ Compare Landing Sites | Compare Launch Dates ]`, Date A vs Date B overlaid on a shared relative clock.

### Carried over from Issue #7 (never built)
* **Virtual Earth** placed along the sub-Earth vector, and a **lightweight directional Sun** along the sub-solar vector. Keep both lightweight (billboards / simple entities, no volumetric shaders).
* **DTE line-of-sight beam** from the active site to Earth: cyan/green when `direct_los` is true, red dashed when occulted.
* **Site HUD** above the active site: PSR distance, solar elevation and power status, Earth elevation and link status.
* **Layer toggles**: `[x] DTE LoS Beam`, `[x] Solar Vectors`.
* **Live API client with fallback** to the static tracks when the backend is not running.

---

## 3. Data honesty rules (all teams, binding)

From the [integration guide](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md#data-honesty-rules-all-teams):

1. **`null` means unknown, never zero.** Show "Unavailable — reason", never `0`.
2. **Always show `horizon_model` and `terrain.dem_product`.** `spherical_horizon` → label "Terrain not modelled here".
3. **`coordinate_type` is binding.** Only `actual_landing` is a landing fix.
4. **Visibility uses the body's centre**; `disk_visible_fraction` covers grazing cases. Earth LOS is geometric only (no link budget, no DSN scheduling).
5. **Countdowns never extrapolate.** Beyond the window → "> 29.5 days".
6. **No hardcoded science values in the UI or API.** No default landing ellipses, no fixed sunlight percentages, no placeholder distances.

---

## 4. Action plan & maintainer assignments

**Merge order:** Backend PR → Frontend PR → Research doc → deploy re-enabled.
**Backend and frontend start in parallel today.** Every PR into `main` must pass `pytest tests/` and `npm run build`.

Setup for everyone, on your own branch:
```sh
git fetch origin
git merge origin/main       # shared branches (backend): always merge, never rebase + force-push
                            # single-owner branches may rebase instead
git lfs pull                # terrain tiles, PSR vectors and SPICE kernels are LFS objects
```

### 4.1 Data Pipeline & SPICE Bridge — @0mehedihasan vai ✅ (merged in PR #9)
- [x] **Horizon event root-finder** — `spice_engine.find_horizon_events`, Sun and Earth rise/set against the LOLA skyline, 1 s bisection, `"4d 18h"` countdowns, finite-disc `disk_visible_fraction`, thread-safe `SPICE_LOCK`.
- [x] **Multi-day precomputation** — 29.5-day hourly tracks for 9 missions in `data/precomputed/tracks/` (missions without an exact coordinate or date are skipped by design and listed in `index.json`).
- [x] **Arbitrary-coordinate interpolator** — `terrain.interpolate_elevation` / `extract_horizon_mask_fast` on the 80 m polar DEM, with global LOLA `LDEM_64` fallback and committed per-site tiles.
- [x] **Manifest grounding** — `ls-1` / `PRIME-2` removed; 5 anchors + 11 CLPS records with sources, `payload_summary`, `coordinate_type`.
- [x] *Beyond scope:* validation vs NASA PGDA 69 (held-out R² 0.951, MAE 1.45 pp), regional screening, Pareto site recommender, 79 test functions.

Remaining support tasks:
- [ ] Pair with the backend team on engine wiring and review their PR.
- [ ] Give the frontend a build step that copies `data/precomputed/tracks/` into its public folder.
- [x] **PSR cold-trap names** — PR #11: NASA PSR ID plus the IAU host crater (`nearest_psr_id`, `nearest_psr_host`, `nearest_psr_label`, `nearest_large_psr`), ~0.05 s per lookup.
- [x] **Backend bridge** — PR #11: `src/compute/api_payloads.py` (`catalog_records`, `mission_geometry`, `site_geometry`, `site_sensitivity`, `artemis_regions`); `ValueError` → 422, `LookupError` → 404.
- [x] **Offline fixtures identical to the API** — PR #11: `offline_fixtures/`, with tests that fail if they drift.
- [x] **Data setup and verification** — PR #11: `docs/DATA_SETUP.md`, `python -m src.acquire.verify_data` (`--fetch` if the LFS quota runs out).
- [ ] Add `include_track` to `api_payloads.site_geometry`, so a custom pin can drive the time slider (§8.1).
- [ ] Install and verify the 531 MB global DEM on the demo machine.

*Thank you so much @0mehedihasan vai, your SPICE work is the secret sauce of this entire system!*

### 4.2 Backend Systems & API Endpoints — @ariful305 & @Eetherr77 🔴 (critical path)

**Start here:** every route below is one call into `src/compute/api_payloads.py` (PR #11). Wiring code: [integration guide → `/sites/geometry`](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md#get-apiv1sitesgeometry-ready-made-payloads).

Current state of `feature/backend-systems` (last commit 2026-10-18): only `/missions`, `/sites/score`, `/sites/comms`; scores use fixed constants (annual sunlight 78 / 65 / 50% by latitude band); a mock catalog (incl. Perseverance, Curiosity, Kennedy LC-39B); a 5 × 2.5 km default ellipse; tests assert the heuristic values.

- [ ] **Bring in `main` (merge, not rebase — two people share this branch).** Keep `main`'s `data/missions.json` and `offline_fixtures/missions.json`; merge both `requirements.txt` files; resolve `.gitignore`; delete `test_write.py`. *(Ariful)*
- [ ] **Serve the catalog with `api_payloads.catalog_records()`** — flat records with canonical IDs, `category`, `coordinate_type`, `landing_ellipse` (null = unknown), `has_precomputed_track`. Same shape as `offline_fixtures/site_geometry/missions.json`. Replace the old `Mission` model with this shape. Serve all 16 records. *(Ariful)*
- [ ] **Point `fixtures_dir` at `offline_fixtures/`** (rename table in the integration guide). *(Ariful)*
- [ ] **Remove invented values** — delete the 5 × 2.5 km default ellipse; replace `compute_site_score` heuristics with engine calls, or retire `/sites/score`. *(Ariful)*
- [ ] **`GET /api/v1/sites/custom?lat=&lon=&utc=`** → `site_evaluation.evaluate_custom_site` (422 on bad input). *(Eetherr77)*
- [ ] **`GET /api/v1/sites/compare-dates?site_id=&date_a=&date_b=`** → `site_evaluation.compare_launch_dates` (404 when the site has no coordinate, e.g. Griffin). *(Eetherr77)*
- [ ] **`GET /api/v1/sites/geometry`** (the #7 endpoint) with the countdown fields below. Request format: §8.1. For catalog missions, read `countdowns_at_start` from the track file. *(Eetherr77)*
  ```json
  {
    "sun":   { "azimuth_deg": 79.33, "elevation_deg": 2.53, "terrain_horizon_deg": 2.46, "is_lit": true,
               "time_to_sunset_hours": 367.08, "time_to_sunset_formatted": "15d 7h", "disk_visible_fraction": 0.661 },
    "earth": { "azimuth_deg": 327.52, "elevation_deg": 1.45, "direct_los": true,
               "time_to_earthset_hours": 452.88, "time_to_earthset_formatted": "18d 20h", "round_trip_light_time_s": 2.694 },
    "psr":   { "status": "not_requested", "distance_m": null, "inside_psr": null },
    "horizon_model": "lola_terrain_mask"
  }
  ```
  *(IM-2 at 2026-11-15T12:00Z, real engine output, trimmed. Full shape in the guide.)*
- [ ] **Startup** — `load_kernels()` and `site_evaluation.warm_up()`; scale with workers, not threads.
- [ ] **Rewrite tests on engine outputs** — `round_trip_light_time_s` in [2.3, 2.8]; Chang'e 4 → `direct_los == false` with `countdown_status == "no_earthrise_within_window"`; Apollo 17 → `horizon_model == "lola_terrain_mask"`, `dem_product == "LOLA GDR LDEM_64"`; sunset hours and formatted string both present or both null.
- [ ] **Open the PR to `main`** with sample payloads; tag `@ASMFahim71`.

### 4.3 Frontend & 3D Visualization — @ASMFahim71 🔴

Current state of `feature/frontend-systems` (last commit 2026-10-18): globe, fleet sidebar, drawer and site compare exist, but every science value is hardcoded (e.g. `SiteView.tsx` prints "Sun Azimuth: 042°"), there are no `fetch` calls, and `missions.ts` still lists `ls-1`, `xl-1`, `PRIME-2`.

Can start today (static data on `main`, no backend needed):
- [ ] **Move the app into `frontend/`** and rebase onto `main` (avoids a root-level `package.json` / `README.md` / `.gitignore` clash with the Python project).
- [ ] **Manifest alignment** — replace `src/data/missions.ts` with a loader over `data/missions.json`; canonical IDs; delete `ls-1`, `xl-1`, `PRIME-2` and all hardcoded viability numbers; hide terminated CP-12; respect `coordinate_type`.
- [ ] **29.5-day `TimelineScrubber.tsx`** on `data/precomputed/tracks/` — lerp elevations, **shortest-arc** azimuths, renormalized unit vectors, nearest-sample booleans; `null` = hatched "unknown". Recipe: [guide → Timeline scrubber](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md#timeline-scrubber-timelinescrubbertsx).
- [ ] **Virtual Earth, directional Sun and DTE beam** (#7 carry-over) from `sun_unit_moon_pa` / `earth_unit_moon_pa`; beam cyan/green when `earth_los`, red dashed when occulted; layer toggles.
- [ ] **Dual-mode header** in `Header.tsx`, state in `App.tsx`.
- [ ] **Simple Mode countdown HUD** from `countdowns_at_start`; Scientific Mode telemetry panel with the horizon margin and disc fraction.

After the backend PR lands:
- [ ] **API client with static fallback** (show which mode is active).
- [ ] **Click-to-pin** (`ScreenSpaceEventType.LEFT_CLICK` raycast → lat/lon → `/sites/custom`) and the **coordinate modal**.
- [ ] **Date A vs Date B** sub-tab in `CompareView.tsx` via `/sites/compare-dates`.
- [ ] **PR to `main`** with `npm run build` clean.

### 4.4 Scientific Review & Coordinate Validation — @Thirtha17 🔴
- [ ] **Review and sign off the JPL Horizons cross-check** done in PR #11 (13 sites over one synodic month, max deviation 0.006°, 100% agreement on above/below horizon; `data/validation/horizons_crosscheck.json`, `src/ml/horizons_crosscheck.py`). Spot-check these three epochs yourself:

  | Site | UTC | Sun el / az | Earth el / az |
  | :--- | :--- | :--- | :--- |
  | Apollo 11 (0.67416, 23.47314) | 1969-07-20T20:17:00Z | 10.692° / 88.805° | 59.225° / 272.194° |
  | Chandrayaan-3 (−69.3741, 32.32) | 2023-08-23T12:34:00Z | 8.613° / 62.048° | 12.995° / 318.997° |
  | IM-2 Mons Mouton (−84.79, 29.20) | 2026-11-15T12:00:00Z | 2.529° / 79.329° | 1.447° / 327.516° |

  Step-by-step Horizons settings: [guide → Research: validation workflow](https://github.com/k-shopnil/apolloharness/blob/main/docs/TEAM_INTEGRATION_GUIDE.md#research-validation-workflow).
- [ ] **Write `docs/SCIENTIFIC_VALIDATION_REPORT.md`** on `feature/research` (rebase onto `main` first).
- [ ] **Frame wording (carried from #7)** — one paragraph settling ME vs PA: README says computations use `MOON_PA`; the validation table describes observer coordinates in mean-Earth (ME); the DEM is ME/DE421.
- [ ] **Educational science review** of all Simple Mode copy, including the flagged "50 km shadow" figure.

## 5. Quality gates & Definition of Done

| # | Gate | Status on 2026-11-05 |
| :- | :--- | :--- |
| 1 | **Zero invented data** — no fictional missions, no hardcoded science values, every coordinate traceable | ✅ `main` · ❌ backend (heuristic %, default ellipse, mock catalog) · ❌ frontend (`ls-1`, `PRIME-2`, fixed numbers) |
| 2 | **Dual-mode fluidity** — instant switch, no reload, no broken layout | ❌ not built |
| 3 | **Operational countdowns** — sunset and Earthset in hours and formatted days | ✅ engine · ❌ API · ❌ UI |
| 4 | **Custom coordinates within 500 ms** | ✅ engine (~0.2–0.35 s warm, PSR included) · ❌ API · ❌ UI |
| 5 | **`pytest tests/` passes 100%** | ✅ `main`: 114 tests, green in CI on PR #11 · backend tests must be rewritten |
| 6 | **`npm run build` succeeds, zero TS errors** | not verified until the frontend is rebased |
| 7 | **Offline presentation safe** — works with network disabled | ✅ static tracks + fixtures exist · ❌ not wired in UI |
| 8 | **LFS assets present** — `git lfs pull` in setup and CI, `horizon_model` shown in UI | ❌ not enforced |
| 9 | **Canonical IDs everywhere** — API and UI use `data/missions.json` IDs | ❌ three schemes today |

---

## 6. Scope: must-have vs stretch

**Must-have for the prototype:** canonical fleet on the globe · virtual Earth/Sun + DTE beam · countdown HUD · 29.5-day scrubber · custom coordinates (click + modal) · Date A vs Date B · Simple/Scientific switch with the precision telemetry panel.

**Stretch (only after must-haves merge):** STEM micro-sandboxes · "Save the Rover" challenge · horizon polar plot · slope envelope · payload matrix · dossier export · site recommender endpoint (`POST /sites/recommend`, engine already exists). · `/sites/sensitivity` ("small changes, big effects", 3–5 s per call, cache it) · `/artemis-regions` (show as labels or halos, never pins)

---

---

## 8. Integration contract, CI & demo readiness (added 2026-11-06)

A follow-up review found gaps in how the pieces connect. **Settle §8.1 and §8.2 before writing integration code**; the rest can land with the PRs.

### 8.1 API contract — one shape per thing
- [x] **`/missions` shape: flat** (decided in PR #11). `api_payloads.catalog_records()` online, `offline_fixtures/site_geometry/missions.json` offline: the same shape both ways, enforced by tests. *(Fahim writes one shared `Mission` TypeScript type from it)*
- [x] **`/sites/geometry` request format** (decided in PR #11): `?site_id=<canonical id>` **or** `?lat=&lon=&utc=` (`utc` defaults to now). With `site_id`, it returns the **start of the precomputed window** (`source: "precomputed_track"`, `utc` ignored). With `lat`+`lon`, it computes live (`source: "engine"`, ~0.2–0.35 s warm). `404` for an unknown ID or a record with no coordinate or date; `422` for bad input.
- [ ] **One readout shape:** `/sites/geometry` and `/sites/custom` both return `apolloharness.site_geometry.v1` (`sun`, `earth` with `unit_vector_moon_pa`, `events`, `psr`, `horizon_model`, `terrain`, `source`). `/sites/custom` = `site_geometry(lat, lon, utc)` plus the optional track. Errors use FastAPI's default `{"detail": "..."}`. *(Eetherr77)*
- [ ] **Time slider for a custom pin:** precomputed day files exist for 9 missions only. For a clicked spot, the frontend calls `/sites/custom?...&include_track=true`, which returns the same column schema as the track files. Measure the added latency and record it in the PR. *(Eetherr77 exposes the flag; Fahim feeds it to `TimelineScrubber`)*
- [ ] **Day-1 draft PR with real samples:** the backend opens a draft PR early with real engine output for three calls (IM-2 geometry, one custom click, one compare-dates), so the frontend wires against real payloads before the full PR. *(Eetherr77)*

### 8.2 CI and branch workflow
- [x] **PR check workflow** `.github/workflows/pr-checks.yml` (PR #10, which also points the deploy workflow and `firebase.json` at `frontend/`). Jobs: `changes` (decides whether the science job runs), `python-tests` (cached Git LFS pull, LFS completeness check, `pytest`), `frontend-build` (skipped until `frontend/` exists), `data-guard` (fails on known mock IDs or the invented default ellipse). Merged; all four jobs are now required on `main` together with 1 approving review, stale approvals dismissed on new pushes, and the branch up to date with `main` (ruleset updated 2026-11-06). *(@k-shopnil)*
- [ ] **Shared branches merge, never rebase.** Two people share `feature/backend-systems`: use `git merge origin/main`, and never force-push. Single-owner branches may rebase. *(Ariful, Eetherr77)*
- [ ] **Named reviewers.** Backend PR → Mehedi (engine use) + Fahim (contract). Frontend PR → Eetherr77 (API client) + Thirtha (Simple Mode science wording). Research PR → Mehedi. *(everyone)*

### 8.3 Deployment and configuration
- [ ] **Backend image includes the engine.** The `Dockerfile` copies `backend/`, `data/` and `offline_fixtures/` but not `src/`. Add `COPY src ./src`, install the merged requirements (`spiceypy`, `rasterio`, `geopandas` + the FastAPI stack), drop `RUN pytest` from the image build (CI runs the tests), and mount or copy `data/` only after `git lfs pull`. Mirror the `src` volume in `docker-compose.yml`. *(Eetherr77)*
- [ ] **CORS for the hosted frontend.** `cors_origins` allows `chhayanautical.web.app` and localhost, but not the `apolloharness` Firebase site. Add its origin (confirm the exact URL in Firebase). *(Ariful)*
- [ ] **Frontend API address.** Read `VITE_API_URL` (default `http://localhost:8000`). If it is unreachable, fall back to the static files and show an "Offline mode" badge. *(Fahim)*

### 8.4 Data gap
- [ ] **Slope for a single site.** `evaluate_custom_site` returns no slope; only `regional.screen_region` computes `slope_deg`. Either add slope to the single-site output, or the "Lander Footing" badge moves to stretch and stays hidden. *(Mehedi decides)*

### 8.5 Demo and submission readiness
- [x] **Deadline:** event **13–15 Nov 2026**; backend deployed and offline mode tested by **12 Nov** ([event-day plan](https://github.com/k-shopnil/apolloharness/blob/main/docs/EVENT_DAY_PLAN.md)). Anything in §6 "stretch" not merged by then is cut.
- [ ] **Demo script and offline demo-machine checklist:** `git lfs pull`, global DEM installed, `docker compose up`, a full rehearsal with the network off, plus the submission materials. *(proposed: Humayra Akter, with Thirtha for science wording — to confirm)*



