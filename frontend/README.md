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

## Data and honesty rules

- The mission list comes from `data/missions.json` (canonical IDs). Terminated missions are hidden.
- Sun/Earth geometry, countdowns and the scrubber come from the precomputed 29.5-day tracks.
- `null` is shown as "Unavailable", never as 0. Only `actual_landing` coordinates are labelled as landing fixes.
- No science value is hard-coded in the UI.

## Offline

Fonts, Cesium assets, coarse Moon tiles (levels 0-3), the catalog and the tracks are all bundled, so the app
works with the network off. Only the optional high-detail NASA Moon Trek tiles (levels 4+) need the internet;
they fail quietly when offline.

## Layout

- `src/data/missions.ts` catalog loader and `Mission` type
- `src/data/tracks.ts` track loader (`useTrack`)
- `src/data/timeline.ts` interpolation and countdowns
- `src/components/` globe, HUD (`SiteHud`), scrubber (`TimelineScrubber`), compare, inspector

Not built yet (needs the backend): live API client, click-to-pin, Date A vs Date B.
