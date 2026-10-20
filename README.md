<div align="center">

<img src="./harness_mark_white_affiliation.png" alt="HarnessApollo Header" width="700" />

  <br /><br />

  <a href="https://www.spaceappschallenge.org/2026/challenges/clps-lunar-mission-browser/">
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

**HarnessApollo** is an environmental intelligence initiative developed for the **NASA Space Apps Challenge 2026** (Challenge #4: *Commercial Lunar Payload Services (CLPS) Lunar Mission Browser*).

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
`demo_fixtures/missions.json`. The current catalog contains eight CLPS mission
records. Coordinates are references with an explicit `coordinate_type`; a
target or region center must not be interpreted as an achieved landing point.
Dates containing only a year are target years, not exact dates.

### Sources, datasets, and coordinate assumptions

The required SPICE kernels are `data/spice/naif0012.tls` (UTC/leap seconds),
`pck00010.tpc` (body constants), `moon_080317.tf` (lunar frame definitions),
`moon_pa_de421_1900-2050.bpc` (Moon PA orientation), and `de430.bsp` (solar
system ephemerides). The large binary kernels are ignored by Git; obtain the
same named kernels from NAIF's generic kernels and place them in `data/spice/`.
SPICE calculations use `MOON_PA`, east-positive
longitude, planetocentric latitude converted through the Moon radii, and
geometric (no aberration correction) line of sight. Earth visibility is a
spherical-horizon test. It does not include terrain masking, lander antenna
constraints, or relay availability.

Terrain analysis accepts an externally downloaded LOLA elevation GeoTIFF in a
projected lunar CRS with meter axes. A NASA GSFC PGDA South Pole LOLA DEM Mosaic
provides GeoTIFFs in south polar stereographic X/Y coordinates; its product
page documents the resolution and frame: [PGDA product 81](https://pgda.gsfc.nasa.gov/products/81).
The newer [PGDA LOLA south-pole product 90](https://pgda.gsfc.nasa.gov/products/90)
also provides COG GeoTIFFs. Download a suitable subset/mosaic and store it
locally under `data/lola/` (or provide an explicit path to
`extract_horizon_mask`). Do not commit these large rasters. The sampler uses the
raster's declared projected CRS and interprets coordinates with a spherical
Moon radius of 1,737,400 m; verify datum/frame compatibility for any selected
product before interpreting results. Its 360-degree output is an observer
height and radial-step dependent local horizon approximation.

Annual illumination is a distinct strategic product and is read from a local
LROC/LOLA annual illumination raster. NASA's [PGDA lunar polar illumination
products](https://pgda.gsfc.nasa.gov/products/69) describe available long-term
products and cloud-optimized GeoTIFFs. Put the selected south-pole product at
`data/illumination/annual_south_pole.tif`, or pass its path to
`annual_illumination`. Raster values in 0–1 are interpreted as fractions and
values above 1 as percent. Keep product identity and units with downloaded data.
The API will report a missing product; it does not substitute tactical
illumination or invent a value.

PSR proximity requires authoritative polygon boundaries, placed at
`data/psr/psr_boundaries.gpkg` or passed to `nearest_psr`. The input vector must
declare its CRS. Distances are calculated after projection to a south-polar
stereographic metric CRS (`MOON_SPS`), not from latitude/longitude differences.
No PSR boundaries are currently bundled, so this calculation is unavailable
until a sourced dataset is installed.

### Offline operation and reproducibility

`src/acquire/safe.py` implements online → `cache/` → committed fixture fallback
for JSON and file downloads. The committed mission JSON fixture keeps the
mission catalog available offline; compute modules that depend on binary
ephemerides still require the local SPICE kernels. Downloaded rasters and PSR
vectors are ignored by Git and are not currently represented by invented demo
values. Analysis output includes its analysis type and source path. For
reproducibility, record the exact source product/version, kernel filenames,
observer coordinate convention, DEM sampling parameters, and mission start and
duration with each result.

Install pinned dependencies with `python -m pip install -r requirements.txt`.
Run an offline geometry example from the repository root with:

```sh
python -m src.compute.spice_engine
```

LOLA tactical illumination can be called from Python using
`extract_horizon_mask(...)` and `calculate_tactical_illumination(...)`;
annual illumination and PSR distance are exposed as
`annual_illumination(...)` and `nearest_psr(...)`. The compute API raises a
clear `FileNotFoundError` when its scientific input product is not installed.
Run the included checks with `.venv/bin/python -m unittest discover -s tests -v`
and use `.venv/bin/python -m compileall src` for a syntax check. No project-specific benchmark
dataset or scientific validation document is currently included; benchmark
values must not be claimed until the matching input products and time windows
are identified and run.

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
