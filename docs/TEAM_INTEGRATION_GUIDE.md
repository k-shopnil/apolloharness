# Issue #8 data-pipeline integration guide

This guide covers what `feature/data-pipeline` delivers for Issue #8 (dual-mode
accessibility, fleet expansion, custom coordinates, temporal rescheduling) and
how each team uses it. Everything here runs offline from committed NASA
products and SPICE kernels; no network is needed at runtime.

- [What is delivered](#what-is-delivered)
- [Data honesty rules (all teams)](#data-honesty-rules-all-teams)
- [Backend: endpoint wiring](#backend-endpoint-wiring)
- [Frontend: tracks, countdowns, manifest](#frontend-tracks-countdowns-manifest)
- [Research: validation workflow](#research-validation-workflow)
- [Downloading the global LOLA DEM (LDEM_64)](#downloading-the-global-lola-dem-ldem_64)
- [Known issues and open decisions](#known-issues-and-open-decisions)
- [Regenerating and testing](#regenerating-and-testing)

> **Setting up data?** Every external file, its source, checksum and location,
> plus the no-LFS fallback, is in [DATA_SETUP.md](DATA_SETUP.md). Check a
> machine with `python -m src.acquire.verify_data`.

## What is delivered

| Issue #8 item | Function / file | Notes |
|---|---|---|
| Horizon event root-finder | `spice_engine.find_horizon_events` | Sun and Earth rise/set against the LOLA terrain mask, bisection to 1 s |
| Operational countdowns | `find_horizon_events(...)["sun"/"earth"]` | Exact Issue #8 field names, plus status |
| Multi-day precomputation | `spice_engine.calculate_geometry_track`, `calculate_hourly_geometry(step_minutes=)` | Column arrays for a 60 FPS scrubber |
| Offline mission tracks | `python -m src.compute.precompute_tracks` → `data/precomputed/tracks/` | 29.5-day windows from touchdown |
| Arbitrary-coordinate interpolator | `terrain.interpolate_elevation`, `terrain.extract_horizon_mask_fast`, `terrain.evaluate_site_terrain` | Bilinear interpolation on `LDEM_80S_80MPP_ADJ.TIF`, with automatic fallback to the global LOLA GDR `LDEM_64` |
| Global terrain (beyond the issue) | `global_terrain.build_site_tile`, committed tiles in `data/lola/tiles/` | Real mountains at every catalog site, not only 80–90°S |
| Custom site, one call | `site_evaluation.evaluate_custom_site` | Measured 0.12–0.30 s per click when warm; call `warm_up()` at startup |
| Launch-slip Date A vs Date B | `site_evaluation.compare_launch_dates` | Shared relative clock, delta summary |
| PSR proximity (interactive) | `proximity.nearest_psr_within` | Reports `inside_psr` and 0 m inside a cold trap |
| PSR names (Issue #7 / #8 §4.1) | `nearest_psr_within(...)["nearest_psr_id", "nearest_psr_host", "nearest_psr_label"]`, `psr_names.host_crater` | PGDA ID plus the IAU-named host crater from the USGS gazetteer; `null` rather than an invented name |
| Backend bridge (Issue #8 §4.2) | `api_payloads.catalog_records`, `site_geometry`, `mission_geometry` | Route handlers become one call; Earth/Sun `unit_vector_moon_pa` included for the virtual Earth/Sun and DTE beam |
| "Small changes, big effects" (beyond the issue) | `api_payloads.site_sensitivity` → `GET /api/v1/sites/sensitivity` | How much sunlight / Earth LOS change if the lander moves a few hundred metres, arrives a few days later, or raises its antenna |
| Artemis III candidate regions (beyond the issue) | `api_payloads.artemis_regions` → `GET /api/v1/artemis-regions`, `data/artemis_iii_regions.json` | NASA's nine regions (Oct 2024), labelled as regions, anchored to IAU features |
| Event-day resource check (beyond the issue) | `python -m src.acquire.identify_resources`, [EVENT_DAY_PLAN.md](EVENT_DAY_PLAN.md) | Classifies released files as KNOWN / NEW_VERSION / NEW by SHA-256 and describes new rasters and vectors; per-team plan for 13–15 Nov |
| Manifest grounding | `data/missions.json`, `offline_fixtures/missions.json` | 11 CLPS + 5 sourced reference anchors, each with `payload_summary` |
| Regional screening (beyond the issue) | `regional.screen_region` | Exact physics for a candidate grid: ~13 ms/point, e.g. 317 points in ~4 s |
| Site recommendations (beyond the issue) | `ml.recommend.recommend_sites` | Pareto ranking under the slope envelope; no invented weights |
| Validation vs NASA (beyond the issue) | `python -m src.ml.validation`, [ML_VALIDATION_REPORT.md](ML_VALIDATION_REPORT.md) | Held-out test: R² 0.951, MAE 1.45 pp, bias −0.05 pp |

## Data honesty rules (all teams)

1. **`None` means unknown, never zero.** A countdown, elevation or percentage
   that is `None` always comes with a `status` / `countdown_status` that says
   why. Show "Unavailable — outside LOLA polar coverage" (or similar). Never
   show `0`.
2. **Always show `horizon_model` and `terrain.dem_product`.**
   `lola_terrain_mask` means real mountains are modelled, and `dem_product`
   says from which map. That is either the 80 m polar DEM (80–90°S) or
   LOLA GDR `LDEM_64` (~474 m/pixel, everywhere else; coarser, so small
   craters near the site are smoothed). `spherical_horizon` (smooth Moon)
   now only appears for a custom click outside 80–90°S on a machine without
   the global DEM. Label that "Terrain not modelled here".
3. **`coordinate_type` is binding.** Only `actual_landing` is a landing fix.
   All five anchors and IM-1 are now `actual_landing`, from LROC orbital images.
   `*_reference` values are regions or targets.
4. **Visibility rule.** `is_lit` / `direct_los`, the events and the countdowns
   use the body's **centre** against the terrain horizon at its azimuth.
   `disk_visible_fraction` (0–1) adds the finite disc, using the exact
   circular-segment area for the Sun (radius ~0.27°) and Earth (~0.9°). Use
   it for grazing cases such as "Sun 62% visible", and as a solar-power
   proxy. The horizon is treated as straight across the disc. Earth LOS is
   geometric only: it does not model link budget or DSN scheduling.
5. **Countdowns never extrapolate.** If the next event is beyond the window,
   the status is `no_sunset_within_window` (or the matching earth status) and
   the UI should say "> 29.5 days".

## Backend: endpoint wiring

Owners: `@ariful305`, `@Eetherr77`. Load kernels once at application startup;
the functions also call `load_kernels()`, which does nothing on later calls.

```python
from src.compute.spice_engine import load_kernels, unload_kernels
from src.compute.site_evaluation import evaluate_custom_site, compare_launch_dates

@app.on_event("startup")
def _spice_up() -> None:
    load_kernels()

@app.on_event("shutdown")
def _spice_down() -> None:
    unload_kernels()
```

> CSPICE is not thread-safe. Without serialization, 6 concurrent requests
> all failed with `SpiceINVALIDDIVISOR`. The pipeline now serializes every
> public SPICE entry point with `spice_engine.SPICE_LOCK` (re-entrant), and
> each call re-loads kernels inside the lock. Plain FastAPI `def` endpoints
> in the default thread pool are therefore safe, and no lock is needed in
> backend code. A concurrency test (8 threads, with hostile
> `unload_kernels()` calls) guards this. SPICE work runs one call at a time,
> so scale with processes (workers), not threads.

### `GET /api/v1/sites/custom?lat=&lon=&utc=`

```python
@router.get("/sites/custom")
def custom_site(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
                utc: str | None = None, include_psr: bool = False, include_track: bool = False):
    utc = utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        return evaluate_custom_site(lat, lon, utc, include_psr=include_psr,
                                    include_track=include_track)
    except ValueError as exc:      # bad UTC / coordinates
        raise HTTPException(422, str(exc))
```

The response shape is shown below. Field names inside `sun` and `earth` are a
superset of the Issue #8 `/sites/geometry` schema.

```json
{
  "latitude_deg": -84.79, "longitude_deg": 29.2, "utc": "2026-11-15T12:00:00Z",
  "horizon_model": "lola_terrain_mask",
  "terrain": {"elevation_m": 5320.8, "status": "complete", "interpolation": "bilinear",
              "dem_resolution_m": 80.0, "horizon_mask": {"azimuth_deg": [...], "elevation_deg": [...]},
              "horizon_incomplete_azimuths": 0},
  "sun": {"azimuth_deg": 79.329, "elevation_deg": 2.529, "terrain_horizon_deg": 2.461,
          "is_lit": true, "time_to_sunset_hours": 367.08, "time_to_sunset_formatted": "15d 7h",
          "time_to_sunrise_hours": null, "time_to_sunrise_formatted": null,
          "countdown_status": "complete", "fraction_of_window_up": 0.518,
          "angular_radius_deg": 0.27, "disk_visible_fraction": 0.661},
  "earth": {"azimuth_deg": 327.516, "elevation_deg": 1.447, "terrain_horizon_deg": -1.451,
            "direct_los": true, "time_to_earthset_hours": 452.883,
            "time_to_earthset_formatted": "18d 20h", "time_to_earthrise_hours": null,
            "time_to_earthrise_formatted": null, "countdown_status": "complete",
            "fraction_of_window_up": 0.824, "angular_radius_deg": 0.904,
            "disk_visible_fraction": 1.0, "range_km": 403845.7, "round_trip_light_time_s": 2.694},
  "events": [{"body": "sun", "kind": "set", "utc": "2026-11-30T19:04:47Z", "hours_from_start": 367.0797},
             {"body": "earth", "kind": "set", "utc": "2026-12-04T08:52:59Z", "hours_from_start": 452.8832}],
  "annual_illumination": {"status": "complete", "annual_sunlight_percent": 46.552,
                          "source_dataset": "AVGVISIB_85S_060M_201608.TIF"},
  "psr": {"status": "not_requested", "distance_m": null, "inside_psr": null}
}
```

(Real output with the validated 100 km horizon; arrays trimmed.) In this case
the Sun clears the LOLA skyline by only 0.07°, which is less than the solar
radius, so `sun.disk_visible_fraction` is 0.661: only 66% of the disc is up. This is the knife-edge case the
launch-slip view exists for. Scientific Mode should show the margin
`elevation_deg - terrain_horizon_deg` and the disc fraction. Both `sun` and
`earth` also carry `angular_radius_deg` and `disk_visible_fraction`.

Latency: about 0.12–0.30 s per warm call (call `site_evaluation.warm_up()`
once at startup; the first cold call is about 0.5 s). `include_psr=true`
adds about 0.05 s: `warm_up()` builds a spatially indexed FlatGeobuf copy of
the PSR product once (`cache/derived/LPSR_80S_20MPP_ADJ.fgb`, about 5 s,
236 MB). Without it, every lookup scans all 506,349 polygons (about 0.3 s).

### `GET /api/v1/sites/compare-dates?site_id=&date_a=&date_b=`

Resolve `site_id` to coordinates from `data/missions.json`. Return `404` for
records whose `landing_site.latitude_deg` is `null` (Griffin).

```python
site = next(m for m in missions if m["id"] == site_id)["landing_site"]
return compare_launch_dates(site["latitude_deg"], site["longitude_deg"], date_a, date_b,
                            duration_days=14.0)
```

The response contains `date_a` and `date_b`, each with `sun`, `earth`,
`events`, `sunlit_percent`, `earth_los_percent` and `track`, plus
`delta_b_minus_a` with `sunlit_percent`, `earth_los_percent` and
`lit_at_arrival_changed`. Both tracks share `hours_from_start`, so the
frontend overlays them directly. Measured: about 0.17 s for two 14-day windows.

### `POST /api/v1/sites/recommend` (suggested)

This finds the best landing spots near a click, using exact physics over a
candidate grid and then Pareto ranking. It takes seconds, so run it as a
background task or cache it per (site, date).

```python
from src.compute.regional import screen_region
from src.ml.recommend import recommend_sites

screen = screen_region(lat, lon, start_utc, radius_m=5_000, spacing_m=500,
                       duration_days=14)                    # ~4 s, 317 points
result = recommend_sites(screen, max_slope_deg=8.0, top_k=10)
# Science priority (planner chooses): drill near a cold trap
result = recommend_sites(screen, objectives=("mean_sun_disk_percent",
                         "earth_los_percent", "psr_distance_m"),
                         weights={"mean_sun_disk_percent": 1, "earth_los_percent": 1,
                                  "psr_distance_m": 2})
```

`screen["columns"]` doubles as a heatmap layer. It has parallel arrays of
lat/lon, `elevation_m`, `slope_deg`, `sunlit_percent`,
`mean_sun_disk_percent`, `earth_los_percent`, `longest_darkness_hours`,
`longest_earth_blackout_hours` and `psr_distance_m`. Each recommendation
carries `pareto_rank`, `slope_class` (nominal / caution / critical, from the
Issue #8 envelope), `top_decile_in` (a plain-language "why") and every
metric. `ranking_mode` says whether planner weights were used. Without
weights the ranking is parameter-free: Pareto front, then crowding
distance, then gentler slope.

### `GET /api/v1/sites/geometry` (ready-made payloads)

`src/compute/api_payloads.py` builds the whole Issue #7/#8 payload, so each
route is one call. Every value comes from the engine or a precomputed track.

```python
from src.compute.api_payloads import catalog_records, mission_geometry, site_geometry

@router.get("/missions")
def missions():
    return catalog_records()        # flat Mission shape, canonical IDs, 16 records

@router.get("/sites/geometry")
def geometry(site_id: str | None = None, lat: float | None = Query(None, ge=-90, le=90),
             lon: float | None = Query(None, ge=-180, le=180), utc: str | None = None):
    try:
        if site_id:
            return mission_geometry(site_id)   # reads the track file, no SPICE call
        if lat is None or lon is None:
            raise ValueError("give site_id, or lat and lon")
        utc = utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return site_geometry(lat, lon, utc)    # ~0.2-0.35 s warm, PSR included
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except LookupError as exc:                 # unknown id, or no coordinate/date (Griffin)
        raise HTTPException(404, str(exc))
```

Payload (`schema: "apolloharness.site_geometry.v1"`):

- `sun` / `earth`: the `find_horizon_events` blocks (elevation, azimuth,
  terrain horizon, `is_lit` / `direct_los`, countdowns, disc fraction), plus
  `unit_vector_moon_pa`. That vector points from the site to the body in
  `MOON_PA`, which is what the virtual Earth/Sun and the DTE beam need.
- `psr`: `distance_m`, `inside_psr`, `nearest_psr_id`, `nearest_psr_area_km2`,
  and `nearest_psr_host` / `nearest_psr_label` (see
  [PSR names](#psr-names-what-the-ui-may-say) below).
- `source`: `"engine"` or `"precomputed_track"`, so the UI can show which.
- No `tactical_pct`, `solar_power_status` or `uptime_pct` fields, because the
  #7 example invented them. Use `sun.fraction_of_window_up`,
  `sun.disk_visible_fraction` and `earth.fraction_of_window_up` instead.

### Optional, after the core routes: `GET /api/v1/sites/sensitivity?lat=&lon=&utc=` ("small changes, big effects")

```python
from src.compute.api_payloads import site_sensitivity
payload = site_sensitivity(lat, lon, utc)        # ValueError -> HTTP 422
```

The polar landing problem is grazing geometry: a few hundred metres or a
few days can turn a good site into a dark one. One call answers three
questions with the engine's exact physics (no surrogate):

| Block | Question | Shape |
|---|---|---|
| `position.<metric>` | What changes if the lander lands a little elsewhere? | `centre`, `neighbours` (min/p10/median/p90/max over the grid), `best_neighbour` (lat/lon, `distance_m`, `bearing_deg`, `direction`, `value`, `improvement`, `regional_slope_deg`), `best_by_distance.within_250_m` … , `headline` |
| `arrival_date[]` | What if arrival slips ±1…7 days? | per slip: `start_utc`, `lit_at_arrival`, `earth_visible_at_arrival`, `sunlit_percent`, `earth_los_percent` |
| `observer_height[]` | What does a 5 m mast buy? | 0 m, 1.5 m (engine default), 5 m: `sunlit_percent`, `earth_los_percent` |

Metrics in `position`: `sunlit_percent`, `earth_los_percent` (higher is
better), `longest_darkness_hours`, `longest_earth_blackout_hours` (lower is
better). `headline` is a ready sentence, e.g. for IM-2 at its track start:
*"Moving 599 m NW raises sunlight from 98.2% to 100.0%."* It is `null`
when no neighbour improves the metric (`centre_is_best: true`); the UI then
says the chosen spot is already the best within the radius.

Example (IM-2, `offline_fixtures/site_sensitivity/clps-prime-1-im2.json`):
arriving 7 days earlier gives 49.9% sunlight over the 14-day mission
window, on time 98.2%, 7 days later 48.7%. That is the launch-slip story
in one array.

Rules the UI must keep:

- Defaults: 1 km radius, 100 m spacing (~316 points), 14-day window,
  ±7-day slips. Latency is about 3–5 s, so **cache by request** and show a
  spinner; do not call it on every mouse move.
- Proposed moves never exceed `max_regional_slope_deg` (default 15°). That
  is the **80 m regional slope**, a screen, not a landing-safety check.
- Sites north of about **83.5°S** are refused (HTTP 422): their 100 km
  horizon runs off the polar DEM, so the comparison would be incomplete.
  Show the message; do not substitute numbers.
- Offline: `offline_fixtures/site_sensitivity/<id>.json` is the payload for
  each tracked polar site (currently IM-2), with `site_id` and `mission`
  added. A test fails if it drifts from the live API.

### Optional, after the core routes: `GET /api/v1/artemis-regions` (Artemis III context layer)

`artemis_regions()` returns NASA's nine Artemis III candidate landing
**regions** (release 24-136, 2024-10-28, "in no priority order"): Peak near
Cabeus B, Haworth, Malapert Massif, Mons Mouton Plateau, Mons Mouton, Nobile
Rim 1, Nobile Rim 2, de Gerlache Rim 2 and Slater Plain.

NASA published the regions as an image only, with no coordinates. We
therefore do not invent centres. Each record carries the IAU feature that
names it (`anchor`: official centre, diameter, USGS link) and an
`anchor_relation`. For example, Nobile Rim 1 *"is on the rim of this
crater, not at its centre"*, so it lies about one crater radius (~40 km)
from the anchor. `catalog_sites_near_anchor` links regions to our missions:
IM-2 landed 7.7 km from the IAU centre of Mons Mouton.

UI rules:

- Label: "Artemis III candidate region near Nobile crater". Never "landing
  site", never a lander icon, never a pin with a precise coordinate.
  Every record has `kind: "candidate_region"` and `is_landing_point: false`.
- Draw a soft label or halo at the anchor, not a box. A box would imply a
  boundary we do not have.
- Do not run "evaluate this site" on an anchor. A crater centre is the
  crater floor, often a PSR, not the region. Users can click the terrain
  near the label to evaluate real points.
- Cite the sources in `sources` (NASA release, NASA NTRS 20250011660, USGS
  gazetteer).

Rebuild with `python -m src.acquire.artemis_regions`, which reads the pinned
USGS gazetteer. Re-check NASA's list on event day (see
[EVENT_DAY_PLAN.md](EVENT_DAY_PLAN.md)).

### PSR names: what the UI may say

PSRs have no official names; the IAU names craters, not shadows. NASA's
product identifies each PSR with a code such as `HNP_874817_0293767`, which
is now returned as `nearest_psr_id`. Before this fix `nearest_psr_id` was
always `null`, because the code never looked in the product's `name` column.
`nearest_psr_host` gives the **smallest IAU-named crater whose rim circle
holds at least half of the PSR's area**, taken from the USGS Gazetteer of
Planetary Nomenclature. It includes the crater's diameter, its USGS link, and
`psr_area_fraction_inside_rim` as evidence. A point-in-circle test was
rejected: it credited a 242 km² PSR to a 17 km crater because the PSR's
centre point fell inside that crater. `nearest_psr_label` is the ready string
`"PSR in Shackleton crater"`. When no named crater contains it, both are
`null`; the UI should show the distance and area only, and must never
invent a name like "Faustini Rim".

Also show `nearest_psr_area_km2`. Many nearest PSRs are micro cold traps of
about 0.001 km² (a few 20 m pixels). These are real, but they are not the
large crater-floor PSRs a reader would picture. `psr.nearest_large_psr` therefore
gives the nearest PSR of at least 1 km² within 50 km, with `id`,
`area_km2`, `host` and `label`. The 1 km² cut is a display choice, not a
physical threshold. Suggested HUD lines:

| Site | Line 1 (nearest any) | Line 2 (`nearest_large_psr`) |
|---|---|---|
| IM-2 | 474 m to a micro cold trap (0.001 km²) | 9.7 km to a 2.4 km² PSR |
| IM-1 | 555 m to a micro cold trap (0.045 km²) | 8.4 km to a 14.5 km² PSR |
| Shackleton floor | Inside a PSR in Shackleton crater (233 km²) | same |

Neither IM-1 nor IM-2 sits next to an IAU-named crater's PSR, so neither
gets a name. Showing a name there would be invented data.

### Offline fallback for the frontend (gate 7)

`offline_fixtures/site_geometry/<id>.json` is `mission_geometry(id)` for each
of the 9 tracked sites, and `missions.json` is `catalog_records()`. They have
exactly the API's shape: the UI fetches `/api/v1/sites/geometry?site_id=`,
and on failure loads the fixture through the same parser. The tracked PSR
context (polar sites) is included, so the cold-trap line works with the
network off. A test fails if fixtures drift from the API; regenerate them
with `python -m src.compute.api_payloads`.

### Mission catalog schema mismatch (action needed)

`backend/api/v1/endpoints/missions.py` (`Mission` model) and
`scripts/validate_mission_schemas.py` expect flat `name`, `lat`, `lon`,
`start_date` and `payload_instruments[].type`. The pipeline catalog has used
nested fields since Issue #2: `mission`, `landing_site.latitude_deg/longitude_deg`,
`target_date` and `payloads[].purpose`. Map these in the backend loader
rather than renaming the source:

| Backend field | Pipeline field |
|---|---|
| `name` | `mission` |
| `lat` / `lon` | `landing_site.latitude_deg` / `landing_site.longitude_deg` (can be `null`) |
| `start_date` | `touchdown_utc[:10]`, or `target_date` when it is a full date |
| `payload_instruments[].type` | `", ".join(payloads[].purpose)` |
| `landing_ellipse` | `landing_ellipse_km` (null = unknown; **do not** default to 5 × 2.5 km) |
| *(new)* `category` | `"clps"` or `"reference_anchor"` |

Do not use the 5 × 2.5 km default ellipse for real missions. It is invented
data, which the Issue #8 "Zero Invented Data" gate rules out.

### Renamed: `demo_fixtures/` → `offline_fixtures/` (action needed)

The offline data folder is now `offline_fixtures/`, and the per-record field
`demo_analysis` is now `offline_analysis`. When rebasing, update the 3 places
on `feature/backend-systems` that hard-code the old path:

| File | Change |
|---|---|
| `backend/core/config.py` | `fixtures_dir = ROOT_DIR / "offline_fixtures"` |
| `Dockerfile` | `COPY offline_fixtures ./offline_fixtures` |
| `docker-compose.yml` | `./offline_fixtures:/app/offline_fixtures` |

### Tests to add on the backend branch

Assert that `sun.time_to_sunset_hours` and `sun.time_to_sunset_formatted` are
both present and either both `null` or consistent. Assert
`earth.round_trip_light_time_s` is within `[2.3, 2.8]`. Assert that a
far-side site (Chang'e 4) returns `direct_los == false` with
`countdown_status == "no_earthrise_within_window"`. Assert that Apollo 17
returns `horizon_model == "lola_terrain_mask"` with `terrain.dem_product ==
"LOLA GDR LDEM_64"` (this needs the committed tiles; see the deployment note
below).

### Deployment note: terrain files

The committed site tiles are stored with **Git LFS**. On a fresh clone, run
`git lfs pull`. Without it, the tiles are tiny pointer files, and the
pipeline falls back to the smooth-Moon horizon and says so; the related
science tests skip. The 531 MB global `ldem_64.img` is **not** in git. The
server only needs it to give terrain for custom clicks outside 80–90°S that
are far from catalog sites. See
[Downloading the global LOLA DEM](#downloading-the-global-lola-dem-ldem_64).

## Frontend: tracks, countdowns, manifest

Owner: `@ASMFahim71`.

### Timeline scrubber (`TimelineScrubber.tsx`)

Fetch `data/precomputed/tracks/index.json` once. Its `missions[]` entries
carry a `status`, and only `status === "complete"` has a file. Then lazy-load
`<id>.json`. Each file is 29.5 days at 60-minute steps (709 samples, about
110 KB) and is safe to bundle for offline deployments.

```ts
type Track = {
  schema: "apolloharness.geometry_track.v1";
  start_utc: string; step_minutes: number; samples: number;
  horizon_model: "lola_terrain_mask" | "spherical_horizon";
  sunlit_percent: number | null; earth_los_percent: number | null;
  mean_sun_disk_visible_fraction: number | null;   // solar-power proxy over the window
  sun_partially_blocked_percent: number | null;    // % of samples with a cut disc
  earth_partially_blocked_percent: number | null;  // IM-2: 12.7%; elsewhere ~0
  columns: {
    utc: string[]; hours_from_start: number[];
    sun_elevation_deg: number[]; sun_azimuth_deg: number[];
    sun_terrain_horizon_deg: (number | null)[]; sun_lit: (boolean | null)[];
    sun_disk_visible_fraction: (number | null)[];   // 0..1 of the solar disc
    earth_elevation_deg: number[]; earth_azimuth_deg: number[];
    earth_terrain_horizon_deg: (number | null)[]; earth_los: (boolean | null)[];
    earth_disk_visible_fraction: (number | null)[]; // 0..1 of Earth's disc
    earth_range_km: number[]; round_trip_light_time_s: number[];
    sun_unit_moon_pa: [number, number, number][];   // observer→Sun, MOON_PA
    earth_unit_moon_pa: [number, number, number][]; // observer→Earth, MOON_PA
  };
};
```

To animate smoothly at 60 FPS, interpolate between samples `i` and `i+1`
with `f = (t - i*step) / step`:

- Elevations: linear interpolation.
- **Azimuths wrap at 360°.** Interpolate the shortest arc:
  `d = ((b - a + 540) % 360) - 180; az = (a + f*d + 360) % 360`.
  A naive lerp from 359° to 1° sweeps the Sun backwards around the sky.
- Unit vectors: lerp, then renormalize. Use these to place the virtual
  Sun and Earth on the Cesium globe (MOON_PA frame).
- `sun_lit` / `earth_los`: use the value of the nearest sample. Do not
  interpolate booleans. Render `null` as "unknown" (hatched), not dark.

### Countdown HUD (Simple Mode)

Take these from `evaluate_custom_site` or `countdowns_at_start`:

| Display | Field |
|---|---|
| "4d 18h of sunlight remaining" | `sun.time_to_sunset_formatted` when `sun.is_lit` |
| "Sunrise in …" | `sun.time_to_sunrise_formatted` when `sun.is_lit === false` |
| "Direct Earth contact: ACTIVE" | `earth.direct_los` |
| "Round-trip ping: 2.69 s" | `earth.round_trip_light_time_s` |
| "Solar power: PARTIAL (62% of the Sun visible)" | `sun.disk_visible_fraction` between 0 and 1 |
| "Radio link: MARGINAL (Earth partly behind terrain)" | `earth.disk_visible_fraction` between 0 and 1 |
| "> 29.5 days" | when `countdown_status` starts with `no_` |

While scrubbing, recompute the countdown from the track: find the next index
where `sun_lit` flips, and subtract `hours_from_start`. The events list gives
the exact times (precise to the second) for the original epoch.

### Horizon polar plot (Scientific Mode)

`terrain.horizon_mask.azimuth_deg` / `elevation_deg` is the LOLA skyline
(0° = north, clockwise). Overlay the track's `(sun_azimuth_deg,
sun_elevation_deg)` and Earth equivalents. `null` entries in the mask are
azimuths where the 100 km ray left every available DEM. Draw them as gaps.

### Manifest sync (`src/data/missions.ts`)

`origin/feature/frontend-systems:src/data/missions.ts` still contains the
fictional `ls-1` with a `PRIME-2` payload. Delete both. **Do not delete
`clps-prime-1-im2`**: PRIME-1 is NASA's real task order for IM-2 Athena.
Generate the frontend list from `data/missions.json` rather than
hand-copying it, and filter by `category` for the "Fleet" vs "Reference
anchors" groupings. Anchors carry `touchdown_utc` and `baseline_role`.

### Click-to-pin

Call `/sites/custom` with the picked lat/lon. Cesium returns cartographic
radians, so convert them to degrees and wrap longitude to [-180, 180]. Show
`terrain.status`, `terrain.dem_product` and `horizon_model`. Elevation is
`null` only when no terrain map covers the point.

## Research: validation workflow

Owner: `@Thirtha17`.

Pipeline values at the Issue #8 validation epochs: geometric (no
light-time/aberration correction), observer on the IAU reference ellipsoid,
mean-Earth (ME) coordinates, DE430 + `moon_pa_de421_1900-2050.bpc`. Azimuth
is measured clockwise from north.

| Site | Lat, Lon (ME) | UTC | Sun el | Sun az | Earth el | Earth az |
|---|---|---|---|---|---|---|
| Apollo 11 | 0.67416, 23.47314 | 1969-07-20T20:17:00Z | 10.692 | 88.805 | 59.225 | 272.194 |
| Chandrayaan-3 | -69.3741, 32.32 | 2023-08-23T12:34:00Z | 8.613 | 62.048 | 12.995 | 318.997 |
| IM-2 Mons Mouton | -84.79, 29.20 | 2026-11-15T12:00:00Z | 2.529 | 79.329 | 1.447 | 327.516 |

Reproduce:

```sh
python -c "from src.compute.spice_engine import *; load_kernels(); print(calculate_geometry(0.67416, 23.47314, '1969-07-20T20:17:00Z'))"
```

How to compare with JPL Horizons (https://ssd.jpl.nasa.gov/horizons/app.html):

1. Ephemeris type: **Observer Table**. Target body: `Sun [Sol] [10]` (then
   `Earth [399]`).
2. Observer location: **User-defined site on body 301 (Moon)**. Enter
   east longitude, latitude and altitude 0. Choose *planetocentric*
   coordinates to match the pipeline.
3. Time: the UTC above, step 1 minute. Quantity **4** (apparent Az/El).
   Set refraction to *airless*.
4. Horizons' apparent Az/El includes light-time and stellar aberration,
   while the pipeline is geometric (`"NONE"`). Expect differences of about
   0.005° for the Sun (aberration ~20″) and smaller for Earth. Differences
   above 0.1° indicate a frame or longitude-sign error.
5. Record version, settings and deltas in
   `data/validation/horizons_crosscheck.json`.

The reproducible batch comparison is implemented in
`src/ml/horizons_crosscheck.py`. Its official API source, exact query
parameters, cached reference responses, representative expected/reference
values, generated engine values, differences, and automated criteria are in
`data/validation/horizons_crosscheck.json`. The automated result supports
reproducibility only; it is not scientific approval.

### Human science handoff

`@Thirtha17`, the Horizons cross-check for this PR has been performed. The
real external reference data and citation are provided in
`data/validation/horizons_crosscheck.json`, with the reproducible comparison
implemented in `src/ml/horizons_crosscheck.py`. Please review the cited
Horizons data, query configuration, coordinate/reference assumptions,
methodology, and resulting comparison manually. The automated agreement is
intended to support reproducibility and does not constitute scientific
sign-off. The NASA PGDA solar and Earth visibility comparisons have the same
pending human-review status in their validation artifacts.

A historical sanity check already passes: Apollo 11 landed with a planned
low morning Sun (about 10–11°), and the pipeline gives 10.69°.
Chandrayaan-3's computed local sunset (12d 3h after touchdown, about
2023-09-04 15:30 UTC) is consistent with ISRO putting Vikram to sleep on
4 September 2023.

### Simple Mode science review notes

- The Moon's equator is inclined **1.54° to the ecliptic**. That angle,
  not the Moon's 6.7° tilt to its own orbit, sets how high the polar Sun
  climbs: at most about ±1.5° plus the local latitude offset.
- Earth's apparent motion is the optical libration envelope: about ±7.9°
  in longitude and ±6.7° in latitude. It is a Lissajous-like path, not a
  fixed ellipse.
- Shadow length: a 2,000 m rim at 1° Sun elevation casts
  `2000 / tan(1°) ≈ 115 km` on flat ground. The Issue #8 "50 km shadow" text
  corresponds to about 2.3°. Fix the copy, or tie the slider to `tan`
  directly.

## Downloading the global LOLA DEM (LDEM_64)

### Do you need it?

| You want… | Needed? |
|---|---|
| Terrain at catalog sites (Apollo, SLIM, Chang'e 4, Chandrayaan-3, Blue Ghost, …) | **No.** Run `git lfs pull` to get the committed site tiles |
| Terrain anywhere in 80–90°S | **No.** The 80 m polar DEM covers it (also via `git lfs pull`) |
| Terrain for custom clicks **outside 80–90°S**, away from catalog sites | **Yes** |
| Rebuilding the committed site tiles (`python -m src.compute.global_terrain`) | **Yes** |

Without it, custom clicks outside 80–90°S still work. They use a
smooth-Moon horizon and report `horizon_model: "spherical_horizon"`.

### The files

Both files are needed; the `.lbl` label describes how to read the `.img`.
Source: NASA PDS Geosciences Node, LRO LOLA GDR (`LRO-L-LOLA-3-RDR-V1`).

| File | Bytes | SHA-256 |
|---|---|---|
| `ldem_64.img` | 530,841,600 (≈ 531 MB) | `1c4958699d4cffd7e777d51421b6044bba300aa0bef286a544309efb082cdbd6` |
| `ldem_64.lbl` | 5,128 | `4e7a94c76c716a147b21ccf07669d004246b0d1b017b7d63d50befaa1a34142d` |

Both go in `cache/nasa/pds/`, which is git-ignored. **Never commit them.**

### Option A (recommended): one command

From the repository root, with the project's Python environment active:

```sh
python -m src.acquire.nasa_products lola_gdr_global_64ppd
```

This downloads both files, or reuses them if they are already present. It
then checks each file's size and SHA-256 against the values above, writes a
provenance record next to each file, and stops with an error on any
mismatch. To check an existing download without fetching:

```sh
python -m src.acquire.nasa_products lola_gdr_global_64ppd --status
```

Both files should report `"integrity_status": "VERIFIED"`.

### Option B: manual download with curl

Run from the repository root. `-C -` resumes an interrupted download, so
rerun the same command if it stops.

```sh
mkdir -p cache/nasa/pds
curl -fL -C - -o cache/nasa/pds/ldem_64.lbl https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.lbl
curl -fL -C - -o cache/nasa/pds/ldem_64.img https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img
```

Verify the checksums. Each line must print `OK`:

```sh
echo "1c4958699d4cffd7e777d51421b6044bba300aa0bef286a544309efb082cdbd6  cache/nasa/pds/ldem_64.img" | shasum -a 256 -c
echo "4e7a94c76c716a147b21ccf07669d004246b0d1b017b7d63d50befaa1a34142d  cache/nasa/pds/ldem_64.lbl" | shasum -a 256 -c
```

On Linux, `sha256sum -c` works the same way. On Windows PowerShell, use
`Get-FileHash cache\nasa\pds\ldem_64.img -Algorithm SHA256`. Then run the
`--status` command from Option A, which also records provenance.

**If a checksum fails:** delete the file and download it again. A
truncated download is the usual cause; check the size with `ls -l`. If it
fails a second time with the correct size, NASA may have reissued the
product. Do not edit the expected hash to make it pass; report it to the
data-pipeline owner, who will verify the new file before updating
`src/acquire/nasa_products.py`.

### After downloading

Nothing else is required. The pipeline detects `cache/nasa/pds/ldem_64.lbl`
automatically and builds a terrain tile on the fly (about 0.1–0.2 s) for
custom clicks outside 80–90°S. Results report `terrain.dem_product:
"LOLA GDR LDEM_64"`. Rebuild the committed tiles only if the manifest's
coordinates change:

```sh
python -m src.compute.global_terrain
python -m src.compute.precompute_tracks
```

## Known issues and open decisions

Items in the Issue #8 text that the pipeline deliberately does **not** follow
(zero-bluff rule):

| Issue #8 statement | Pipeline decision | Evidence |
|---|---|---|
| IM-1 Odysseus at 86.00°S, 4.00°E | Kept **80.13°S, 1.44°E** | NASA reports IM-1 landed near Malapert A at about 80.1°S |
| Griffin-1 / VIPER at 84.90°S, 31.60°W | Griffin landing coordinate kept `null`; Nobile crater centre (USGS: 85.28°S, 53.27°E) stored separately as `target_feature`, for map context only | NASA and Astrobotic name the Nobile region but publish no landing point. A crater centre is not a landing site, and Nobile's floor is largely shadowed, so computing a track there would mislead |
| VIPER flies on Griffin | **Wrong.** VIPER was cancelled in July 2024, then **revived in September 2025** on Blue Origin's second Blue Moon MK1 (task order **CS-7**, late 2027, delivery is a contract option). Added as `clps-cs7-blue-origin-viper` | [NASA release 25-064](https://www.nasa.gov/news-release/nasa-selects-blue-origin-to-deliver-viper-rover-to-moons-south-pole/) and NASA's Moon Base page. NASA's older *CLPS Providers* page still says "Griffin will deliver VIPER in 2024"; that stale page is the likely origin of the issue's claim |
| Blue Ghost-2 at Schrödinger, 75.00°S, 132.40°E | **Wrong site.** Blue Ghost Mission 2 (task order CS-3, NET 2027) targets **Nassau Crater** on the far side. Added as `clps-cs3-blue-ghost-2`, with the USGS crater centre (24.91°S, 177.34°E) as a `target_feature_reference` | [Firefly mission page](https://fireflyspace.com/missions/blue-ghost-mission-2/), NASA CLPS providers (CS-3), USGS Gazetteer. Schrödinger was Draper CP-12, now terminated |
| *(not in the issue)* Blue Moon MK1 "Endurance" | Added as `clps-blue-moon-mk1-endurance`: Shackleton Connecting Ridge, SCALPSS + LRA; no published coordinate or current date | NASA Moon Base page |
| SLIM "proved the need for slope envelopes" | Reworded | SLIM tipped over because a main engine lost thrust during descent; the slope was a contributing factor, not the cause |
| Apollo 11 "> 98% Earth visibility" | Not stated | Geometrically, Earth is visible 100% of the time at Tranquility Base; the pipeline reports the computed value |
| "50 km shadow" at 1° | Flagged for the science review | See above |

Pipeline limitations:

- **Global terrain is coarser.** Outside 80–90°S, horizons come from
  `LDEM_64` (~474 m/pixel), which resolves massifs (Apollo 17's horizon
  reaches 13.6°) but smooths nearby small craters. Published elevations
  check out: SLIM at −913 m vs LROC −912 m, and Chang'e 4 at −5,929 m vs
  −5,935 m (Liu et al. 2019); both are asserted in tests. For sharper
  nearside terrain, `LDEM_128` (237 m, 2.1 GB) uses the same converter.
- **Catalog values still waiting on publishers** (checked 2026-10-31):
  - **Blue Moon MK1 Endurance and VIPER:** NASA names the Shackleton
    Connecting Ridge and the "South Pole region" but publishes no landing
    coordinate. Endurance has no current launch date (NASA's 2025 "later this
    year" target slipped).
  - **Blue Ghost Mission 2:** Nassau Crater is named but no landing point, and
    the date is NET 2027 only; the crater centre is a map reference.
  - **Griffin-1:** NASA and Astrobotic name the Nobile region but publish no
    landing coordinate. Launch is no earlier than November 2026.
  - **IM-3** (Reiner Gamma) and **IM-4** (south pole): only target years
    are published, with no exact date.
  These get tracks automatically once the manifest has a coordinate and an
  exact date. Rerun `python -m src.compute.precompute_tracks`.
- **Draper CP-12 is terminated.** NASA and Draper ended the mission
  (SpaceNews, 2026-07-18). Its status is `terminated` and the track index
  reports `skipped_mission_terminated`. Hide it from the active fleet.
- **Touchdown precision.** IM-1 (23:23:53 UTC, LROC), Apollo 11 and
  Apollo 17 are to the second. Chandrayaan-3, Chang'e 4 and SLIM are to
  the minute.
- **Polar-edge sites mix two maps.** For sites near 80°S (IM-1 at 80.13°S),
  rays that run off the 80 m polar map are completed from `LDEM_64` for the
  same azimuth. `terrain.horizon_azimuths_filled_from_global` counts them
  (170 of 360 for IM-1), and `dem_product` says "edge fill".
- **Height convention trap (handled).** GDAL reports the PDS label's
  OFFSET of 1,737,400 m. Applying it would turn heights into radii, so the
  converter uses DN × 0.5 m only. It refuses any product whose scaling
  differs from that.
- The legacy `proximity.calculate_psr_distance` measures distance to the
  nearest PSR **boundary**, so a site inside a PSR reports a positive
  distance. New code should use `nearest_psr_within`, which reports
  `inside_psr`. The legacy function is unchanged for compatibility.
- `extract_horizon_mask_fast` (bilinear) and the legacy `extract_horizon_mask`
  (nearest pixel) differ by up to about 0.8° on rough terrain. The
  difference comes from the near-field (< 200 m) samples, and bilinear is
  the more faithful of the two.
- A shared pole-axis bug was fixed: within a few metres of ±90° latitude,
  the east axis used to be a skewed chord, which made horizon azimuths wrong
  and dropped rays. East is now built perpendicular to north (the projection
  is conformal).

## Regenerating and testing

```sh
python -m src.acquire.nasa_products lola_gdr_global_64ppd   # 531 MB global DEM, verified
python -m src.compute.global_terrain                  # rebuild committed site tiles
python -m src.compute.precompute_tracks               # 29.5-day tracks, ~3 s total
python -m src.acquire.usgs_nomenclature               # IAU crater subset for PSR names (24 MB, pinned sha256)
python -m src.compute.api_payloads                    # offline API fixtures (after precompute_tracks)
python -m src.compute.precompute_tracks --days 14 --step-minutes 30
python -m pip install -r requirements-dev.txt         # runtime deps + pytest
python -m pytest -q tests                             # or: python -m unittest discover -s tests
```

`tests/test_temporal_dynamics.py` covers the Issue #8 contracts: bilinear
exactness, the known wall angle, NaN propagation, pole rays, events being
true horizon crossings, countdown consistency, far-side Earth, the terrain
blocking rule, sub-hour steps, track physics, PSR-inside, custom-site and
launch-slip contracts, and manifest grounding. `tests/test_global_terrain.py`
covers the LDEM_64 height convention, the 0° longitude seam, refusal of
unexpected scaling, tile coverage, fallback, the PDS registry, and the
published-elevation checks for SLIM, Chang'e 4 and Taurus-Littrow.
