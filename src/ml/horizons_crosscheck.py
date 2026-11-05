"""Independent cross-check of Sun/Earth sky positions against JPL Horizons.

The challenge names JPL Horizons as the reference ephemeris tool. This module
asks Horizons for the azimuth/elevation of the Sun and Earth seen from every
catalog site with a published coordinate, over one synodic month, and compares
them with the production engine (``spice_engine._topocentric_state``).

The two are independent: Horizons uses DE441 and JPL's own site-frame code;
the engine uses NAIF DE430 + ``moon_pa_de421`` through spiceypy. Horizons
reports *apparent* airless positions (light time, stellar aberration, light
bending); the engine reports *geometric* positions. To attribute the residual,
the same corrections are reproduced in SPICE (``spkcpo``, ``CN+S``): if that
reproduction matches Horizons closely, any engine/Horizons difference is the
documented geometric-vs-apparent choice, not a frame or time error.

    python -m src.ml.horizons_crosscheck            # uses cached responses
    python -m src.ml.horizons_crosscheck --refresh  # re-query Horizons (~1 min)

Horizons responses are cached in ``data/validation/horizons/`` so the check
and its test are reproducible offline.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from src.compute.terrain import DATA_DIR

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
CACHE_DIR = DATA_DIR / "validation" / "horizons"
REPORT = DATA_DIR / "validation" / "horizons_crosscheck.json"
START_UTC = "2026-11-15T00:00:00Z"
STOP_UTC = "2026-12-14T12:00:00Z"   # one synodic month
STEP = "6 h"
BODIES = {"sun": "10", "earth": "399"}


def catalog_sites() -> list[dict]:
    missions = json.loads((DATA_DIR / "missions.json").read_text(encoding="utf-8"))
    sites = []
    for mission in missions:
        site = mission.get("landing_site") or {}
        if site.get("latitude_deg") is not None and site.get("longitude_deg") is not None:
            sites.append({"id": mission["id"], "mission": mission["mission"],
                          "latitude_deg": site["latitude_deg"],
                          "longitude_deg": site["longitude_deg"]})
    return sites


def _query(site: dict, body: str) -> str:
    params = {
        "format": "text", "COMMAND": f"'{BODIES[body]}'", "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        # Altitude 0 km on Horizons' 1737.4 km sphere, matching the engine's observer.
        "SITE_COORD": f"'{site['longitude_deg']},{site['latitude_deg']},0'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'",
        "START_TIME": f"'{START_UTC[:16].replace('T', ' ')}'",
        "STOP_TIME": f"'{STOP_UTC[:16].replace('T', ' ')}'",
        "STEP_SIZE": f"'{STEP}'", "QUANTITIES": "'4'", "ANG_FORMAT": "'DEG'",
        "APPARENT": "'AIRLESS'", "CSV_FORMAT": "'YES'", "EXTRA_PREC": "'YES'",
        "TIME_DIGITS": "'SECONDS'",
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "ApolloHarness/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def fetch(site: dict, body: str, *, refresh: bool = False) -> Path:
    path = CACHE_DIR / f"{site['id']}__{body}.txt"
    if refresh or not path.is_file():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        text = _query(site, body)
        if "$$SOE" not in text:
            raise RuntimeError(f"Horizons returned no ephemeris for {site['id']}/{body}:\n{text[:800]}")
        path.write_text(text, encoding="utf-8")
        time.sleep(1.0)  # be polite to the public API
    return path


def parse(path: Path) -> tuple[list[str], np.ndarray, np.ndarray, dict]:
    text = path.read_text(encoding="utf-8")
    block = text.split("$$SOE")[1].split("$$EOE")[0]
    utc, az, el = [], [], []
    for line in block.strip().splitlines():
        fields = [f.strip() for f in line.split(",")]
        stamp = fields[0]  # e.g. 2026-Nov-15 00:00:00
        utc.append(stamp)
        az.append(float(fields[3]))
        el.append(float(fields[4]))
    meta = {}
    for key in ("Target body name", "Center pole/equ", "Center radii", "Atmos refraction"):
        line = next((l for l in text.splitlines() if l.startswith(key)), "")
        meta[key] = line.split(":", 1)[1].strip() if ":" in line else None
    return utc, np.array(az), np.array(el), meta


def _unit(az_deg: np.ndarray, el_deg: np.ndarray) -> np.ndarray:
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.column_stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)])


def _separation_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b), axis=1), np.sum(a * b, axis=1)))


def engine_positions(site: dict, utc: list[str]) -> dict[str, dict[str, np.ndarray]]:
    """Production geometric az/el, plus a SPICE reproduction of Horizons' apparent positions."""
    import spiceypy as spice
    from src.compute.spice_engine import (
        SPICE_LOCK, _elevation_azimuth, _site_frame_me, _topocentric_state, load_kernels,
    )
    out = {kind: {body: [] for body in BODIES} for kind in ("geometric", "apparent")}
    lat, lon = site["latitude_deg"], site["longitude_deg"]
    with SPICE_LOCK:
        load_kernels()
        position_me, (east, north, up) = _site_frame_me(lat, lon)
        for stamp in utc:
            et = spice.str2et(stamp + " UTC")
            state = _topocentric_state(lat, lon, et)
            out["geometric"]["sun"].append((state.sun_azimuth_deg, state.sun_elevation_deg))
            out["geometric"]["earth"].append((state.earth_azimuth_deg, state.earth_elevation_deg))
            for body, name in (("sun", "SUN"), ("earth", "EARTH")):
                vector, _ = spice.spkcpo(name, et, "MOON_ME", "OBSERVER", "CN+S",
                                         position_me.copy(), "MOON", "MOON_ME")
                elevation, azimuth = _elevation_azimuth(np.asarray(vector[:3]), east, north, up)
                out["apparent"][body].append((azimuth, elevation))
    return {kind: {body: np.array(values) for body, values in bodies.items()}
            for kind, bodies in out.items()}


def _summary(values: np.ndarray) -> dict[str, float]:
    return {"median": float(np.median(values)), "p95": float(np.percentile(values, 95)),
            "max": float(np.max(values))}


def run(*, refresh: bool = False) -> dict:
    sites = catalog_sites()
    rows = []
    pooled = {kind: {body: [] for body in BODIES} for kind in ("geometric", "apparent")}
    elevation_error = {body: [] for body in BODIES}
    sign_agree = {body: [0, 0] for body in BODIES}
    meta = None
    for site in sites:
        horizons = {body: parse(fetch(site, body, refresh=refresh)) for body in BODIES}
        meta = meta or horizons["sun"][3]
        utc = horizons["sun"][0]
        ours = engine_positions(site, utc)
        row = {"site_id": site["id"], "latitude_deg": site["latitude_deg"],
               "longitude_deg": site["longitude_deg"], "samples": len(utc)}
        for body in BODIES:
            _, az, el, _ = horizons[body]
            reference = _unit(az, el)
            for kind in ("geometric", "apparent"):
                mine = ours[kind][body]
                sep = _separation_deg(_unit(mine[:, 0], mine[:, 1]), reference)
                pooled[kind][body].append(sep)
                row[f"{body}_{kind}_max_sep_deg"] = float(sep.max())
            geometric_el = ours["geometric"][body][:, 1]
            elevation_error[body].append(np.abs(geometric_el - el))
            clear = np.abs(el) > 0.05  # skip samples grazing the spherical horizon
            sign_agree[body][0] += int(np.sum((geometric_el[clear] > 0) == (el[clear] > 0)))
            sign_agree[body][1] += int(np.sum(clear))
        rows.append(row)
    result = {
        "schema": "apolloharness.horizons_crosscheck.v1",
        "reference": "JPL Horizons API, observer table, QUANTITIES=4, APPARENT=AIRLESS",
        "reference_metadata": meta,
        "engine": "spice_engine._topocentric_state: DE430 + moon_pa_de421, geometric (abcorr NONE)",
        "window_utc": [START_UTC, STOP_UTC], "step": STEP, "sites": len(sites),
        "samples_per_body": int(sum(r["samples"] for r in rows)),
        "angular_separation_deg": {
            kind: {body: _summary(np.concatenate(pooled[kind][body])) for body in BODIES}
            for kind in pooled},
        "geometric_elevation_abs_error_deg": {
            body: _summary(np.concatenate(elevation_error[body])) for body in BODIES},
        "spherical_horizon_visibility_agreement": {
            body: {"agree": a, "compared": n, "fraction": a / n if n else None}
            for body, (a, n) in sign_agree.items()},
        "per_site": rows,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-check Sun/Earth positions vs JPL Horizons")
    parser.add_argument("--refresh", action="store_true", help="re-query Horizons instead of the cache")
    args = parser.parse_args(argv)
    result = run(refresh=args.refresh)
    print(json.dumps({k: result[k] for k in ("sites", "samples_per_body", "angular_separation_deg",
                                             "geometric_elevation_abs_error_deg",
                                             "spherical_horizon_visibility_agreement")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
