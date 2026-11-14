# HarnessApollo frontend

React + TypeScript + Vite + CesiumJS. It reads the engine's static data, so it runs without a backend.

## Run

```sh
git lfs pull          # once, from the repo root: pulls data/ (tracks live in data/precomputed/tracks)
cd frontend
npm ci                # or npm install
npm run dev           # http://localhost:5173
```

`npm run dev` and `npm run build` first run `scripts/copy-data.mjs`, which copies `../data/missions.json`
and `../data/precomputed/tracks/` into `public/data/` (git-ignored), and copy Cesium's runtime assets.

Other scripts: `npm run build` (type-check + production build into `dist/`), `npm run preview`, `npm run lint`.

## Routes

- `/`: the gateway (the lobby from the original apolloharness.web.app placeholder). The clock counts down
  to the Space Apps window (2026-11-13 00:00 UTC) as `T-`, then counts mission elapsed time as `T+`.
  **Takeoff with us** plays a short rocket launch and opens the interface. The interface chunks are
  prefetched while the lobby is idle. With `prefers-reduced-motion`, it is a plain fade.
- `/app`: the mission interface. Firebase rewrites every path to `index.html`, so `/app` deep-links
  and reloads work, and browser Back returns to the lobby.

The lobby's backdrop is the live black-hole simulation from `vgpu.sh`, in an iframe over the static
`src/gateway/assets/space_bg.png`. It is the only part of the site that needs the network. Offline, the
static image shows.

## Data and honesty rules

- The mission list comes from `data/missions.json` (canonical IDs). Terminated missions are hidden.
- Sun/Earth geometry, countdowns and the scrubber come from the precomputed 29.5-day tracks.
- `null` is shown as "Unavailable", never as 0. Only `actual_landing` coordinates are labelled as landing fixes.
- No science value is hard-coded in the UI.

## Live engine

Precomputed data (catalog, mission tracks) is bundled with the site. The live engine on Render
(`https://apolloharness-api.onrender.com`, FastAPI in `backend/`) is called only for work nobody
precomputed:

- **Custom point:** click empty lunar surface, or **Analyse a point** to type coordinates →
  `/api/v1/sites/custom` (readout, events, terrain, PSR distance and a 29.5-day track for the HUD and scrubber).
- **Two launch dates** (Compare tab) → `/api/v1/sites/compare-dates`.

The header shows **Live engine**, **Starting live engine…** or **Offline data**. The lobby wakes the engine
when the site opens, because the free instance sleeps after 15 idle minutes. Slow steps show a "please wait"
with a timer; a cold start says so. With the engine unreachable, everything bundled keeps working.
The URL is the default in `src/data/api.ts`; override it at build time with `VITE_API_URL`, or set it empty
for an offline-only build.

## Offline

Apart from the gateway backdrop (above): fonts, Cesium assets, coarse Moon tiles (levels 0-3), the catalog and the tracks are all bundled, so the app
works with the network off. Only the optional high-detail NASA Moon Trek tiles (levels 4+) need the internet;
they fail quietly when offline.

## Layout

- `src/data/missions.ts` catalog loader and `Mission` type
- `src/data/tracks.ts` track loader (`useTrack`)
- `src/data/timeline.ts` interpolation and countdowns
- `src/Root.tsx` gateway / interface routing; `src/gateway/` the lobby and takeoff sequence
- `src/components/` globe, HUD (`SiteHud`), scrubber (`TimelineScrubber`), compare, inspector

- `src/data/api.ts` live-engine client and status; `src/components/CustomSiteDetails.tsx`, `PointForm.tsx`, `DateCompare.tsx`
