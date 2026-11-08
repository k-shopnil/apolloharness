# Issue #8 – Analysis for Fahim (ASMFahim71, Frontend)

Audited 2026-11-07 against branch `feature/frontend-systems` (local working tree, including your uncommitted edits).
Event is **13–15 Nov 2026**. Prep must be done by **12 Nov**. That is 5 days from today.

---

# PART 1 – The basics (plain-language glossary)

## 1.1 What is this project, in one paragraph?

**HarnessApollo** is a web app that helps people choose and understand **landing sites on the Moon**. NASA's Space Apps 2026 challenge ("Lunar Landing Site Navigator") asks teams to build such a tool.

The tool must answer questions like:
- Will the Sun shine on this spot, and for how long?
- Can we talk to Earth from here (is Earth above the horizon)?
- What happens if the launch is delayed by 3 days?

The project has three layers:

```
[Python science engine]  ->  [FastAPI backend]  ->  [Your React + Cesium frontend]
 (Mehedi, DONE)              (Ariful/Eetherr77)       (YOU)
 computes Sun/Earth          serves it as JSON        draws globe, HUD,
 positions from NASA data    over HTTP                scrubber, compare
```

## 1.2 Space and science terms

| Term | Plain meaning |
| :--- | :--- |
| **CLPS** | *Commercial Lunar Payload Services*. NASA pays private companies (Intuitive Machines, Firefly, Astrobotic, Blue Origin) to deliver cargo to the Moon. Those missions are our "fleet". |
| **Lander** | The spacecraft that touches down on the Moon. |
| **Rover** | A wheeled robot the lander carries (e.g. VIPER, Yutu-2). |
| **Anchor / reference anchor** | A past real landing (Apollo 11, Apollo 17, Chandrayaan-3, Chang'e 4, SLIM) used as a yardstick: "how does my new site compare to a known one?" |
| **Selenographic lat/lon** | Latitude/longitude on the Moon (like Earth's, but for the Moon). South is negative. |
| **Lunar south pole** | The area NASA wants to visit. Sun is always low on the horizon there, so shadows are long. |
| **Sun elevation** | Angle of the Sun above the horizon. 0° = on the horizon, 90° = straight overhead. At the poles it's only 0–3°. |
| **Azimuth** | Compass direction (0° = north, 90° = east). "Sun azimuth 79°" means the Sun is to the east-north-east. |
| **Terrain horizon** | The skyline from the site, including hills and crater rims. The Sun is only really visible if its elevation is **above** this skyline. |
| **Horizon margin** | `elevation − terrain horizon`. Positive = visible, negative = blocked by terrain. |
| **`disk_visible_fraction`** | The Sun is a disc, not a point. When it's half behind a hill, this is ~0.5. Used for "62% of the Sun visible". |
| **Sunset / Sunrise countdown** | How long until the Sun drops below the terrain skyline. Lunar day = ~29.5 Earth days, so sunlight can last days. |
| **Earthset** | Same idea for Earth: when Earth drops below the horizon and you lose direct radio contact. |
| **Lunation / synodic month** | One full Moon cycle = **29.5 days**. The "29.5-day scrubber" slides across exactly this period. |
| **Libration** | Earth seems to wobble slowly in the Moon's sky (~±7°) because of the Moon's orbit and tilt. That is why Earth can drift in and out of view near the edge. |
| **PSR (Permanently Shadowed Region)** | A crater floor that never sees sunlight. Very cold (≈ −200 °C), may hold water ice. Valuable for science, bad for solar power. |
| **Cold trap** | Same thing, viewed as "a place where ice can survive". |
| **DTE (Direct-To-Earth)** | A radio link straight from the lander to Earth, with no relay satellite. |
| **LoS (Line of Sight)** | A straight, unblocked line between two things. `direct_los = true` means the lander can "see" Earth. |
| **Occulted** | Blocked. "Earth occulted" = the Moon's body is in the way. |
| **Round-trip light time** | Time for a signal to go Moon→Earth→Moon. About 2.5–2.7 s. A sanity-check number (valid range 2.3–2.8 s). |
| **Far side** | The Moon side never facing Earth. No DTE possible, so a relay satellite is needed (Chang'e 4, Blue Ghost-2). |
| **Slope** | Steepness of the ground in degrees. Landers tip over on steep ground. Envelope: <8° OK, 8–12° caution, >12° critical. |
| **Landing ellipse** | The oval on the ground where a lander is predicted to land. If unpublished, show **unknown**, never invent one. |
| **`coordinate_type`** | Says how trustworthy a coordinate is: `actual_landing` (really landed there) vs target/region centre (only a reference). **Only `actual_landing` may be called a landing fix.** |

## 1.3 Data and software terms

| Term | Plain meaning |
| :--- | :--- |
| **SPICE (NAIF)** | NASA's library for computing where planets/moons/spacecraft are at any time. Mehedi's engine uses it to get Sun & Earth positions. |
| **LOLA** | *Lunar Orbiter Laser Altimeter*. NASA instrument that measured Moon terrain height. Gives the terrain horizon. |
| **DEM** | *Digital Elevation Model*. A height map of the terrain. |
| **PGDA 69** | NASA's published illumination data. The team uses it to validate its own numbers. |
| **JPL Horizons** | NASA's public ephemeris website. Used to cross-check our numbers. |
| **`MOON_PA` / ME** | Two coordinate frames of the Moon (Principal Axis vs Mean Earth). Just use the vectors as delivered. Thirtha writes a paragraph explaining the difference. |
| **Ephemeris** | A table of "where is body X at time T". Your `src/data/ephemeris.ts` is a *fake local version* of this. |
| **Unit vector** | An arrow of length 1 pointing at something. `sun_unit_moon_pa` = arrow from the Moon's centre toward the Sun. You use it to place the Sun on the globe. |
| **Precomputed track** | A static JSON file with 29.5 days × hourly samples for a site (Sun/Earth elevation, azimuth, vectors, flags). No backend needed. 9 missions have one in `data/precomputed/tracks/`. |
| **`countdowns_at_start`** | Inside a track file: time to sunset/Earthset at the start of the window. |
| **`horizon_model`** | Tells whether the terrain was modelled (`lola_terrain_mask`) or not (`spherical_horizon`). The UI must show it. |
| **`null`** | "Unknown". Never display it as 0. |
| **Git LFS** | Git's mechanism for big files (terrain tiles, kernels). Needs `git lfs pull`. |
| **FastAPI** | Python web framework used by the backend. |
| **CORS** | Browser security rule. The backend must allow your site's URL, otherwise `fetch` is blocked. |
| **`VITE_API_URL`** | Env variable your frontend reads to know where the backend lives (default `http://localhost:8000`). |
| **Cesium** | JavaScript 3D globe library (already used in `MoonGlobe.tsx`). |
| **Entity / billboard / polyline (Cesium)** | Objects you draw: an *entity* is a thing on the globe, a *billboard* is a 2D icon in 3D space, a *polyline* is a line (the beam). |
| **Lerp** | Linear interpolation: smoothly blend between two sample values (for scrubber between hourly samples). |
| **Shortest-arc azimuth** | When blending 350° → 10°, go through 0° (20° gap), not back through 180°. |
| **Static fallback / offline mode** | If the backend is down, the app reads local JSON files and shows an "Offline mode" badge. Required for the demo. |

## 1.4 Terms from the issue structure

| Term | Meaning |
| :--- | :--- |
| **Deliverable A–D** | The four feature groups: A dual mode, B fleet, C custom coordinates, D time dynamics. |
| **Must-have vs stretch** | Must-have = needed for the demo. Stretch = only if time remains. Anything stretch not merged by 12 Nov is cut. |
| **Zero invented data / data honesty** | Every number on screen must come from the engine or the data files. No made-up percentages, ellipses or placeholder distances. |
| **Canonical ID** | The official mission id from `data/missions.json` (e.g. `clps-prime-1-im2`). Your current ids (`im-2`, `griffin-1`) are NOT canonical. |
| **Date A vs Date B** | "Launch slip" comparison: same site, two dates. |
| **Simple Mode / Scientific Mode** | Same app, two levels of detail. Simple = classroom, plain words. Scientific = planners, exact numbers. |
| **Day-1 draft PR** | Backend pushes a draft PR early with real sample outputs so you can code against real JSON. |
| **Merge vs rebase** | On shared branches use `git merge origin/main` only. Single-owner branches (like yours) may rebase. |

---

# PART 2 – What the issue wants from YOU (§4.3 and related)

Your assignment is **§4.3 Frontend & 3D Visualization**, plus the frontend parts of §8.

**Can start now (no backend needed):**
1. Move the app into `frontend/` and rebase onto `main`.
2. Manifest alignment: loader over `data/missions.json`, canonical IDs, delete `ls-1`/`xl-1`/`PRIME-2` and hardcoded viability numbers, hide terminated CP-12, respect `coordinate_type`.
3. `TimelineScrubber.tsx` (29.5 days) on precomputed tracks.
4. Virtual Earth, directional Sun, DTE beam, layer toggles.
5. Dual-mode header (Simple/Scientific), state in `App.tsx`.
6. Simple Mode countdown HUD + Scientific telemetry panel.

**After the backend PR lands:**
7. API client with static fallback and an "Offline mode" badge (`VITE_API_URL`).
8. Click-to-pin on the globe + coordinate modal -> `/sites/custom`.
9. Date A vs Date B in `CompareView.tsx` -> `/sites/compare-dates`.
10. PR to `main` with a clean `npm run build`.

**Also on you (§8):** one shared TypeScript `Mission` type from the flat `/missions` shape; feed `include_track` data to `TimelineScrubber`; hide "Lander Footing" badge unless slope exists (§8.4).

---

# PART 3 – Audit: what is built vs what is missing

## 3.1 Current state of the repo

- Branch `feature/frontend-systems`, one commit `65b4e3d firstcommit`. Not yet rebased on `main`.
- **The app is at the repo root** (not in `frontend/`). The `data/`, `offline_fixtures/`, `docs/` folders from `main` do not exist here, so the real data is not available yet.
- Uncommitted work (yours): `MoonGlobe.tsx`/`.css` modified, new `SiteTelemetryCard.tsx`, new `src/data/ephemeris.ts`.
- Stack: React 19, Vite, TypeScript, Cesium 1.146. No router, no state library, **zero `fetch` calls**.

## 3.2 Checklist against the issue

| # | Item (issue ref) | Status | Evidence / notes |
| :-: | :--- | :-: | :--- |
| 1 | Globe with mission pins (Cesium) | ✅ Built | `MoonGlobe.tsx` (600 lines), local tiles via `scripts/fetch-tiles.mjs` |
| 2 | Fleet sidebar, mission drawer, filter tabs | ✅ Built | `FleetSidebar`, `MissionDrawer`, `Header` tabs |
| 3 | Site inspector screen, compare-sites screen, provenance modal | ✅ Built (UI shell) | `SiteView.tsx`, `CompareView.tsx`, `ProvenanceModal.tsx` – but values are hardcoded |
| 4 | Virtual Earth on the globe (§2 carry-over #7) | 🟡 Built, **fake data** | Earth billboard added in `MoonGlobe.tsx` at a fixed point (lat 1.5, lon 2.0) from `ephemeris.ts` FIXTURE |
| 5 | Directional Sun | 🟡 Built, **fake data** | Fixed point (lat -1.1, lon 38.0). Dashed amber solar vector exists |
| 6 | DTE LoS beam (cyan when LOS, red dashed when occulted) | 🟡 Built, **fake data** | Colour logic done. LOS is derived from the simple fixture, not from `earth_los` in tracks |
| 7 | Layer toggles `DTE LoS Beam`, `Solar Vectors` | ✅ Built | `globe__layers` checkboxes |
| 8 | Site HUD above the active site | 🟡 Built, partially fake | `SiteTelemetryCard.tsx`: sun elev, earth elev, comms status. **PSR distance is the hardcoded `viability.psrKm`**. No countdowns |
| 9 | Dual-mode header (Simple / Scientific) | ❌ Not started | `Header.tsx` has only filter tabs and a static "NASA PDS · OFFLINE CACHED" label. No `UIMode` type |
| 10 | Simple Mode countdown HUD (sunlight remaining, Earth contact + ping) | ❌ Not started | no countdown anywhere |
| 11 | Plain-language badges (Solar / Radio / Footing) | ❌ Not started | the card has NOMINAL/MARGINAL labels, not the required wording |
| 12 | Scientific telemetry panel (az/el, horizon, margin, disc fraction, vectors) | ❌ Not started | |
| 13 | 29.5-day `TimelineScrubber.tsx` | ❌ Not started | file does not exist |
| 14 | Manifest from `data/missions.json`, canonical IDs | ❌ Not started | `missions.ts` is a hand-written 352-line file |
| 15 | Delete fictional `ls-1`, `xl-1`, `PRIME-2` | ❌ Not done | `ls-1` and `xl-1` still in `missions.ts` (lines ~240, ~272); `App.tsx` also hardcodes `griffin-1`, IM-2 coordinates |
| 16 | Remove hardcoded science numbers | ❌ Fails "zero invented data" | viability %, scores, ellipse `5km × 3km` text in `SiteView.tsx`, `FILTERED_BRIEF` text in `compare.ts` (e.g. "82%", "71% vs 89%") |
| 17 | Respect `coordinate_type`, hide terminated CP-12 | ❌ Not started | |
| 18 | API client + static fallback + "Offline mode" badge | ❌ Not started | no `fetch`, no `VITE_API_URL` |
| 19 | Click-to-pin (LEFT_CLICK raycast to lat/lon) | ❌ Not started | |
| 20 | Coordinate modal (lat/lon/UTC) | ❌ Not started | |
| 21 | Date A vs Date B tab in `CompareView` | ❌ Not started | CompareView compares **sites** only |
| 22 | Shared `Mission` TS type from flat `/missions` | ❌ Not started | current `Mission` type is a custom design-file shape |
| 23 | App moved into `frontend/` | ❌ Not started | |
| 24 | Rebase onto `main` + `git lfs pull` | ❌ Not started | |
| 25 | `npm run build` clean | ❓ Unverified | `dist/` exists, but your uncommitted changes are not confirmed to compile |
| 26 | Build step copying `data/precomputed/tracks/` into public folder | ❌ Not started | Mehedi owes this; you need it to read tracks |
| 27 | Show `horizon_model` and `terrain.dem_product` in the UI | ❌ Not started | |
| 28 | `null` shown as "Unavailable – reason" | ❌ Not started | |

Legend: ✅ done · 🟡 started, but on fake data · ❌ missing · ❓ unknown

## 3.3 What is good about the current code
- Visual shell (globe, sidebar, drawer, compare, provenance) already exists, so real data can be plugged into existing components.
- Earth/Sun/beam/telemetry-card **rendering code is reusable**. Only the data source (`getEphemeris()`) needs to change. The comment in `ephemeris.ts` already says "swap `getEphemeris()` for an API call later".
- Lazy-loading Cesium and responsive hook (`useMediaQuery`) are already in place.

## 3.4 What breaks the rules right now (fix first)
1. `ephemeris.ts` FIXTURE: invented sub-Earth and sub-solar points. Breaks rule 6 (no hardcoded science values).
2. `siteTelemetry()` thresholds (`>= 1.5` NOMINAL, `< 2` LOW) are invented; and it ignores the terrain horizon. Per the issue, use the horizon margin and `disk_visible_fraction`.
3. `missions.ts`: fictional missions, fixed scores and viability, `dataStatus: 'placeholder'`.
4. `SiteView.tsx` prints fixed text such as "5km × 3km LANDING ELLIPSE" and "Sun Azimuth: 042°".
5. `compare.ts` hand-written brief with percentages.
6. `App.tsx` `hudByFilter` prints fixed lat/lon and "LOLA 20m DEM".
7. Only `im-2` is inspectable (`INSPECTABLE` set).
8. A single sun/earth position is used for all sites (a Sun/Earth direction should come per time, from the track).

---

# PART 4 – Recommended work plan (5 days to 12 Nov)

Order matters. Do the data foundation first; everything depends on it.

## Day 1 (today, 7 Nov) – Foundation
1. Commit your current uncommitted work on a WIP commit (so nothing is lost).
2. `git fetch origin && git rebase origin/main` (your branch is single-owner, rebase is allowed). Run `git lfs pull`.
3. Move the app into `frontend/` (package.json, src, public, scripts, vite config, tsconfigs, index.html).
4. Confirm `npm run build` passes. Fix TS errors.
5. Read `docs/TEAM_INTEGRATION_GUIDE.md` (track file format, Countdown HUD mapping, Timeline scrubber recipe).
6. Add a build/dev script that copies `data/precomputed/tracks/` and `data/missions.json` into `frontend/public/` (or asks Mehedi for it).

## Day 2 – Real data in the existing UI
7. Define the shared `Mission` TS type from the flat `/missions` shape.
8. Write a `loadMissions()` loader over `missions.json` (offline source) with canonical IDs; hide CP-12; mark `coordinate_type`.
9. Rewire `FleetSidebar`, `MoonGlobe`, `MissionDrawer`, `CompareView` to the new type. Delete fiction (`ls-1`, `xl-1`, `PRIME-2`, scores, viability, ellipses).
10. Missions without coordinates (Griffin, VIPER, Endurance): show in the list as "No coordinate published", not as pins.

## Day 3 – Core must-haves
11. `TimelineScrubber.tsx`: load a track, lerp elevations, shortest-arc azimuth, renormalise unit vectors, nearest sample for booleans, `null` = hatched "unknown".
12. Replace `ephemeris.ts` fixture with the track-driven sample at the scrubber time (`sun_unit_moon_pa`, `earth_unit_moon_pa`, `earth_los`).
13. `UIMode` switch in `Header.tsx`, state in `App.tsx`.
14. Simple Mode HUD (countdowns, plain badges) and Scientific panel (az/el, horizon, margin, disc fraction, `horizon_model`, `dem_product`).

## Day 4 – API connection (after backend PR)
15. API client with `VITE_API_URL`, timeout, static fallback and "Offline mode" badge.
16. Click-to-pin + coordinate modal -> `/sites/custom` (with `include_track=true` for the scrubber).
17. Date A vs Date B tab in `CompareView` -> `/sites/compare-dates`.

## Day 5 (11–12 Nov) – Harden
18. Test with network off (offline demo must work). Test phone width.
19. `npm run build` clean, open PR to `main`. Reviewers: Eetherr77 (API client) + Thirtha (Simple Mode wording).
20. Skip all stretch items (STEM sandboxes, polar plot, dossier export...) unless everything above is merged.

---

# PART 5 – Dependencies and risks

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| Backend not merged yet (critical path is Ariful/Eetherr77) | Items 15–17 blocked | Build everything on static tracks first; ask Eetherr77 for the **day-1 draft PR with sample JSON** (§8.1) and code against it |
| `data/` not in your branch | You cannot read tracks | Rebase + `git lfs pull` today |
| Track-copy build step missing | Scrubber can't load files | Add the copy script yourself (small), tell Mehedi |
| Only 9 of 16 missions have tracks | Scrubber for the others | Show "no precomputed track" for them, or use a custom call. Never fake. |
| Big `Mission` type rewrite touches every component | Regressions | Do it in one commit, keep `npm run build` green |
| Slope not available for single sites (§8.4) | "Lander Footing" badge | Keep it hidden until Mehedi decides |
| "50 km shadow" figure flagged | Wrong science on screen | Do not show it (stretch item anyway) |
| Time (5 days) | Scope | Only must-haves (§6). Everything stretch is cut |

# Questions to confirm with the team
1. Does Mehedi's copy-tracks build step exist yet, or should you write it?
2. Exact Firebase URL for CORS (Ariful) and for deploy.
3. Is Fahim expected to author the shared `Mission` type before the backend finalises the shape? (Issue says yes, from `offline_fixtures/site_geometry/missions.json`.)
4. Humayra's role (demo script / offline checklist) is still "to be confirmed".

---

# One-line summary

**Built:** the visual shell (globe, sidebar, drawer, compare, provenance) plus a first version of Earth/Sun/beam/layer-toggles/HUD card, all running on **invented local data**.
**Missing:** real data/manifest, canonical IDs, `frontend/` move, rebase, dual-mode, countdown HUD, scientific panel, 29.5-day scrubber, API client + offline mode, click-to-pin, coordinate modal, Date A vs B, and removal of every hardcoded science number.
**Next step today:** commit your WIP, rebase on `main`, pull LFS, move the app to `frontend/`, get a green build.
