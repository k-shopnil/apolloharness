# Scientific basis and data provenance

This note records the physical and coordinate assumptions used by Issue #2. It
is not a validation claim for a particular mission site: quantitative results
are valid only when the exact source data, kernels, time span, and sampling
settings are recorded with the result.

## Lunar frames and map coordinates

`MOON_ME` is the mean-Earth body-fixed orientation used by the cited NASA PGDA
polar LOLA products. Their product-90 metadata identifies the frame as ME and
its realization as DE421. `MOON_PA` is the principal-axes body-fixed frame used
by the project's lunar orientation binary PCK; it is not interchangeable with
ME: ME's positive Z axis follows the mean lunar pole and its prime meridian
contains the mean Earth direction, while PA follows the solid Moon's
principal axes. For DE421, NASA reports the constant ME-to-PA rotation as
0.0288473° (about 875 m at the surface; [PGDA product 95](https://pgda.gsfc.nasa.gov/products/95)).
`IAU_MOON` is the IAU body-fixed frame label; [NAIF cautions](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/Tutorials/pdf/individual_docs/23_lunar-earth_pck-fk.pdf)
that it is not a substitute for the high-accuracy `MOON_ME`/`MOON_PA` frames.
The string in a GeoTIFF WKT is CRS metadata; it does not itself apply an
epoch-dependent SPICE transformation.

The raster's south-polar stereographic grid (`MOON_SPS` in this project) is a
map projection, not a SPICE frame. It uses a spherical Moon radius of
1,737,400 m, central meridian 0° east, the south pole as origin, and meter
coordinates. Mission latitude/longitude values are planetocentric in the ME
orientation for projection to NASA ME rasters. SPICE ephemeris geometry is
computed in PA; coordinates and local tangent axes are transformed from ME to
PA at the requested ephemeris time using the loaded lunar orientation kernels.
PSR vectors must declare their CRS; projected distances are calculated in
meters after transformation to the same polar metric CRS.

NASA PGDA product 90 documents its LOLA DEM and PSR data in polar
stereographic coordinates and its reference frame. Product 81's 5 m mosaic has
87–90°S coverage and therefore does not cover Mons Mouton at 84.79°S. The
product-90 80–90°S, 80 m DEM is the selected shared coverage for the two
benchmark sites. The product-90 page declares MOON_ME/DE421, while the acquired
DEM's GeoTIFF WKT labels its CRS “Moon (2015) - Sphere / Ocentric / South Polar”
and gives IAU authority 30135. PyProj applies only the spherical stereographic
projection when transforming ME longitude/latitude to this file, with no datum
rotation. Because the product page explicitly defines the grid as ME, the
pipeline uses ME coordinates for its map lookup and records the WKT discrepancy
as a metadata inconsistency to resolve before high-precision science claims.
This distinction matters: NASA documents an approximately 875 m surface offset
between ME and PA for DE421. The SPICE engine explicitly rotates ME observer
coordinates and tangent axes into PA at each epoch; the map projection itself
does not perform that SPICE-frame transform.

## NASA data sources

| Input | Primary source and semantics | Local path |
|---|---|---|
| Mission manifest | NASA CLPS delivery pages linked per record in `data/missions.json`; date and coordinate fields retain reference/provenance qualifiers where NASA does not publish an exact value | `data/missions.json` |
| LOLA elevation | NASA GSFC PGDA [product 90](https://pgda.gsfc.nasa.gov/products/90), `LDEM_80S_80MPP_ADJ.TIF`, 80–90°S, 80 m/pixel, south-polar stereographic meters, product page says MOON_ME/DE421, reference sphere 1,737.4 km; 189,158,392 bytes. Embedded WKT says IAU Moon 2015 Ocentric; see CRS discrepancy above. | `cache/nasa/pgda/LDEM_80S_80MPP_ADJ.TIF`, linked into `data/lola/` |
| Global LOLA elevation | NASA PDS Geosciences LRO LOLA GDR `LDEM_64` (LRO-L-LOLA-3-RDR-V1), global, 64 pixel/degree (473.8 m/pixel at the equator), simple cylindrical centred on 180°E, int16 DN × 0.5 m above a 1,737.4 km sphere (label OFFSET 1737400 m is the sphere radius and is not applied to heights); `.img` 530,841,600 bytes, SHA-256 `1c4958699d4cffd7e777d51421b6044bba300aa0bef286a544309efb082cdbd6`. Used outside the 80 m polar DEM and to complete polar-edge rays, resampled per site to stereographic metres. | `cache/nasa/pds/ldem_64.img` (not in Git); derived site tiles in `data/lola/tiles/` (Git LFS) |
| Average solar illumination | NASA GSFC PGDA [product 69](https://pgda.gsfc.nasa.gov/products/69), 85–90°S, 60 m/pixel, solar illumination averaged over hourly samples across approximately an 18.6-year nutation cycle. The GeoTIFF has `scale=0.00004`, `offset=0`; scaled values are fractions of illuminated time. Nodata is `-32768`. Its embedded CRS labels the datum `Moon_2000_IAU_IAG`, with a 1,737,400 m sphere; product page does not specify a DE421 orientation realization. | `cache/nasa/pgda/AVGVISIB_85S_060M_201608.TIF`, linked into `data/illumination/` |
| Broader average solar illumination | NASA GSFC PGDA product 69, 75–90°S, 120 m/pixel, same 201608 product release and long-term temporal basis; covers both Shackleton and Mons Mouton. GeoTIFF scale `0.00004`, offset `0`, nodata `-32768`; SHA-256 `d539467f16ccc5f51b6a904af6be5d16c9b2f194afe619b9f1f81841d9fec0bb`. | `cache/nasa/pgda/AVGVISIB_75S_120M_201608.TIF`, linked into `data/illumination/` |
| Permanently shadowed regions | NASA GSFC PGDA [product 90](https://pgda.gsfc.nasa.gov/products/90), full `LPSR_80S_20MPP_ADJ` shapefile set, south-polar PSR polygon boundaries; four components (`.SHP`, `.SHX`, `.DBF`, `.PRJ`) are required. Source `.PRJ` declares Moon2000 / IAU-IAG spherical South Polar Stereographic, which differs from the product page's stated ME/DE421 realization. | `cache/nasa/pgda/`, linked into `data/psr/` |
| SPICE kernels | NAIF [generic kernels](https://naif.jpl.nasa.gov/naif/data_generic.html): `naif0012.tls` UTC/leap seconds; `pck00010.tpc` body constants; `moon_080317.tf` frame definitions; `moon_pa_de421_1900-2050.bpc` lunar orientation; `de430.bsp` planetary ephemerides | `data/spice/` |

The product-69 file is exposed by NASA's “Average solar illumination” listing
under its product page, despite the legacy `AVGVISIB` filename. Do not confuse it
with the separately listed “Average Earth visibility” products. Verify the
embedded `PRODUCT_ID`, scale, CRS, and nodata metadata before use. The selected
85–90°S illumination map does not cover Mons Mouton; an appropriately broad
product-69 map is required for Mons Mouton; the registry also provides the
broader 75–90°S raster for that site. Unlike the cited product-90 DEM,
the product-69 web description does not explicitly identify an ME/DE421
orientation realization. Its projection and reference radius are known, but
the frame realization is a remaining provenance uncertainty for comparisons
that require high-precision coordinate alignment.

Large files are acquired through `python -m src.acquire.nasa_products
<product-name>`, cached locally, and linked into ignored `data/` paths. The
acquisition registry records source URL, expected filename, byte size and
verified SHA-256 where acquired. For downloads too large or slow for a
particular environment, use the source product page and place complete files at
the documented paths. Never commit downloaded binaries. Record the source
checksum with run metadata for reproducibility.

## Model meaning and limitations

The deterministic physics engine is the ground-truth computation layer for
this project: SPICE supplies time-dependent Sun/Earth geometry, LOLA supplies
terrain elevation and horizon samples, product-69 rasters supply long-term
illumination, and the product-90 vector supplies PSR boundaries subject to its
validity/CRS limitations. Physics results remain available independently of
ML. The optional intelligence layer in `src/ml/features.py` aggregates those
results for future screening and audit; it does not modify, replace, or
validate the physical calculations. No trained model, candidate ranking,
physics-derived utility target, or surrogate exists in this revision.

Feature schema `apollo-lunar-site-v1` carries deterministic outputs and leaves
missing sources null. Completeness/status/provenance are separate metadata,
not a hidden score. Benchmark sites are excluded from feature records by
default and cannot enter the audit helper as training samples. Spatial groups
are deterministic 5-degree latitude/longitude blocks; helpers reject overlap
and adjacent cells across spatial partitions using a one-cell buffer, and
enforce chronological ordering when evaluating a temporal model. The buffer is
a conservative grid guard rather than a precise geodesic distance. These
utilities prevent some common leakage paths but do not make an uncurated
dataset scientifically valid. Current sample count for
legitimate independent ML training is zero: the CLPS records are mission
metadata, not independent site/physics labels, and the only available real
site samples are reserved benchmarks. No preprocessing, estimator, or model
artifact is fitted or persisted.

- Tactical sunlight compares SPICE Sun elevation with a DEM-derived radial
  terrain horizon. Missing or incomplete terrain rays produce an unknown
  illumination state, not an open-sky state. The computation depends on DEM
  resolution, radial spacing and extent, observer height, and start time.
- The horizon is a radial sampling approximation. It does not model sub-pixel
  terrain, diffuse light, reflected light, solar-disc integration, or a rover's
  local geometry.
- Annual illumination is sampled from NASA's long-period raster and must not
  be interpreted as a chosen mission window or interpolated from tactical
  samples.
- Communications output is geometric line-of-sight to Earth's center under a
  spherical horizon. It does not represent the finite Earth disc, terrain
  masking, antenna constraints, relay links, or radio link budget.
- PSR distance is planar map distance from the site coordinate to the nearest
  polygon boundary. Product completeness, polygon definitions, map scale, and
  coordinate accuracy constrain the result.
- Mission site coordinates tagged as a region/site reference are not exact
  landing fixes. The manifest's `sources[]` and `coordinate_provenance` must be
  retained downstream.
- No benchmark values are encoded in the implementation. The Shackleton,
  Mons Mouton, and deep-crater values in the Issue #2 brief are comparison
  targets only; differences must be investigated against source version,
  frame, coordinate, epoch, and method.

## Data and calculation status

| Calculation or input | Current status |
|---|---|
| Mission catalog | NASA-sourced mission facts with explicit source links; some site coordinates remain references or null where no exact NASA coordinate was found |
| SPICE hourly geometry | Uses installed NAIF kernels and is software-tested against real kernel calculations; no external geometry benchmark has been validated |
| Annual Shackleton sample | REAL DATA: product-69 sample 11.26%; independent physics gives 10.2% at the same coordinate, so the brief's ~89.4% refers to a different point (resolved, see ML_VALIDATION_REPORT.md) |
| Annual Mons Mouton sample | REAL DATA: product-69 75–90°S GeoTIFF acquired; nearest-pixel sample is 46.412% |
| LOLA terrain horizon | REAL DATA diagnostic: the verified product-90 DEM produced 360/360 complete rays at both Mons Mouton and the reference Shackleton coordinate (20 km extent, 100 m radial step, 1° azimuth step). Result ranges are provisional while the embedded CRS discrepancy is unresolved; synthetic temporary DEM tests verify software contracts only. |
| Tactical sunlight benchmark | UNAVAILABLE for Issue #2's active-window comparison because its exact UTC start and duration were not specified. The terrain-aware calculation is exposed; do not substitute an arbitrary window. |
| PSR proximity | REAL DATA ACQUIRED: product-90 shapefile loads with 506,349 polygons; 10 are invalid. The current strict distance API rejects the unmodified source, so no PSR distance benchmark is reported. |
| Deep-crater negative control | UNAVAILABLE until a floor coordinate, matching time interval, and valid DEM horizon are pinned |

“REAL DATA” here describes the source pixels or kernels used. It does not mean
the scientific benchmark is validated. Synthetic test results are never
described as lunar science results.

## Reproducibility and offline mode

For each analysis, record: manifest revision; source product identifier and
version; file SHA-256; local kernel names and versions; coordinate and frame;
UTC start and duration; DEM observer height, radial step, azimuth step and
range; source code revision; and unavailable-data counts. JSON mission metadata
can fall back online → cache → committed mission fixture. Science binaries have
no scientific fixture fallback: when the real product is missing, the API must
report it unavailable. Fixture outputs are for software and offline testing
and are NOT scientific results.

Install dependencies from `requirements.txt`. Run checks with
`.venv/bin/python -m unittest discover -s tests -v`; run syntax validation with
`.venv/bin/python -m compileall src`. The synthetic raster/vector tests verify
software contracts only and are not scientific benchmarks.

## Validation run record

On 2026-10-20, the downloaded product-69 file
`AVGVISIB_85S_060M_201608.TIF` was opened with Rasterio. It reports 5058 × 5058
pixels, 60 m cells, nodata `-32768`, scale `0.00004`, offset `0`, and product ID
`AVGVISIB_85S_060M_201608`. Its SHA-256 is
`ccf67d4f39e0a970c111196da7d6551ffcf50d075470b93067fb3904c0b05806`. The
nearest-pixel sample at the brief's Shackleton coordinate (-89.54°, 0°) is
11.26% after applying the declared scale. This differs substantially from the
brief's approximately 89.4% comparison target. The comparison is therefore
unvalidated; confirm that the benchmark coordinate, expected product/version,
and sampling convention correspond before attributing a cause. No expected
value has been forced into the code. No terrain, PSR, tactical-window, or
deep-crater scientific benchmark is claimed until its real inputs and exact
time window have been run.

The broader product-69 `AVGVISIB_75S_120M_201608.TIF` was also acquired and
verified at 83,052,039 bytes. It reports 7624 × 7624 cells at 120 m, scale
`0.00004`, offset `0`, and nodata `-32768`. Its SHA-256 is
`d539467f16ccc5f51b6a904af6be5d16c9b2f194afe619b9f1f81841d9fec0bb`. The
nearest-pixel samples are 10.42% at Shackleton (-89.54°, 0°) and 46.412% at
Mons Mouton (-84.79°, 29.20°). These are real-raster samples, not validation
targets. **Resolved (2026-10-31):** an independent physics computation at
(-89.54°, 0°) gives 10.2%, consistent with NASA's 11.26%, so the coordinate is
not the highly illuminated rim; see
[ML_VALIDATION_REPORT.md](ML_VALIDATION_REPORT.md).

The complete product-90 PSR shapefile set was downloaded and byte-size checked
on 2026-10-20. SHA-256 values are recorded in the acquisition registry for its
SHP and SHX components; DBF and PRJ are size checked. GeoPandas reads 506,349
features with the `.PRJ` Moon2000 polar stereographic CRS and expected bounds
of ±303,990 m. Ten source polygons are invalid (gids 57, 116, 158, 408, 645,
1620, 2490, 8038, 15187, and 35852). The proximity calculation intentionally
rejects the source as a whole, so nearest-PSR distances remain unavailable
until an authoritative cleanup or a rigorously justified validity policy is
established. No polygons were modified for this report.

The product-90 DEM was acquired at exactly 189,158,392 bytes; SHA-256
`82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a`. Rasterio
reports 7600 × 7600 float32 pixels at 80 m/pixel with NaN nodata and 80–90°S
coverage. The product page and embedded WKT CRS labels differ as described
above. Using the product-page ME map-coordinate convention, the terrain
sampler found complete rays for both benchmark references. At Mons Mouton, the
sampled horizon elevations ranged from -1.41° to 4.06°; at (-89.54°, 0°), they
ranged from -2.41° to 10.72°. These are terrain-processing diagnostics, not
sunlight benchmark results, and should be revisited after the CRS metadata
discrepancy is resolved.

## References

- Erwan Mazarico et al. (2011), “Illumination conditions of the lunar polar
  regions using LOLA topography,” *Icarus* 211, 1066–1081,
  [doi:10.1016/j.icarus.2010.10.030](https://doi.org/10.1016/j.icarus.2010.10.030).
  NASA PGDA product 69 requests citation of this work for the LOLA illumination
  maps.
- NASA GSFC PGDA, [LOLA South Pole products, product 90](https://pgda.gsfc.nasa.gov/products/90).
- Barker et al. (2023), “A New View of the Lunar South Pole from the Lunar
  Orbiter Laser Altimeter (LOLA),” *The Planetary Science Journal* 4, 183,
  [doi:10.3847/PSJ/acf3e1](https://doi.org/10.3847/PSJ/acf3e1).
- NASA GSFC PGDA, [LOLA MOON_PA gridded dataset, product 95](https://pgda.gsfc.nasa.gov/products/95), including the ME-to-PA relationship and its approximately 875 m surface offset.
- NASA GSFC PGDA, [South Pole LOLA DEM Mosaic, product 81](https://pgda.gsfc.nasa.gov/products/81).
- NASA GSFC PGDA, [Lunar Polar Illumination, product 69](https://pgda.gsfc.nasa.gov/products/69).
- JPL NAIF, [Generic kernels and SPICE data](https://naif.jpl.nasa.gov/naif/data_generic.html).
- Hayne et al. (2015), “Evidence for exposed water ice in the Moon’s south
  polar regions from Lunar Reconnaissance Orbiter ultraviolet albedo and
  temperature measurements,” *Icarus* 255, 58–69,
  [doi:10.1016/j.icarus.2015.03.032](https://doi.org/10.1016/j.icarus.2015.03.032).
  This is volatile-detection context; it does not provide the illumination
  raster or validate this pipeline's sunlight model.
- Spudis et al. (2010), “Initial results for the north pole of the Moon from
  Mini-SAR, Chandrayaan-1 mission,” *Geophysical Research Letters* 37, L06204,
  [doi:10.1029/2009GL042259](https://doi.org/10.1029/2009GL042259). This is
  radar context and is not used to define south-pole PSR geometry.
- NASA, [Artemis III Science Definition Team Report](https://www.nasa.gov/wp-content/uploads/2015/01/artemis-iii-science-definition-report-12042020c.pdf).
