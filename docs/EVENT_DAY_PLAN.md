# Event-day plan: 13–15 November 2026

NASA publishes each Space Apps challenge's full resource list when the
hackathon opens. Our pipeline was built before then from public NASA
products. Day one is therefore about one question: **do the official
resources change anything we serve?** This page gives each team its steps,
the commands, and the rules for deciding.

Times are relative to **T0, the moment the challenge page shows its
resources**. Convert them to local time in the team channel on the day.

## Before T0 (by 12 November)

| Owner | Task | Done when |
|---|---|---|
| Data pipeline | `git lfs pull`, `python -m src.acquire.verify_data` on every machine that will run the API | prints `all required data present and verified` |
| Data pipeline | Check that the LFS quota is not exhausted; if it is, use `verify_data --fetch` (public NASA mirrors) | every team member has the data |
| Backend | Deploy from the merged branch; call `site_evaluation.warm_up()` at startup | `/api/v1/sites/geometry?site_id=clps-prime-1-im2` returns 200 |
| Frontend | Offline fallback tested with the network off (`offline_fixtures/`) | UI works with no API |
| All | Read the [integration guide](TEAM_INTEGRATION_GUIDE.md) "Data honesty rules" | — |
| All | Save the current challenge page as a PDF in the team drive, so day-one changes can be diffed | file saved |

## T0 to T0+2 h: triage the official resources (data pipeline lead)

1. Open the challenge page and the "Resources" section. Save every link to
   `event_resources/links.md`, with its title and publisher.
   `event_resources/` is git-ignored: put no third-party files in the repo.
2. Download every data file into `event_resources/<publisher>/`. Put
   archives in their own folder and do not extract them yet.
3. Run the identifier:

   ```sh
   python -m src.acquire.identify_resources event_resources/
   python -m src.acquire.identify_resources event_resources/ --json > event_resources/identify_report.json
   ```

4. Read each line and act on its status:

   | Status | Meaning | Action |
   |---|---|---|
   | `KNOWN` | Byte-identical to a file we already use | None. Note in `links.md`: "already in pipeline (`<path>`)". This is evidence for the judges that we used the official data. |
   | `NEW_VERSION` | Same name, different bytes: a new release | Go to "Adopting a new release" below. Do **not** replace the file in place. |
   | `NEW`, raster, `covers_south_pole: true` | A polar product we do not use yet | Triage within 30 min (next section). |
   | `NEW`, vector or table | Sites, regions, PSRs, catalogs | Compare with `data/missions.json`, `data/artemis_iii_regions.json`, the PSR product. |
   | `NEW`, document | Paper, slide deck, rules | Read; note the requirements in `links.md`. |
   | archive | Listed, not extracted | Extract into its own folder, run the identifier on that folder. |

5. Post a summary in the team channel by **T0+2 h**: counts per status and
   any item that needs a decision.

## Triage of a NEW polar product (30 minutes per product)

Answer these questions in `links.md` for each product:

1. **What quantity is it?** Elevation, illumination, Earth visibility,
   PSR, slope, hazard, temperature, ice, or something else. Read the label
   or the product page, and do not guess from the filename.
2. **Does it overlap what we compute?** If it measures what we compute
   (sunlight, Earth visibility, PSR, slope), it is **validation truth
   first**. Run it through the same protocol as
   [ML_VALIDATION_REPORT.md](ML_VALIDATION_REPORT.md), writing to a new
   report so the committed one is untouched:

   ```sh
   python -m src.ml.validation --product PATH.TIF --output event_resources/solar_check.json
   python -m src.ml.earth_validation --product PATH.TIF --output event_resources/earth_check.json
   ```

   Adopt it only if it is finer or newer than what we use.
3. **Does it add a layer we lack?** Examples: hazard, roughness, rock
   abundance, temperature, ice. Add it as a **read-only context layer**
   with its source and resolution, after the same `nasa_products` +
   `verify_data` registration as every other file.
4. **Size and licence.** Over 100 MB goes in `cache/` via `nasa_products`,
   not in Git. Only public NASA/USGS/JPL data goes into the registry.

Decision rule: **a new layer must not delay a working submission.**
Anything not adopted by the freeze is listed in the README as "evaluated,
not adopted" with the reason. That is still credit-worthy.

## Adopting a new release (NEW_VERSION)

Follow [DATA_SETUP.md](DATA_SETUP.md), "Updating a dataset":

1. Register the new file (new size and SHA-256) in
   `src/acquire/nasa_products.py` and `src/acquire/verify_data.py`.
2. Regenerate the derived outputs: tracks, fixtures, regions if relevant.
3. Re-run the validations and the full test suite. Compare the metrics
   with the committed reports, and write any change into the report.
4. One pull request per product, reviewed by a second person.

## Checks against the challenge text (T0 to T0+3 h, research lead)

- [ ] The challenge's named reference tools are covered. JPL Horizons is
      already cross-checked (`python -m src.ml.horizons_crosscheck --refresh`
      re-queries the live API). Re-run it on day one and commit the result
      if it changed.
- [ ] Re-check the Artemis III region list on nasa.gov against
      `data/artemis_iii_regions.json`. If NASA changed it, edit `REGIONS` in
      `src/acquire/artemis_regions.py`, rebuild, and run the tests.
- [ ] Re-check the CLPS mission list and dates against `data/missions.json`
      (sources are recorded per fact).
- [ ] Map every stated objective of the challenge to a feature, or to an
      honest "not covered" line in the README.

## 14 November: build day

| Owner | Focus |
|---|---|
| Data pipeline | Adopt the approved new products; keep `verify_data` green |
| Backend | Routes: missions, geometry, sensitivity, artemis-regions; cache sensitivity responses |
| Frontend | Simple Mode story: site → sunlight/Earth countdown → "small changes, big effects" → Artemis regions layer |
| Research/ML | Validation numbers into the presentation; one slide on methods and limits |

**Code freeze: T0+40 h.** After the freeze, only fixes to failing tests or
broken deploys go in, each through a pull request.

## 15 November: submission

- [ ] `python -m src.acquire.verify_data` and `python -m pytest -q tests` pass
      on the release commit. Tag it (`git tag space-apps-2026-submission`).
- [ ] The deployed site works with the API down (offline fixtures).
- [ ] README: challenge link, the official resources used (from `links.md`),
      validation numbers, known limits, team.
- [ ] Video/slides use the same numbers as `data/validation/*.json`.
      Do not round them differently or claim more than they show.
- [ ] Submit before the deadline, with at least 2 h of margin.

## Fallbacks

| Problem | Fallback |
|---|---|
| Git LFS quota exhausted | `python -m src.acquire.verify_data --fetch` (downloads from NASA/NAIF) |
| NASA site slow or down | All required files are already in LFS. Optional ones can wait. |
| API host down | Frontend serves `offline_fixtures/` through the same parser |
| JPL Horizons unreachable | The cross-check uses the committed responses in `data/validation/horizons/` |
| A new product is too large or slow to adopt in time | List it as "evaluated, not adopted", with the reason |
