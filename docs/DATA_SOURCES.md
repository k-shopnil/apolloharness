# Scientific data sources and provenance

Project challenge: **NASA Space Apps Challenge 2026 — Lunar Landing Site Navigator**.

This document is the human-readable companion to
[`data/validation/data_provenance.json`](../data/validation/data_provenance.json).
It separates source data, locally generated data, automated comparison and
human scientific review. Automated checks do not constitute scientific
approval; human review is pending with `@Thirtha17`.

## 1. Mission and challenge data

The canonical manifest is [`data/missions.json`](../data/missions.json). Each
record contains the source organization, title, URL, accessed date and the
fields supported by that source. NASA CLPS pages are used wherever available;
LROC/ASU, NASA NSSDCA, ISRO, JAXA/NASA and USGS/IAU references are retained for
historical landing positions and named features. Planned coordinates are
explicitly labelled `target_region_reference`, `target_feature_reference`,
`basin_reference`, or `landing_region_center` when no authoritative landing
fix is published. They must not be presented as actual landing points.

The offline files [`offline_fixtures/missions.json`](../offline_fixtures/missions.json)
and [`offline_fixtures/site_geometry/`](../offline_fixtures/site_geometry/) are
software fixtures derived from the canonical catalog and cited inputs; they are
not independent scientific sources.

## 2. Artemis III landing regions

This project intentionally uses NASA's **nine-region October 2024 update**, not
the original thirteen-region August 2022 list. The primary source is
[NASA release 24-136](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)
(2024-10-28); the downselection context is the
[NASA NTRS report](https://ntrs.nasa.gov/citations/20250011660). NASA published
the regions as an image, not coordinate polygons. Therefore
[`data/artemis_iii_regions.json`](../data/artemis_iii_regions.json) stores
IAU feature-centre anchors from the
[USGS/IAU Gazetteer](https://planetarynames.wr.usgs.gov/), with explicit
`anchor_relation` and `is_landing_point: false`. Anchor coordinates are
processed local references, not NASA region centroids.

## 3. Lunar South Pole and PSR data

PSR polygons come from NASA GSFC PGDA
[product 90](https://pgda.gsfc.nasa.gov/products/90), file set
`LPSR_80S_20MPP_ADJ`. PSR distance, area and containment are locally computed
in [`src/compute/proximity.py`](../src/compute/proximity.py).

PSR host-crater names and Artemis anchor feature metadata come from the
[USGS Astrogeology / IAU Moon centre-points archive](https://asc-planetarynames-data.s3.us-west-2.amazonaws.com/MOON_nomenclature_center_pts.zip),
pinned by SHA-256 in [`src/acquire/usgs_nomenclature.py`](../src/acquire/usgs_nomenclature.py).
The CSV is a locally filtered subset of IAU-adopted features, not a NASA PSR
attribute table.

## 4. Horizons ephemerides

The authoritative source is the [NASA/JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api);
the [official API documentation](https://ssd.jpl.nasa.gov/api/horizons.api-doc.html)
defines the programmatic interface. Cached reference responses are retained in
[`data/validation/horizons/`](../data/validation/horizons/). Object IDs,
center, site coordinate convention, UTC interval, step, quantity, airless
setting, units, frame and retrieval metadata are recorded in
[`horizons_crosscheck.json`](../data/validation/horizons_crosscheck.json), and
the query/comparison code is [`src/ml/horizons_crosscheck.py`](../src/ml/horizons_crosscheck.py).
The comparison is automated consistency evidence only; human scientific review
is pending.

## 5. SPICE and ephemeris data

The five kernels are NASA/JPL NAIF generic kernels:
[NAIF generic kernel archive](https://naif.jpl.nasa.gov/naif/data_generic.html).
The exact file URLs, sizes and SHA-256 values are maintained in
[`src/acquire/nasa_products.py`](../src/acquire/nasa_products.py) and
[`src/acquire/verify_data.py`](../src/acquire/verify_data.py). The engine uses
spiceypy to load them and locally computes ME/PA frame transforms and
topocentric geometry. Kernel coverage and frame assumptions are documented in
[`docs/SCIENTIFIC_BASIS.md`](SCIENTIFIC_BASIS.md).

## 6. LOLA and terrain data

The polar DEM is NASA GSFC PGDA product 90,
[`LDEM_80S_80MPP_ADJ.TIF`](https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF),
80 m/pixel. The global DEM is the NASA PDS Geosciences Node LRO LOLA GDR
[`LDEM_64`](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img),
64 pixels/degree. The label and checksums are recorded by the acquisition
registry. Committed site tiles in [`data/lola/tiles/`](../data/lola/tiles/)
are derived resamples, with source hash and projection recorded in
[`index.json`](../data/lola/tiles/index.json).

## 7. Other scientific datasets

NASA GSFC PGDA product 69 supplies the 85-90S and 75-90S average solar
illumination rasters and the Earth-visibility truth raster. Their exact URLs,
release names, checksums and transformations are in
[`data/validation/data_provenance.json`](../data/validation/data_provenance.json)
and the validation artifacts. The validation outputs distinguish NASA
reference rasters from locally generated values and retain
`human_review_status: pending`.

## 8. Derived and processed data

Precomputed tracks, geometry payloads, sensitivity payloads, site tiles, PSR
nearest-neighbour results and validation metrics are derived locally. They
inherit provenance from their cited inputs; they are not external datasets.
Processing includes raster sampling, frame conversion, horizon ray tracing,
disc geometry, spherical distance calculations, spatial joins, and statistical
comparison. See [`docs/SCIENTIFIC_BASIS.md`](SCIENTIFIC_BASIS.md) and each
module's docstring for assumptions.

## Audit status

| Data item | Local file(s) | Source | Version/date | Citation present | Human review required | Status |
|---|---|---|---|---|---|---|
| Mission catalog | `data/missions.json` | Per-record NASA/primary citations | Record-specific | Yes | Yes | Coordinate qualifiers retained |
| Artemis III regions | `data/artemis_iii_regions.json` | NASA 24-136 + USGS/IAU anchors | 2024-10-28; archive SHA pinned | Yes | Yes | Nine-region version explicit |
| PSR polygons | `data/psr/*` | NASA PGDA product 90 | Filename release | Yes | Yes | CRS caveat documented |
| IAU crater names | `data/psr/iau_south_polar_craters.csv` | USGS/IAU Gazetteer | SHA pinned 2026-11-05 | Yes | Yes | Locally filtered subset |
| Polar DEM | `data/lola/LDEM_80S_80MPP_ADJ.TIF` | NASA PGDA product 90 | SHA pinned | Yes | Yes | LFS/download verified |
| Global DEM and tiles | `cache/nasa/pds/ldem_64.*`, `data/lola/tiles/*` | NASA PDS LRO LOLA GDR | SHA pinned | Yes | Yes | Tiles labelled derived |
| Illumination rasters | `data/illumination/*` | NASA PGDA product 69 | 201608 release | Yes | Yes | Validation truth separated |
| SPICE kernels | `data/spice/*` | NASA/JPL NAIF | Kernel-specific | Yes | Yes | SHA manifest |
| Horizons responses | `data/validation/horizons/*` | NASA/JPL Horizons API | Query-specific | Yes | Yes | Automated comparison pending review |
| Derived tracks/validation | `data/precomputed/*`, `data/validation/*.json` | Local processing of cited inputs | Artifact-specific | Yes, as derived | Yes | Not source data |

No important scientific dataset is intentionally marked citation-absent.
The known unresolved items are listed in the provenance JSON audit findings,
especially planned-mission reference coordinates and the secondary CP-12
termination citation.
