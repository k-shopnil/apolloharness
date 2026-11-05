# Physics engine validation against NASA PGDA product 69

**Question.** Does our SPICE + LOLA horizon engine reproduce NASA's
independent long-term solar illumination map of the lunar south pole?

**Answer.** Yes. On a held-out test set it explains 95% of the variance
(R² = 0.951), with a mean absolute error of 1.45 percentage points and no
measurable bias (−0.05 pp, 95% CI [−0.34, +0.29]). The same engine, unchanged,
reproduces NASA's independent **Earth visibility** map out-of-sample (R² 0.953,
MAE 1.40 pp), and its Sun/Earth sky positions match **JPL Horizons** to
0.006° (sections below). 97% of test points
fall within ±5 pp. The validation also showed that the previous 50 km horizon
default over-predicted polar sunlight by about 1.6 pp. Production now uses
the configuration this protocol selected.

Machine-readable results: [`data/validation/annual_illumination_validation.json`](../data/validation/annual_illumination_validation.json).
Reproduce (deterministic, ~1 min):

```sh
python -m src.ml.validation --points 800 --epochs 2000
```

## Why this is the right ML work here

The challenge's quantities (sunlight, Earth line of sight, countdowns) are
computed exactly by physics. Training a regression model on outputs we
generate ourselves would add error, not knowledge. The repository's ML
contract (`src/ml/features.py`) also forbids training without an
independent, leakage-audited corpus. The data-science value is in:

1. **Independent validation**: comparing against a NASA product we did not
   produce, with ML-grade evaluation (held-out test, spatial CIs, baseline,
   stratified errors). This report.
2. **Evidence-based configuration**: the only free choice in the physics
   (horizon ray length and resolution) is selected on dev data and then
   frozen. `tests/test_regional_and_ml.py` fails if production drifts
   from the selected configuration or its test metrics regress.
3. **Decision support**: Pareto-optimal site recommendation over
   exact-physics screens (`src/ml/recommend.py`). There is no learned
   scoring and no invented weights.

## Data

| | Ground truth | Our engine |
|---|---|---|
| Source | NASA PGDA product 69, `AVGVISIB_85S_060M_201608` (Mazarico et al. 2011 method; LOLA 2009–2013) | PGDA product 90 `LDEM_80S_80MPP_ADJ` (80 m), NAIF DE430 + `moon_pa_de421` |
| Quantity | Mean visible fraction of the solar disc | Same: exact circular-segment disc fraction above the terrain horizon |
| Time base | Long-term average | 2,000 stratified-jittered epochs over one 18.61-year nodal cycle (standard error ≤ 1.1 pp per point) |
| Sampling | Nearest 60 m pixel | Observer 1.5 m above the bilinear DEM surface; 1° azimuth, 80 m radial step |

The two are not circular. Both start from LOLA altimetry, but they differ
in DEM release, resolution, ray tracer, ephemeris and time sampling.

## Protocol (fixed before any test result was seen)

1. **Sample:** 800 area-uniform random points in the product footprint
   (seed 20261031).
2. **Spatial split:** alternating 30° longitude wedges around the pole,
   giving dev (309 points) and test (305 points). A 5 km buffer at every
   wedge boundary and near the pole drops 186 points, so spatially
   correlated neighbours never straddle the split.
3. **Selection on dev only:** the candidates below were compared. The rule:
   lowest dev RMSE among configurations whose single-site horizon latency
   is ≤ 150 ms (the interactive budget inside the 500 ms request gate).
4. **One-shot test:** the selected configuration, plus the previous
   production configuration for comparison, is evaluated once on test. The
   test reports 95% CIs from 1,000 spatial-block bootstrap replicates
   (15 km blocks), a no-skill baseline, and errors stratified by local
   terrain steepness.

### Development set: configuration selection

| Configuration | RMSE (pp) | MAE (pp) | Bias (pp) | R² | Latency (ms) | Within budget |
|---|---|---|---|---|---|---|
| `rays_050km_single_res` (previous default) | 3.67 | 2.25 | +1.52 | 0.937 | 111 | yes |
| **`rays_100km_multires`** (selected) | **1.95** | **1.28** | −0.33 | **0.982** | **52** | yes |
| `rays_150km_multires` | 1.97 | 1.33 | −0.43 | 0.982 | 57 | yes |
| `rays_150km_single_res` | 1.98 | 1.34 | −0.45 | 0.982 | 506 | no |

The rule selected 100 km rays with a multi-resolution far field: 80 m
samples to 20 km, then a cached 4× block-averaged DEM. The 100 km and
150 km configurations are statistically tied on dev. The pre-declared rule
picks the lower RMSE, and it was followed rather than overridden.

### Test set: one-shot result

| Configuration | n | RMSE (pp) [95% CI] | MAE (pp) [95% CI] | Bias (pp) [95% CI] | R² [95% CI] | Within ±5 pp |
|---|---|---|---|---|---|---|
| **Selected** | 305 | 3.02 [1.74, 4.12] | **1.45** [1.17, 1.75] | **−0.05** [−0.34, +0.29] | **0.951** [0.905, 0.984] | **97.0%** |
| Previous production (50 km) | 305 | 4.43 [3.23, 5.51] | 2.38 [1.83, 2.96] | +1.59 [+0.95, +2.23] | 0.894 [0.829, 0.946] | 88.5% |
| No-skill baseline (dev mean) | 305 | 13.63 | 11.73 | +0.47 | 0.00 | 20.0% |

### Where the error comes from

| Local terrain steepness (range of NASA's map within ±180 m) | n | MAE (pp) | RMSE (pp) | Within ±5 pp |
|---|---|---|---|---|
| Smooth (lower 50%: 0–7 pp) | 152 | 0.88 | 1.19 | 100.0% |
| Moderate (50–90%: 7–27 pp) | 122 | 1.58 | 2.40 | 96.7% |
| Steep (top 10%: 27–49 pp) | 31 | 3.70 | 7.77 | 83.9% |

The residual is uncorrelated with elevation (r = 0.03), horizon height
(r = −0.00) and latitude (r = 0.10). It correlates with local steepness of
the truth itself (r = 0.33). The largest errors (max 29 pp) sit on crater
walls, where NASA's own map swings from 0% to about 50% within a few pixels.
There, sub-pixel differences between the two DEM releases (60 m vs 80 m
grid, and the CRS labelling discrepancy recorded in `SCIENTIFIC_BASIS.md`)
dominate. These points are physically ambiguous, not physics failures.
Median absolute error is 1.08 pp, and the 90th percentile is 2.56 pp.

## Resolved: the Shackleton reference discrepancy

`SCIENTIFIC_BASIS.md` recorded that NASA's map gives 11.26% at the brief's
Shackleton coordinate (−89.54°, 0°), while the brief expected about 89.4%.
Our independent physics gives **10.2%** there. Two independent methods
agree, so the coordinate is not the highly illuminated rim; the 89.4%
figure belongs to a different point. No code or data should be changed
to match it.

## Earth line of sight against NASA's Earth visibility map

The same protocol was applied to Earth, against PGDA product 69's
`AVGVISIB_85S_060M_201608_EARTH`: the fraction of 18.6 years in which **any
part of Earth's disc** is above the terrain (NASA's definition). It used the
same 800 points, seed, wedge split, bootstrap and baseline. The horizon
configuration is the production one, selected on solar dev data and frozen,
so nothing was tuned to Earth data and the test result is fully
out-of-sample.

| Test set (n = 305) | R² [95% CI] | MAE (pp) [95% CI] | Bias (pp) [95% CI] | Within ±5 pp |
|---|---|---|---|---|
| Engine, NASA's "any part visible" rule | **0.953** [0.899, 0.987] | **1.40** [0.95, 1.95] | +1.29 [+0.83, +1.82] | **93.4%** |
| Engine, Earth centre visible (`direct_los`) | 0.911 | 4.31 | −3.45 | 58.0% |
| No-skill baseline (dev mean) | 0 | 17.82 | — | — |

| Local terrain steepness | n | MAE (pp) | Within ±5 pp |
|---|---|---|---|
| Smooth (lower 50%) | 152 | 1.16 | 92.8% |
| Moderate (50–90%) | 122 | 1.03 | 95.1% |
| Steep (top 10%) | 31 | 4.09 | 90.3% |

**What this means for the API.** `earth.direct_los` tests Earth's *centre*.
That is about 3.5 pp more conservative than NASA's any-part rule, which is
the right side to err on for a radio link (NASA itself notes the any-part
rule "may be very slightly optimistic" for DSN links). `earth.disk_visible_fraction > 0`
is the any-part quantity, if a UI needs NASA's definition.

**The +1.3 pp bias, investigated on dev data only:**

| Dev-set experiment | Bias (pp) | MAE (pp) |
|---|---|---|
| Production (100 km rays, observer 1.5 m) | +1.23 | 1.37 |
| Rays to 150 km / 200 km | +1.20 / +1.26 | 1.35 / 1.41 |
| Observer 0.5 m | +0.85 | 1.14 |
| Observer 0.0 m (on the surface) | +0.62 | 1.08 |

Distant terrain is not the cause. Observer height explains half of it:
the engine evaluates at 1.5 m (instrument height), while NASA's maps appear
to be for the surface (the product page does not state a height). This is
a modelling difference, not an error, and it is itself a planning fact:
**raising an antenna by 1.5 m adds about 0.6 pp of Earth visibility** at
polar sites. Production was not re-tuned to the test data.

Reproduce (needs `python -m src.acquire.nasa_products earth_visibility_85s_60m`, 25 MB):

```sh
python -m src.ml.earth_validation   # -> data/validation/earth_visibility_validation.json, ~15 s
```

## Independent check of Sun and Earth positions: JPL Horizons

The challenge names JPL Horizons as the reference ephemeris tool, so the
engine's sky positions were compared against it directly. The authoritative
source is the [NASA/JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api)
([API documentation](https://ssd.jpl.nasa.gov/api/horizons.api-doc.html)).
The exact query configuration, object IDs, cached reference responses, and
representative reference/engine values are recorded in
`data/validation/horizons_crosscheck.json`; the reproducible implementation is
`src/ml/horizons_crosscheck.py`. The comparison
covers every catalog site with a published coordinate (13 sites, near side
and far side), the Sun and Earth, and one synodic month from
2026-11-15 at 6-hour steps, giving 1,547 samples per body. Horizons
(DE441, `MEAN_ME` site frame, airless) and the engine (NAIF DE430 +
`moon_pa_de421` via spiceypy) share no code.

| Comparison | Sun: max angular error | Earth: max angular error | Visible/not visible agreement |
|---|---|---|---|
| Production engine (geometric) vs Horizons (apparent) | 0.0060° (21.5″) | 0.0002° | 100% / 100% |
| Same light-time and aberration corrections in SPICE vs Horizons | 0.000014° (0.05″) | 0.000012° | 100% / 100% |

With Horizons' corrections reproduced, the two agree to 0.05 arcseconds in
this automated comparison, supporting consistency of the frames, time scale
and site geometry. The production residual
is entirely **stellar aberration** (≤ 20.6″), which Horizons includes and the
engine, like the NASA illumination products it was validated against,
omits. Its operational effect, measured by re-running the event finder
with aberration on: Sun rise/set times move by about **40 s**, and Earth
rise/set by under 5 s. Countdowns are displayed in minutes, so event times
should be read as accurate to about ±1 minute; `tolerance_seconds=1` is
the root-finder's numerical precision, not a physical accuracy.

Reproduce (cached responses in `data/validation/horizons/`, so it runs offline):

```sh
python -m src.ml.horizons_crosscheck             # -> data/validation/horizons_crosscheck.json
python -m src.ml.horizons_crosscheck --refresh   # re-query Horizons (~1 min)
```

`tests/test_regional_and_ml.py::HorizonsCrossCheckTests` fails if either
bound regresses.

This is a computational reproducibility result, not scientific approval.
Human review of the cited reference data, query parameters, coordinate
assumptions, methodology and residuals is pending with `@Thirtha17`.

The NASA PGDA solar and Earth visibility comparisons in the preceding
sections likewise record the cited raster products, generated values and
automated metrics in their validation JSON files. Their
`automated_comparison.human_review_status` remains `pending`; passing tests
must not be read as scientific sign-off.

## Limitations

- The truth is a model too (NASA's), not an in-situ measurement. Agreement
  shows consistency between two independent implementations, not absolute
  accuracy.
- Only the 85–90°S product was used, where both products overlap at full
  resolution. Sites north of 80°S use LOLA GDR `LDEM_64` (~474 m) and are
  not covered by this validation.
- Geometric (not light-time-corrected) directions are used. That costs
  about 0.005°, which is negligible here.
- Epoch sampling contributes up to 1.1 pp of random error per point,
  included in the scatter above.

## Changes made because of this validation

- `terrain.HORIZON_MAX_DISTANCE_M` went from 50 km to **100 km**, with
  multi-resolution tracing (`NEAR_FIELD_M = 20 km`, `FAR_FIELD_FACTOR = 4`).
  Single-site horizon latency fell from about 220 ms to about 55 ms, despite
  rays twice as long.
- Global LDEM_64 site tiles widened to a 160 km half-width so 100 km rays
  stay complete. A polar-tile bug (an all-NaN IM-1 tile) and a 0°-seam
  offset bug (90 m height error) were found and fixed along the way.
