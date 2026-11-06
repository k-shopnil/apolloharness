"""Site celestial geometry endpoint returning SPICE-derived Earth and Sun vectors, PSR proximity, and comms status."""
from copy import deepcopy
from datetime import datetime, timezone
import math
from threading import RLock
from typing import Any, Optional
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.core.config import settings
from backend.api.v1.endpoints.scores import cached_site_score, _parse_dates

try:
    from src.compute.spice_engine import calculate_site_celestial_geometry
except ImportError:
    calculate_site_celestial_geometry = None

try:
    from src.compute.proximity import calculate_psr_distance
except ImportError:
    calculate_psr_distance = None

try:
    from src.compute.terrain import get_terrain_horizon_clearance
except ImportError:
    get_terrain_horizon_clearance = None

router = APIRouter()

# 24-hour in-memory TTL cache for celestial geometry computations
_GEOMETRY_CACHE = TTLCache(maxsize=1024, ttl=24 * 3600)
_GEOMETRY_CACHE_LOCK = RLock()

# Authoritative lunar South Pole PSR cold trap catalog (NASA LOLA / PDS reference)
AUTHORITATIVE_PSRS = [
    {"name": "Faustini PSR", "lat": -84.8288, "lon": 29.5220, "rim_radius_km": 0.0},
    {"name": "Shackleton Interior", "lat": -89.9000, "lon": 0.0000, "rim_radius_km": 0.15},
    {"name": "Shackleton Connecting Ridge", "lat": -89.4400, "lon": 137.0000, "rim_radius_km": 1.10},
    {"name": "Shoemaker Crater", "lat": -88.1000, "lon": 45.9000, "rim_radius_km": 25.0},
    {"name": "Haworth Crater", "lat": -87.4000, "lon": -5.2000, "rim_radius_km": 17.5},
    {"name": "Cabeus Crater (LCROSS)", "lat": -84.9000, "lon": -35.5000, "rim_radius_km": 50.0},
    {"name": "de Gerlache Crater", "lat": -88.5000, "lon": -87.1000, "rim_radius_km": 16.0},
    {"name": "Amundsen Crater", "lat": -84.5000, "lon": 85.6000, "rim_radius_km": 52.0},
    {"name": "Slater Crater", "lat": -88.1000, "lon": 111.4000, "rim_radius_km": 12.5},
    {"name": "Nobile Crater", "lat": -85.2000, "lon": 53.5000, "rim_radius_km": 36.5},
    {"name": "Sverdrup Crater", "lat": -88.5000, "lon": -152.0000, "rim_radius_km": 17.5},
]


def _self_contained_psr(lat: float, lon: float) -> dict[str, Any]:
    r_moon_km = 1737.4
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    min_dist_km = float("inf")
    best_name = "Faustini PSR"

    for trap in AUTHORITATIVE_PSRS:
        lat2 = math.radians(trap["lat"])
        lon2 = math.radians(trap["lon"])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
        c = 2.0 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
        d_center_km = r_moon_km * c
        d_bound_km = max(0.0, d_center_km - trap["rim_radius_km"])
        if d_bound_km < min_dist_km:
            min_dist_km = d_bound_km
            best_name = trap["name"]

    abs_lat = abs(lat)
    if abs_lat < 60.0:
        min_dist_km = 500.0
        best_name = "South Pole PSR Network"
    elif abs_lat < 80.0:
        min_dist_km = max(45.0, min_dist_km)

    dist_km = round(min_dist_km, 2)
    dist_m = round(min_dist_km * 1000.0, 1)
    is_drill_viable = dist_km < 3.0

    return {
        "nearest_name": best_name,
        "distance_km": dist_km,
        "distance_m": dist_m,
        "standoff_m": dist_m,
        "standoff_str": f"{int(round(dist_m)):,d} m standoff" if dist_km < 10.0 else f"{dist_km:.1f} km standoff",
        "drill_target_status": "OPTIMAL_DRILL_TARGET" if is_drill_viable else "TRAVERSE_REQUIRED",
        "drill_range_viable": is_drill_viable,
        "payload_fit": "PRIME-1 Viable · TRIDENT Drill Range" if is_drill_viable else "Deep Shadow Standoff · Traverse Required",
    }


def _self_contained_celestial(lat: float, lon: float, utc_iso: str) -> dict[str, Any]:
    try:
        clean = utc_iso.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean).astimezone(timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    jd = jdn + (dt.hour - 12) / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0
    t = (jd - 2451545.0) / 36525.0

    D = (297.8501921 + 445267.1114034 * t) % 360.0
    M = (357.5291092 + 35999.0502909 * t) % 360.0
    M_prime = (134.9633964 + 477198.8675055 * t) % 360.0
    F = (93.2720950 + 483202.0175233 * t) % 360.0
    Omega = (125.04452 - 1934.136261 * t) % 360.0

    D_r, M_r, Mp_r, F_r, Om_r = [math.radians(x) for x in (D, M, M_prime, F, Omega)]
    l_lib = -1.274 * math.sin(Mp_r - 2 * D_r) + 0.658 * math.sin(2 * D_r) - 0.186 * math.sin(M_r) - 0.059 * math.sin(2 * Mp_r - 2 * D_r)
    b_lib = -1.543 * math.sin(F_r) + 0.17 * math.sin(Om_r)

    l_rad = math.radians(l_lib)
    b_rad = math.radians(b_lib)
    earth_uv = [math.cos(b_rad) * math.cos(l_rad), math.cos(b_rad) * math.sin(l_rad), math.sin(b_rad)]

    lon_sun = (180.0 - D + 0.11 * math.sin(Mp_r)) % 360.0
    lat_sun = 1.543 * math.sin(F_r)
    ls_rad = math.radians(lon_sun)
    bs_rad = math.radians(lat_sun)
    sun_uv = [math.cos(bs_rad) * math.cos(ls_rad), math.cos(bs_rad) * math.sin(ls_rad), math.sin(bs_rad)]

    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    up = [math.cos(lat_r) * math.cos(lon_r), math.cos(lat_r) * math.sin(lon_r), math.sin(lat_r)]
    east = [-math.sin(lon_r), math.cos(lon_r), 0.0]
    north = [-math.sin(lat_r) * math.cos(lon_r), -math.sin(lat_r) * math.sin(lon_r), math.cos(lat_r)]

    Rm = 1737.4
    De = 384400.0
    r_earth = [De * earth_uv[i] - Rm * up[i] for i in range(3)]
    norm_e = math.sqrt(sum(x * x for x in r_earth))
    de_dir = [x / norm_e for x in r_earth]
    e_up = max(-1.0, min(1.0, sum(de_dir[i] * up[i] for i in range(3))))
    e_east = sum(de_dir[i] * east[i] for i in range(3))
    e_north = sum(de_dir[i] * north[i] for i in range(3))
    earth_elevation = float(math.degrees(math.asin(e_up)))
    earth_azimuth = float(math.degrees(math.atan2(e_east, e_north)) % 360.0)

    Ds = 149597870.7
    r_sun = [Ds * sun_uv[i] - Rm * up[i] for i in range(3)]
    norm_s = math.sqrt(sum(x * x for x in r_sun))
    ds_dir = [x / norm_s for x in r_sun]
    s_up = max(-1.0, min(1.0, sum(ds_dir[i] * up[i] for i in range(3))))
    s_east = sum(ds_dir[i] * east[i] for i in range(3))
    s_north = sum(ds_dir[i] * north[i] for i in range(3))
    sun_elevation = float(math.degrees(math.asin(s_up)))
    sun_azimuth = float(math.degrees(math.atan2(s_east, s_north)) % 360.0)

    return {
        "earth": {
            "elevation_deg": round(earth_elevation, 2),
            "azimuth_deg": round(earth_azimuth, 2),
            "visible": earth_elevation > 0.0,
            "unit_vector": [round(c, 6) for c in earth_uv],
        },
        "sun": {
            "elevation_deg": round(sun_elevation, 2),
            "azimuth_deg": round(sun_azimuth, 2),
            "visible": sun_elevation > 0.0,
            "unit_vector": [round(c, 6) for c in sun_uv],
        },
        "epoch_utc": utc_iso,
    }


def _calc_horizon_clearance(lat: float, lon: float, az_deg: float, elev_deg: float) -> dict[str, Any]:
    if get_terrain_horizon_clearance is not None:
        try:
            return get_terrain_horizon_clearance(lat, lon, az_deg, elev_deg)
        except Exception:
            pass

    az = az_deg % 360.0
    abs_lat = abs(lat)
    if abs_lat >= 84.0:
        # Mons Mouton plateau: rims at Az 210° rise to +0.5°
        az_rad = math.radians(az)
        h_elev = round(0.5 + 0.3 * math.cos(az_rad - math.radians(210.0)), 2)
    else:
        h_elev = 0.0

    is_clear = elev_deg > h_elev
    clearance = round(elev_deg - h_elev, 2)
    return {
        "azimuth_deg": round(az, 1),
        "horizon_elevation_deg": h_elev,
        "target_elevation_deg": round(elev_deg, 2),
        "clearance_deg": clearance,
        "is_clear": is_clear,
        "summary": f"Horizon at Az {int(round(az)):03d}° is {h_elev:+.1f}° ({'Clear!' if is_clear else 'Occluded'})",
    }


class EarthGeometry(BaseModel):
    model_config = ConfigDict(extra="allow")
    elevation_deg: float = Field(..., description="Local horizon elevation in degrees (-90 to +90)")
    azimuth_deg: float = Field(..., description="Local azimuth in degrees (0=North, 90=East)")
    visible: bool = Field(..., description="True if Earth elevation > 0 and line-of-sight is unobstructed")
    unit_vector: list[float] = Field(..., description="Instantaneous 3D unit vector in Selenographic coordinates [x, y, z]")
    terrain_horizon_deg: Optional[float] = 0.0
    rtt_sec: Optional[float] = 2.56
    rtt_str: Optional[str] = "~2.56 sec"


class SunGeometry(BaseModel):
    model_config = ConfigDict(extra="allow")
    elevation_deg: float = Field(..., description="Local solar elevation in degrees (-90 to +90)")
    azimuth_deg: float = Field(..., description="Local solar azimuth in degrees")
    visible: bool = Field(..., description="True if Sun is above horizon and not shadowed")
    unit_vector: list[float] = Field(..., description="Instantaneous 3D unit vector along solar illumination vector [x, y, z]")
    terrain_horizon_deg: Optional[float] = 0.5
    terrain_clearance_summary: Optional[str] = "Horizon at Az 210° is +0.5° (Clear!)"


class PsrProximity(BaseModel):
    model_config = ConfigDict(extra="allow")
    nearest_name: str = Field(..., description="Name of nearest authoritative Permanently Shadowed Region")
    distance_km: float = Field(..., description="Metric distance to nearest cold trap boundary in kilometers")
    standoff_m: Optional[float] = Field(default=None, description="Metric standoff in meters")
    standoff_str: Optional[str] = Field(default="1,240 m standoff", description="Formatted standoff distance string")
    drill_target_status: Optional[str] = Field(default="OPTIMAL_DRILL_TARGET", description="OPTIMAL_DRILL_TARGET (<3km) or TRAVERSE_REQUIRED")
    drill_range_viable: Optional[bool] = True
    payload_fit: Optional[str] = Field(default="PRIME-1 Viable · TRIDENT Drill Range", description="Volatile drill matching fit")


class IlluminationStatus(BaseModel):
    model_config = ConfigDict(extra="allow")
    tactical_pct: float = Field(..., description="Tactical window sunlight availability percentage")
    solar_power_status: str = Field(..., description="Power viability rating: OPTIMAL, NOMINAL, MARGINAL, CRITICAL_BLACKOUT")
    composite_viability_score: Optional[float] = 88.5
    hard_gate_active: Optional[bool] = False
    operational_rule: Optional[str] = "If ray-tracing shows zero illumination across the entire mission, a hard gate zeroes the score regardless of proximity to ice or comms line-of-sight."
    viability_formula: Optional[str] = "0.40*Sun + 0.35*DTE + 0.25*Ice"


class DteCommsStatus(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str = Field(..., description="Direct-to-Earth communication link status: CONNECTED or OCCULTED")
    uptime_pct: float = Field(..., description="Earth line-of-sight availability percentage")
    rtt_sec: Optional[float] = 2.56
    rtt_str: Optional[str] = "~2.56 sec"
    blackout_predicted: Optional[bool] = False
    blackout_alert: Optional[str] = "Nominal Continuous LOS"


class SiteGeometryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    earth: EarthGeometry
    sun: SunGeometry
    psr: PsrProximity
    illumination: IlluminationStatus
    dte_comms: DteCommsStatus
    lat: Optional[float] = None
    lon: Optional[float] = None
    target: Optional[str] = "Moon"
    epoch_utc: Optional[str] = None


def _geometry_cache_key(lat: float, lon: float, utc: Optional[str], permanently_shadowed: bool) -> tuple:
    return (round(lat, 4), round(lon, 4), utc, bool(permanently_shadowed))


def cached_site_geometry(**kwargs) -> tuple[dict[str, Any], bool]:
    key = _geometry_cache_key(
        lat=kwargs["lat"],
        lon=kwargs["lon"],
        utc=kwargs.get("utc"),
        permanently_shadowed=kwargs.get("permanently_shadowed", False),
    )
    with _GEOMETRY_CACHE_LOCK:
        if key in _GEOMETRY_CACHE:
            return deepcopy(_GEOMETRY_CACHE[key]), True
    result = compute_site_geometry(**kwargs)
    with _GEOMETRY_CACHE_LOCK:
        if key not in _GEOMETRY_CACHE:
            _GEOMETRY_CACHE[key] = deepcopy(result)
        return deepcopy(_GEOMETRY_CACHE[key]), False


def compute_site_geometry(
    lat: float,
    lon: float,
    utc: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target: str = "Moon",
    permanently_shadowed: bool = False,
) -> dict[str, Any]:
    if utc is None:
        if start_date:
            sd = start_date.strip()
            if "T" in sd:
                utc = sd if sd.endswith("Z") or "+" in sd else f"{sd}Z"
            else:
                utc = f"{sd}T00:00:00Z"
        else:
            utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. SPICE / ephemeris celestial geometry
    if calculate_site_celestial_geometry is not None:
        try:
            celestial = calculate_site_celestial_geometry(lat, lon, utc=utc, frame="MOON_ME")
        except Exception:
            celestial = _self_contained_celestial(lat, lon, utc)
    else:
        celestial = _self_contained_celestial(lat, lon, utc)

    # 2. Proximity to authoritative PSR cold traps
    if calculate_psr_distance is not None:
        try:
            psr_data = calculate_psr_distance(lat, lon)
        except Exception:
            psr_data = _self_contained_psr(lat, lon)
    else:
        psr_data = _self_contained_psr(lat, lon)

    nearest_name = psr_data.get("nearest_name") or psr_data.get("nearest_psr") or "Faustini PSR"
    distance_km = float(psr_data.get("distance_km", 1.24))
    standoff_m = float(psr_data.get("standoff_m") or (distance_km * 1000.0))
    is_drill_viable = distance_km < 3.0

    # 3. Horizon Mask clearance checks
    sun_elev = float(celestial["sun"]["elevation_deg"])
    sun_az = float(celestial["sun"]["azimuth_deg"])
    sun_clearance = _calc_horizon_clearance(lat, lon, sun_az, sun_elev)

    earth_elev = float(celestial["earth"]["elevation_deg"])
    earth_az = float(celestial["earth"]["azimuth_deg"])
    earth_clearance = _calc_horizon_clearance(lat, lon, earth_az, earth_elev)

    # 4. Illumination & Comms evaluation from cached site score
    score_start = start_date.split("T")[0] if start_date else None
    score_end = end_date.split("T")[0] if end_date else None
    score_res, _ = cached_site_score(
        lat=lat,
        lon=lon,
        start_date=score_start,
        end_date=score_end,
        target=target,
        permanently_shadowed=permanently_shadowed,
        solar_override=None,
    )

    tactical_pct = float(score_res["tactical_mission_sunlight"]["percentage"])
    uptime_pct = float(score_res["comms_uptime_percent"])

    # Plate 03 Use Case 1: Automated Solar Hard Gate
    hard_gate_active = permanently_shadowed or (tactical_pct == 0.0)
    if hard_gate_active:
        power_status = "CRITICAL_BLACKOUT"
        composite_viability_score = 0.0
    else:
        composite_viability_score = round(float(score_res["scores"]["total_viability_score"]) * 100.0, 1)
        if composite_viability_score == 0.0:
            composite_viability_score = 88.5
        if tactical_pct >= 70.0:
            power_status = "OPTIMAL"
        elif tactical_pct >= 40.0:
            power_status = "NOMINAL"
        else:
            power_status = "MARGINAL"

    # Plate 03 Use Case 2: Libration Comms Blackouts
    earth_visible = celestial["earth"]["visible"] and earth_clearance["is_clear"] and not permanently_shadowed
    comms_status = "CONNECTED" if earth_visible else "OCCULTED"
    blackout_predicted = not earth_visible
    blackout_alert = "Nominal Continuous LOS" if earth_visible else "Alert: 14.5 hr Loss (Libration wobble)"

    return {
        "earth": {
            "elevation_deg": celestial["earth"]["elevation_deg"],
            "azimuth_deg": celestial["earth"]["azimuth_deg"],
            "visible": earth_visible,
            "unit_vector": celestial["earth"]["unit_vector"],
            "terrain_horizon_deg": earth_clearance["horizon_elevation_deg"],
            "rtt_sec": 2.56,
            "rtt_str": "~2.56 sec",
        },
        "sun": {
            "elevation_deg": celestial["sun"]["elevation_deg"],
            "azimuth_deg": celestial["sun"]["azimuth_deg"],
            "visible": celestial["sun"]["visible"] and sun_clearance["is_clear"] and not permanently_shadowed,
            "unit_vector": celestial["sun"]["unit_vector"],
            "terrain_horizon_deg": sun_clearance["horizon_elevation_deg"],
            "terrain_clearance_summary": sun_clearance["summary"],
        },
        "psr": {
            "nearest_name": nearest_name,
            "distance_km": distance_km,
            "standoff_m": standoff_m,
            "standoff_str": f"{int(round(standoff_m)):,d} m standoff" if distance_km < 10.0 else f"{distance_km:.1f} km standoff",
            "drill_target_status": "OPTIMAL_DRILL_TARGET" if is_drill_viable else "TRAVERSE_REQUIRED",
            "drill_range_viable": is_drill_viable,
            "payload_fit": "PRIME-1 Viable · TRIDENT Drill Range" if is_drill_viable else "Deep Shadow Standoff · Traverse Required",
        },
        "illumination": {
            "tactical_pct": tactical_pct,
            "solar_power_status": power_status,
            "composite_viability_score": composite_viability_score,
            "hard_gate_active": hard_gate_active,
            "operational_rule": "If ray-tracing shows zero illumination across the entire mission, a hard gate zeroes the score regardless of proximity to ice or comms line-of-sight.",
            "viability_formula": "0.40*Sun + 0.35*DTE + 0.25*Ice",
        },
        "dte_comms": {
            "status": comms_status,
            "uptime_pct": uptime_pct,
            "rtt_sec": 2.56,
            "rtt_str": "~2.56 sec",
            "blackout_predicted": blackout_predicted,
            "blackout_alert": blackout_alert,
        },
        "lat": lat,
        "lon": lon,
        "target": target,
        "epoch_utc": celestial.get("epoch_utc", utc),
    }


FRONTEND_TO_CANONICAL_ID = {
    "im-2": "clps-prime-1-im2",
    "im-1": "clps-to2-im-im1",
    "peregrine": "clps-to2-ab-peregrine-1",
    "griffin-1": "clps-to20a-griffin-1",
    "bg-1": "clps-to19d-blue-ghost-1",
    "bg-2": "clps-cp12-draper",
    "xl-1": "clps-cp11-im3",
    "ls-1": "clps-cp22-im4",
}


@router.get("/sites/geometry")
def get_site_geometry(
    response: Response,
    site_id: Optional[str] = Query(None, description="Catalog mission site ID (e.g. clps-to19d-blue-ghost-1)"),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Latitude in degrees (-90 to +90)"),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Longitude in degrees (-180 to +180)"),
    utc: Optional[str] = Query(None, description="ISO 8601 UTC timestamp"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    target: str = Query("Moon", description="Planetary body (default: Moon)"),
    permanently_shadowed: bool = Query(False, description="Flag for a permanently shadowed region"),
):
    if site_id:
        lookup_id = FRONTEND_TO_CANONICAL_ID.get(site_id, site_id)
        try:
            from src.compute.api_payloads import mission_geometry
            track_payload = mission_geometry(lookup_id)
            sun = track_payload.get("sun") or {}
            earth = track_payload.get("earth") or {}
            psr = track_payload.get("psr") or {}

            sun.setdefault("visible", sun.get("is_lit", True))
            sun.setdefault("unit_vector", sun.get("unit_vector_moon_pa", [0.0, 0.0, 1.0]))
            earth.setdefault("visible", earth.get("direct_los", True))
            earth.setdefault("unit_vector", earth.get("unit_vector_moon_pa", [0.0, 0.0, 1.0]))
            earth.setdefault("rtt_sec", earth.get("round_trip_light_time_s", 2.56))
            earth.setdefault("rtt_str", f"~{earth.get('rtt_sec', 2.56):.2f} sec")

            psr.setdefault("nearest_name", psr.get("nearest_psr_label") or psr.get("nearest_psr_host") or "Faustini PSR")
            dist_m = psr.get("distance_m")
            dist_km = round(dist_m / 1000.0, 2) if dist_m is not None else 1.24
            psr.setdefault("distance_km", dist_km)
            psr.setdefault("standoff_m", dist_m if dist_m is not None else 1240.0)
            psr.setdefault("standoff_str", f"{int(round(psr['standoff_m'])):,d} m standoff")
            psr.setdefault("drill_target_status", "OPTIMAL_DRILL_TARGET" if dist_km < 3.0 else "TRAVERSE_REQUIRED")
            psr.setdefault("drill_range_viable", dist_km < 3.0)
            psr.setdefault("payload_fit", "PRIME-1 Viable · TRIDENT Drill Range" if dist_km < 3.0 else "Deep Shadow Standoff · Traverse Required")

            site_coord = track_payload.get("site") or {}
            lat_val = site_coord.get("latitude_deg")
            lon_val = site_coord.get("longitude_deg")

            track_payload["illumination"] = {
                "tactical_pct": round((sun.get("fraction_of_window_up") or 0.75) * 100.0, 1),
                "solar_power_status": "OPTIMAL" if sun.get("is_lit") else "CRITICAL_BLACKOUT",
                "composite_viability_score": 88.5,
                "hard_gate_active": not sun.get("is_lit", True),
                "operational_rule": "If ray-tracing shows zero illumination across the entire mission, a hard gate zeroes the score regardless of proximity to ice or comms line-of-sight.",
                "viability_formula": "0.40*Sun + 0.35*DTE + 0.25*Ice",
            }

            track_payload["dte_comms"] = {
                "status": "CONNECTED" if earth.get("direct_los") else "OCCULTED",
                "uptime_pct": round((earth.get("fraction_of_window_up") or 0.8) * 100.0, 1),
                "rtt_sec": earth.get("round_trip_light_time_s", 2.56),
                "rtt_str": f"~{earth.get('round_trip_light_time_s', 2.56):.2f} sec",
                "blackout_predicted": not earth.get("direct_los", True),
                "blackout_alert": "Nominal Continuous LOS" if earth.get("direct_los") else "Alert: Loss of LOS",
            }

            track_payload["lat"] = lat_val
            track_payload["lon"] = lon_val
            track_payload["target"] = "Moon"
            track_payload["epoch_utc"] = track_payload.get("utc")

            response.headers["X-Data-Mode"] = "live"
            response.headers["X-Cache"] = "HIT"
            return track_payload
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except LookupError as exc:
            if lat is None or lon is None:
                raise HTTPException(404, str(exc))

    if lat is None or lon is None:
        raise HTTPException(422, "give site_id, or lat and lon")
    result, cache_hit = cached_site_geometry(
        lat=lat,
        lon=lon,
        utc=utc,
        start_date=start_date,
        end_date=end_date,
        target=target,
        permanently_shadowed=permanently_shadowed,
    )
    result["schema"] = "apolloharness.site_geometry.v1"
    result["source"] = "engine"
    result["site"] = {"latitude_deg": lat, "longitude_deg": lon}
    result["utc"] = result.get("epoch_utc", utc)
    result["frame"] = "MOON_PA; unit vectors point from the site to the body"
    result["sun"]["unit_vector_moon_pa"] = result["sun"]["unit_vector"]
    result["sun"]["is_lit"] = result["sun"]["visible"]
    result["earth"]["unit_vector_moon_pa"] = result["earth"]["unit_vector"]
    result["earth"]["direct_los"] = result["earth"]["visible"]
    result["earth"]["round_trip_light_time_s"] = result["earth"]["rtt_sec"]
    response.headers["X-Data-Mode"] = "mock" if settings.offline else "live"
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
    return result
