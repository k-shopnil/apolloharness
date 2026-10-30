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

## What is delivered

| Issue #8 item | Function / file | Notes |
|---|---|---|
| Horizon event root-finder | `spice_engine.find_horizon_events` | Sun and Earth rise/set against the LOLA terrain mask, bisection to 1 s |
| Operational countdowns | `find_horizon_events(...)["sun"/"earth"]` | Exact Issue #8 field names, plus status |
| Multi-day precomputation | `spice_engine.calculate_geometry_track`, `calculate_hourly_geometry(step_minutes=)` | Column arrays for a 60 FPS scrubber |
| Offline mission tracks | `python -m src.compute.precompute_tracks` → `data/precomputed/tracks/` | 29.5-day windows from touchdown |
| Arbitrary-coordinate interpolator | `terrain.interpolate_elevation`, `terrain.extract_horizon_mask_fast`, `terrain.evaluate_site_terrain` | Bilinear interpolation on `LDEM_80S_80MPP_ADJ.TIF`, with automatic fallback to the global LOLA GDR `LDEM_64` |
| Global terrain (beyond the issue) | `global_terrain.build_site_tile`, committed tiles in `data/lola/tiles/` | Real mountains at every catalog site, not only 80–90°S |
| Custom site, one call | `site_evaluation.evaluate_custom_site` | Measured 0.34–0.39 s per click |
| Launch-slip Date A vs Date B | `site_evaluation.compare_launch_dates` | Shared relative clock, delta summary |
| PSR proximity (interactive) | `proximity.nearest_psr_within` | Reports `inside_psr` and 0 m inside a cold trap |
| Manifest grounding | `data/missions.json`, `demo_fixtures/missions.json` | 8 CLPS + 5 sourced reference anchors, each with `payload_summary` |

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
4. **Visibility rule.** A body is up when its **centre** elevation is above
   the terrain horizon at its azimuth. The Sun is modelled as a point; its disk
   radius of ~0.27° is not included, so a limb can be visible up to a few hours
   before the reported "sunrise" at grazing polar angles. Earth LOS is
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

> SPICE (CSPICE) is not thread-safe. Run these calls in one worker thread,
> or guard them with a `threading.Lock`. Do not run them concurrently in
> FastAPI's default threadpool.

### `GET /api/v1/sites/custom?lat=&lon=&utc=`

```python
@router.get("/sites/custom")
def custom_site(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
                utc: str | None = None, include_psr: bool = False, include_track: bool = False):
    utc = utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with SPICE_LOCK:
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
  "sun": {"azimuth_deg": 79.329, "elevation_deg": 2.529, "terrain_horizon_deg": 2.48,
          "is_lit": true, "time_to_sunset_hours": 367.08, "time_to_sunset_formatted": "15d 7h",
          "time_to_sunrise_hours": null, "time_to_sunrise_formatted": null,
          "countdown_status": "complete", "fraction_of_window_up": 0.518},
  "earth": {"azimuth_deg": 327.516, "elevation_deg": 1.447, "terrain_horizon_deg": -1.451,
            "direct_los": true, "time_to_earthset_hours": 452.883,
            "time_to_earthset_formatted": "18d 20h", "time_to_earthrise_hours": null,
            "time_to_earthrise_formatted": null, "countdown_status": "complete",
            "fraction_of_window_up": 0.824, "range_km": 403845.7, "round_trip_light_time_s": 2.694},
  "events": [{"body": "sun", "kind": "set", "utc": "2026-11-30T19:04:47Z", "hours_from_start": 367.0797},
             {"body": "earth", "kind": "set", "utc": "2026-12-04T08:52:59Z", "hours_from_start": 452.8832}],
  "annual_illumination": {"status": "complete", "annual_sunlight_percent": 46.55,
                          "source_dataset": "AVGVISIB_85S_060M_201608.TIF"},
  "psr": {"status": "not_requested", "distance_m": null, "inside_psr": null}
}
```

(Real output; arrays trimmed.) In this case the Sun clears the LOLA skyline by
only 0.05°, which is less than the solar radius. This is the knife-edge case
the launch-slip view exists for, and Scientific Mode should show the margin
`elevation_deg - terrain_horizon_deg`.

Latency: about 0.35 s per call. `include_psr=true` adds about 1.2 s because
it reads the vector dataset, so request it after the click (lazy load), not
on it.

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
frontend overlays them directly. Measured: about 0.5 s for two 14-day windows.

### Extending `/api/v1/sites/geometry`

Merge `find_horizon_events(lat, lon, utc)["sun"|"earth"]` (the default
`horizon_mask="auto"` loads the LOLA mask itself; pass `horizon_mask=mask` to
reuse one you already have)
into the Issue #7 payload. For mission sites, prefer reading the countdown at
mission start from `data/precomputed/tracks/<id>.json → countdowns_at_start`.

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
110 KB) and is safe to bundle for offline demos.

```ts
type Track = {
  schema: "apolloharness.geometry_track.v1";
  start_utc: string; step_minutes: number; samples: number;
  horizon_model: "lola_terrain_mask" | "spherical_horizon";
  sunlit_percent: number | null; earth_los_percent: number | null;
  columns: {
    utc: string[]; hours_from_start: number[];
    sun_elevation_deg: number[]; sun_azimuth_deg: number[];
    sun_terrain_horizon_deg: (number | null)[]; sun_lit: (boolean | null)[];
    earth_elevation_deg: number[]; earth_azimuth_deg: number[];
    earth_terrain_horizon_deg: (number | null)[]; earth_los: (boolean | null)[];
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
| "> 29.5 days" | when `countdown_status` starts with `no_` |

While scrubbing, recompute the countdown from the track: find the next index
where `sun_lit` flips, and subtract `hours_from_start`. The events list gives
the exact times (precise to the second) for the original epoch.

### Horizon polar plot (Scientific Mode)

`terrain.horizon_mask.azimuth_deg` / `elevation_deg` is the LOLA skyline
(0° = north, clockwise). Overlay the track's `(sun_azimuth_deg,
sun_elevation_deg)` and Earth equivalents. `null` entries in the mask are
azimuths where the 50 km ray left the DEM. Draw them as gaps.

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
5. Record version, settings and deltas in `docs/SCIENTIFIC_VALIDATION_REPORT.md`.

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
| Griffin-1 / VIPER at 84.90°S, 31.60°W | Coordinate kept `null`; VIPER is not on Griffin | Cited NASA sources name Nobile but publish no coordinate; VIPER was removed from Griffin |
| Blue Ghost-2, Schrödinger 75.00°S, 132.40°E | Not added | No NASA source with a coordinate found yet; CP-12 Draper already references the Schrödinger basin |
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
python -m src.compute.precompute_tracks --days 14 --step-minutes 30
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
