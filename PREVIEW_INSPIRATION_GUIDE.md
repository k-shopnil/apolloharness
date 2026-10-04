# Apollo Harness — Frontend Preview & Inspiration Guide for Fahim

Welcome Fahim! This `preview` branch contains the interactive mission control prototype and reference architecture for Apollo Harness. Use this as your base file and inspiration for building out the frontend components described in `TEAM_DIRECTIVES_OCT4.txt`.

---

## 🚀 Quickstart: Running the Preview

To run this preview locally:

```bash
# 1. Install dependencies
npm install

# 2. Start Vite development server
npm run dev
```

Visit `http://localhost:5173` in your browser.

---

## 🗺️ What This Preview Implements

This codebase fulfills the Sprint 1 & 2 requirements and provides production-ready UI patterns:

### 1. 3D CesiumJS Lunar Globe (`CesiumMoonViewer` in `App.tsx`)
- Configured specifically for the lunar ellipsoid: `Cesium.Ellipsoid.default = Cesium.Ellipsoid.MOON` (1,737,400 m radius).
- Streams official Cesium Moon 3D Tileset (Ion Asset `2684829`) with high-resolution polar topography and craters.
- Interactive camera controls:
  - Global polar view: Centered at `84.79°S, 29.20°E` at 4,500 km altitude.
  - Site inspection zoom: Flies down to Mons Mouton at 85 km altitude with angled pitch (`-55°`) for 3D terrain profile inspection.
- Tactical 2D polar orthographic grid mode switch with LOLA 20m DEM vector projection.

### 2. CLPS Fleet Manifest & Filtering (Screen 1)
- Category filter buttons: **All Missions (7)**, **★ Volatiles & Drills (3)**, and **Rovers & Mobility (2)**.
- Filtering automatically highlights south-polar volatiles targets (e.g. IM-2 Nova-C at Mons Mouton).
- Interactive landing site beacons and clickable mission cards that link directly into the site inspector.

### 3. Site Inspector & Tactical Telemetry (Screen 2)
- High-fidelity tactical overlays:
  - **Landing Ellipse**: 1px dashed safety boundary (`rx: 100px, ry: 58px`).
  - **Sun Direction Vector**: Real-time calculated subsolar bearing and elevation angle (`+1.8°`).
  - **Earth Line-of-Sight (LOS) Vector**: Direct Earth communications ray (`+3.2° above horizon`).
  - **PSR Mask Toggle**: Permanently Shadowed Region cold trap boundaries.
- **Environmental Viability Index Card**:
  - Overall Viability Score (`79/100`).
  - Progress bars for **Solar Illumination** (`82.0%`), **Ice Proximity** (`1.2 km`), and **Direct-to-Earth Comms** (`94.5%`).

### 4. Side-by-Side Site Comparison (Screen 3)
- Direct comparison matrix comparing **IM-2 Nova-C Athena** vs. **Astrobotic Griffin-1**.
- Detailed metric evaluations across solar illumination, slope safety, communication uptime, and water-ice access.

### 5. UI Architecture & Styling
- **Liquid Frosted Glass Header**: Floating translucent glass header with specular highlights and centered tabs.
- **Aerospace Design Language**: JetBrains Mono telemetry typography, high-contrast dark theme (`#000000`, `#09090B`, `#27272A`), and NASA safety orange (`#FF4D00`) accents.
- **Zero-Scroll Viewport**: Strict `100vh` dashboard container preventing layout jitter during 3D camera navigation.

---

## 📁 Key Files to Explore

- **`App.tsx`**: Complete interactive React implementation containing all 4 screens, Cesium viewer, tactical SVG overlays, and state controllers.
- **`index.html`**: CesiumJS CDN dependencies, custom scrollbars, and styling optimizations.
- **`prototype/index.html`**: Standalone zero-dependency vanilla JS prototype if you want to inspect raw CesiumJS calls.
- **`vite.config.ts`**: Vite configuration.

Happy coding! Reach out to the team if you have any questions on data schemas or integration.
