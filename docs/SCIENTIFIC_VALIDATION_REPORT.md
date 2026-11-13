# Scientific validation report

Human scientific review for the Lunar Landing Site Navigator.
Reviewer: `@Thirtha17` (Scientific Review, `feature/research`).

This file records the human review. The automated comparisons are described in
[ML_VALIDATION_REPORT.md](ML_VALIDATION_REPORT.md) and
[TEAM_INTEGRATION_GUIDE.md](TEAM_INTEGRATION_GUIDE.md#research-validation-workflow);
their machine-readable outputs are in [`data/validation/`](../data/validation/).

## Review status

| Item | Status | Date |
|---|---|---|
| JPL Horizons ephemeris spot-check (Apollo 11, Chandrayaan-3, IM-2) | **Passed** | 2026-11-12 |
| Horizons batch cross-check, 13 sites (`horizons_crosscheck.json`) | **Accepted** | 2026-11-12 |
| NASA PGDA annual solar illumination comparison | **Accepted** | 2026-11-12 |
| NASA PGDA Earth visibility comparison | **Accepted** | 2026-11-12 |
| Data provenance audit, 11 datasets (`data_provenance.json`) | **Accepted** | 2026-11-12 |
| CP-12 termination citation (secondary source: SpaceNews) | **Accepted** (secondary source; no NASA release located) | 2026-11-12 |
| Simple Mode "50 km shadow" copy (≈115 km at 1° for a 2,000 m rim) | **Resolved**: not used in the app | 2026-11-12 |

## 1. JPL Horizons ephemeris spot-check

**Result: passed.** All 12 values agree with JPL Horizons to within
**0.006°**, against an acceptance target of **Δ < 0.1°**.

### Method

Reference values were taken from the JPL Horizons API
(`https://ssd.jpl.nasa.gov/api/horizons.api`) on 2026-11-12. Horizons used
ephemeris DE441.

| Setting | Value |
|---|---|
| Ephemeris type | Observer table |
| Targets | Sun (`10`), Earth (`399`) |
| Observer | User-defined site on the Moon (`coord@301`), altitude 0 km, MEAN_ME frame, spherical radius 1737.4 km |
| Coordinates | East longitude, latitude (entered in that order) |
| Time | The UTC epoch below, 1-minute step |
| Quantity | 4 (apparent azimuth and elevation) |
| Refraction | Airless |

The pipeline values come from `src.compute.spice_engine.calculate_geometry`.
That function computes geometric directions with no light-time or aberration
correction, using DE430 and `moon_pa_de421_1900-2050.bpc` (see
[TEAM_INTEGRATION_GUIDE.md](TEAM_INTEGRATION_GUIDE.md#research-validation-workflow)).
Azimuth is measured clockwise from north in both.

### Results (degrees)

| Site | Lon E, Lat | UTC | Quantity | Horizons | Pipeline | \|Δ\| |
|---|---|---|---|---|---|---|
| Apollo 11 | 23.47314, 0.67416 | 1969-07-20 20:17 | Sun elevation | 10.6977 | 10.692 | 0.006 |
| | | | Sun azimuth | 88.8054 | 88.805 | 0.000 |
| | | | Earth elevation | 59.2245 | 59.225 | 0.001 |
| | | | Earth azimuth | 272.1940 | 272.194 | 0.000 |
| Chandrayaan-3 | 32.32, −69.3741 | 2023-08-23 12:34 | Sun elevation | 8.6146 | 8.613 | 0.002 |
| | | | Sun azimuth | 62.0425 | 62.048 | 0.005 |
| | | | Earth elevation | 12.9952 | 12.995 | 0.000 |
| | | | Earth azimuth | 318.9964 | 318.997 | 0.001 |
| IM-2 Mons Mouton | 29.20, −84.79 | 2026-11-15 12:00 | Sun elevation | 2.5299 | 2.529 | 0.001 |
| | | | Sun azimuth | 79.3232 | 79.329 | 0.006 |
| | | | Earth elevation | 1.4471 | 1.447 | 0.000 |
| | | | Earth azimuth | 327.5159 | 327.516 | 0.000 |

The pipeline values are rounded to 3 decimal places, so differences below
0.001° are within rounding.

### Interpretation

- **The largest difference is 0.006°, about 1/16 of the tolerance.**
- The Sun differences (up to about 0.006°) are larger than the Earth
  differences (up to about 0.001°). That pattern is expected: Horizons
  returns apparent directions, which include light-time and stellar
  aberration (about 20″ for the Sun), while the pipeline is geometric. The
  13-site batch cross-check shows the same Sun offset (maximum 0.0060°).
- There is no sign of a frame, longitude-sign or azimuth-convention error.
  Errors of that kind would show up as differences of degrees, not
  thousandths of a degree.
- A first manual attempt entered latitude and longitude in the wrong order.
  Horizons expects east longitude first. It returned a Sun elevation of
  −10.57° for Apollo 11, which is clearly wrong because Apollo 11 landed in
  low morning sunlight. Anyone repeating this check should enter longitude
  first.

### Reproduce

Web: https://ssd.jpl.nasa.gov/horizons/app.html with the settings above.

API (Apollo 11, Sun):

```sh
curl -s -G https://ssd.jpl.nasa.gov/api/horizons.api \
  --data-urlencode "format=text" --data-urlencode "COMMAND='10'" \
  --data-urlencode "EPHEM_TYPE='OBSERVER'" --data-urlencode "CENTER='coord@301'" \
  --data-urlencode "COORD_TYPE='GEODETIC'" --data-urlencode "SITE_COORD='23.47314,0.67416,0'" \
  --data-urlencode "START_TIME='1969-07-20 20:17'" --data-urlencode "STOP_TIME='1969-07-20 20:18'" \
  --data-urlencode "STEP_SIZE='1 m'" --data-urlencode "QUANTITIES='4'" --data-urlencode "APPARENT='AIRLESS'"
```

Pipeline:

```sh
python -c "from src.compute.spice_engine import *; load_kernels(); print(calculate_geometry(0.67416, 23.47314, '1969-07-20T20:17:00Z'))"
```

## 2. Validation and provenance review

Reviewed 2026-11-12 by `@Thirtha17`.

- **Horizons batch cross-check: accepted.** The query configuration,
  geometric-vs-apparent assumption and residuals in
  [`horizons_crosscheck.json`](../data/validation/horizons_crosscheck.json)
  agree with the manual spot-check in section 1.
- **NASA PGDA solar illumination and Earth visibility: accepted.** The method,
  results (test-set MAE 1.45 pp and 1.40 pp; R² 0.951 and 0.953) and stated
  limitations in [ML_VALIDATION_REPORT.md](ML_VALIDATION_REPORT.md) are
  accepted. The validation covers 85–90°S only. Sites north of 80°S use
  `LDEM_64` and are outside its scope.
- **Data provenance: accepted.** Every dataset in [DATA_SOURCES.md](DATA_SOURCES.md)
  and [`data_provenance.json`](../data/validation/data_provenance.json) has a
  cited source. The CP-12 termination remains sourced from SpaceNews, a
  secondary source; this is accepted because no NASA release was located.

Sign-offs are recorded in [`human_review.json`](../data/validation/human_review.json).
The validation scripts read their review status from that file, so re-running
them does not reset a review.

- **"50 km shadow" (Issue #8): resolved.** The figure appears only in the
  Issue #8 brief. It does not appear in the app on `main` or on
  `feature/frontend-systems`. The correct relation is
  `shadow length = height / tan(sun elevation)`, which gives about 115 km for a
  2,000 m rim at 1° (50 km corresponds to about 2.3°). Any future shadow
  feature must compute the length this way and not reuse the Issue #8 number.

## Sign-off

Final sign-off is given when every row in the status table reads "Passed"
or "Accepted".

Reviewer: `@Thirtha17` — Date: 2026-11-12 — **All items passed or accepted.**
