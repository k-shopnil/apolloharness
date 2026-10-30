# Physics engine validation against NASA PGDA product 69

**Question.** Does our SPICE + LOLA horizon engine reproduce NASA's
independent long-term solar illumination map of the lunar south pole?

**Answer.** Yes. On a held-out test set it explains 95% of the variance
(R² = 0.951), with a mean absolute error of 1.45 percentage points and no
measurable bias (−0.05 pp, 95% CI [−0.34, +0.29]). 97% of test points
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
