import json
import httpx
import pytest
from backend.core.config import settings
from backend.main import app

SAMPLE = [
    {
        "id": "clps-test-mission-1",
        "mission": "Test Mission 1",
        "category": "clps",
        "provider": "Test Provider",
        "lander": "Test Lander",
        "status": "planned",
        "target_site": "Test Site",
        "landing_site": {
            "latitude_deg": -89.5,
            "longitude_deg": 0.0,
            "coordinate_type": "target_landing_ellipse_center",
        },
        "target_date": "2026-11-01",
        "touchdown_utc": None,
        "landing_ellipse_km": {
            "major_axis_km": 1.2,
            "minor_axis_km": 0.6,
        },
        "payload_summary": "Test payloads",
        "payloads": [
            {"name": "ShadowCam-2", "purpose": ["Optical Imager"]}
        ],
    }
]


from fastapi.testclient import TestClient

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    data, fixtures = tmp_path / "data", tmp_path / "demo_fixtures"
    data.mkdir()
    fixtures.mkdir()
    monkeypatch.setattr(settings, "data_dir", data)
    monkeypatch.setattr(settings, "fixtures_dir", fixtures)
    monkeypatch.setattr(settings, "offline", False)
    return data, fixtures


def write(path, payload):
    (path / "missions.json").write_text(json.dumps(payload), encoding="utf-8")


# --- Catalog Fallback & Data Mode Tests ---

def test_serves_live_catalog(client, dirs):
    data, _ = dirs
    write(data, SAMPLE)
    r = client.get("/api/v1/missions")
    assert r.status_code == 200
    assert r.headers["X-Data-Mode"] == "live"
    assert r.json()[0]["id"] == "clps-test-mission-1"


def test_falls_back_when_primary_missing(client, dirs):
    _, fixtures = dirs
    write(fixtures, SAMPLE)
    r = client.get("/api/v1/missions")
    assert r.status_code == 200
    assert r.headers["X-Data-Mode"] in ("offline", "mock")
    assert r.json()[0]["id"] == "clps-test-mission-1"


def test_offline_mode_ignores_primary(client, dirs, monkeypatch):
    data, fixtures = dirs
    write(data, [{"id": "live", "mission": "Live Mission", "landing_site": {"latitude_deg": 0.0, "longitude_deg": 0.0}}])
    write(fixtures, SAMPLE)
    monkeypatch.setattr(settings, "offline", True)
    r = client.get("/api/v1/missions")
    assert r.headers["X-Data-Mode"] in ("offline", "mock")
    assert r.json()[0]["id"] == "clps-test-mission-1"


def test_returns_503_when_no_catalog(client, dirs):
    assert client.get("/api/v1/missions").status_code == 503


# --- Schema Structure & Payload Types Contract Tests ---

def test_missions_schema_and_payload_array_types(client):
    r = client.get("/api/v1/missions")
    assert r.status_code == 200
    missions = r.json()
    assert isinstance(missions, list)
    assert len(missions) == 16

    for m in missions:
        # Core identification
        assert isinstance(m["id"], str) and len(m["id"]) > 0
        assert isinstance(m["name"], str) and len(m["name"]) > 0
        assert m["category"] in ("clps", "reference_anchor")
        if m["lat"] is not None:
            assert -90.0 <= m["lat"] <= 90.0
            assert -180.0 <= m["lon"] <= 180.0
        else:
            assert m["lon"] is None

        # Landing ellipse schema: null = unknown, never defaulted
        ellipse = m.get("landing_ellipse")
        if ellipse is not None:
            assert "major_axis_km" in ellipse

        # Structured payload instrument array types
        instruments = m.get("payload_instruments")
        assert isinstance(instruments, list), f"payload_instruments for {m['id']} must be a list"
        for inst in instruments:
            assert isinstance(inst["name"], str) and len(inst["name"]) > 0
            assert isinstance(inst["type"], str)


# --- Site Scoring Endpoint Contract Tests ---

def test_sites_score_structure_tactical_and_strategic(client):
    params = {
        "lat": -89.5,
        "lon": 0.0,
        "start_date": "2026-11-01",
        "end_date": "2027-02-15",
    }
    r = client.get("/api/v1/sites/score", params=params)
    assert r.status_code == 200
    data = r.json()

    # Tactical sunlight structure
    assert "tactical_mission_sunlight" in data
    tactical = data["tactical_mission_sunlight"]
    assert 0.0 <= tactical["percentage"] <= 100.0
    assert tactical["sunlight_hours"] >= 0.0
    assert tactical["window_days"] > 0
    assert isinstance(tactical["description"], str)

    # Strategic annual baseline structure
    assert "strategic_annual_baseline" in data
    strategic = data["strategic_annual_baseline"]
    assert 0.0 <= strategic["percentage"] <= 100.0
    assert 0.0 <= strategic["annual_sunlight_fraction"] <= 1.0
    assert isinstance(strategic["description"], str)

    # Viability scores
    assert "scores" in data
    scores = data["scores"]
    assert 0.0 <= scores["solar_viability"] <= 1.0
    assert 0.0 <= scores["earth_comms_viability"] <= 1.0
    assert 0.0 <= scores["ice_proximity_viability"] <= 1.0
    assert 0.0 <= scores["total_viability_score"] <= 1.0
    assert isinstance(scores["hard_gate_triggered"], bool)

    # Hard gate rule object
    assert "hard_gate_rule" in data
    rule = data["hard_gate_rule"]
    assert "solar_gate_passed" in rule
    assert rule["solar_gate_passed"] is True


def test_extreme_polar_coordinates(client):
    """Test extreme polar coordinates (89.5 S - Shackleton Rim)."""
    params = {
        "lat": -89.5,
        "lon": 0.0,
        "start_date": "2026-11-01",
        "end_date": "2027-02-15",
    }
    r = client.get("/api/v1/sites/score", params=params)
    assert r.status_code == 200
    data = r.json()

    # Shackleton rim enjoys persistent grazing sunlight in austral summer
    assert data["tactical_mission_sunlight"]["percentage"] >= 75.0
    assert data["strategic_annual_baseline"]["percentage"] >= 70.0
    # Polar cold traps offer high ice proximity
    assert data["scores"]["ice_proximity_viability"] >= 0.90
    # Near side libration allows periodic Earth comms
    assert data["scores"]["earth_comms_viability"] >= 0.70
    assert data["scores"]["total_viability_score"] > 0.70


def test_equatorial_landing_site_blue_ghost_1(client):
    """Test equatorial landing site: Blue Ghost 1 at Mare Crisium (18.56 N, 61.81 E)."""
    params = {
        "lat": 18.56,
        "lon": 61.81,
        "start_date": "2024-11-15",
        "end_date": "2024-12-05",
    }
    r = client.get("/api/v1/sites/score", params=params)
    assert r.status_code == 200
    data = r.json()

    # Equatorial lunar surface experiences ~50% diurnal illumination
    assert round(data["tactical_mission_sunlight"]["percentage"]) == 50
    assert round(data["strategic_annual_baseline"]["percentage"]) == 50
    # High direct Earth line of sight on near side
    assert data["scores"]["earth_comms_viability"] >= 0.85
    # Equatorial heat eliminates surface volatile ice
    assert data["scores"]["ice_proximity_viability"] <= 0.15
    assert data["scores"]["hard_gate_triggered"] is False
    assert data["scores"]["total_viability_score"] > 0.0


def test_missing_date_ranges_handled_gracefully(client):
    """Verify endpoint gracefully computes baseline when dates are omitted."""
    params = {"lat": 0.674, "lon": 23.473}
    r = client.get("/api/v1/sites/score", params=params)
    assert r.status_code == 200
    data = r.json()
    assert data["tactical_mission_sunlight"]["window_days"] > 0
    assert data["scores"]["total_viability_score"] > 0


def test_malformed_and_invalid_date_ranges(client):
    """Verify error responses for invalid date strings or end_date < start_date."""
    # Malformed start date
    r1 = client.get("/api/v1/sites/score", params={"lat": 0.0, "lon": 0.0, "start_date": "bad-date"})
    assert r1.status_code == 400
    assert "Malformed" in r1.json()["detail"]

    # Malformed end date
    r2 = client.get("/api/v1/sites/score", params={"lat": 0.0, "lon": 0.0, "end_date": "2026-99-99"})
    assert r2.status_code == 400

    # Inverted date range (end_date earlier than start_date)
    r3 = client.get(
        "/api/v1/sites/score",
        params={"lat": 0.0, "lon": 0.0, "start_date": "2027-01-01", "end_date": "2026-01-01"},
    )
    assert r3.status_code == 400
    assert "cannot be before" in r3.json()["detail"]


def test_out_of_bounds_coordinates(client):
    """Verify coordinate bounds [-90, 90] and [-180, 180] are enforced."""
    r_lat = client.get("/api/v1/sites/score", params={"lat": 95.0, "lon": 0.0})
    assert r_lat.status_code == 422

    r_lon = client.get("/api/v1/sites/score", params={"lat": 0.0, "lon": 200.0})
    assert r_lon.status_code == 422


def test_hard_gate_rule_zero_solar_viability(client):
    """
    Validate the hard-gate rule:
    If solar power viability is zero (e.g. permanent shadow on a crater floor),
    the total viability score must return 0, regardless of comms or ice proximity.
    """
    # Case 1: Permanently shadowed region (Crater floor)
    params_psr = {
        "lat": -89.9,
        "lon": 0.0,
        "permanently_shadowed": True,
    }
    r = client.get("/api/v1/sites/score", params=params_psr)
    assert r.status_code == 200
    data = r.json()

    # Ice proximity is maximum (1.0) and comms may be high, but solar viability is 0
    assert data["scores"]["ice_proximity_viability"] == 1.0
    assert data["scores"]["solar_viability"] == 0.0
    # HARD GATE ASSERTIONS:
    assert data["scores"]["total_viability_score"] == 0.0
    assert data["scores"]["hard_gate_triggered"] is True
    assert data["hard_gate_rule"]["solar_gate_passed"] is False
    assert data["hard_gate_rule"]["triggered"] is True
    assert "Zero solar power" in data["hard_gate_rule"]["reason"]

    # Case 2: Solar viability forced to 0 via override at high-comms site
    params_override = {
        "lat": 0.0,
        "lon": 0.0,
        "solar_override": 0.0,
    }
    r2 = client.get("/api/v1/sites/score", params=params_override)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["scores"]["solar_viability"] == 0.0
    assert data2["scores"]["total_viability_score"] == 0.0
    assert data2["scores"]["hard_gate_triggered"] is True


def test_health_endpoint(client):
    """Verify system health endpoint."""
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["missions_count"] > 0


def test_sites_comms_endpoint_returns_estimate(client):
    response = client.get("/api/v1/sites/comms", params={"lat": -89.5, "lon": 0.0})
    assert response.status_code == 200
    body = response.json()
    assert body["target"] == "Moon"
    assert 0.0 <= body["earth_comms_viability"] <= 1.0
    assert body["direct_to_earth_possible"] is True
    assert body["model_status"] == "heuristic_demo_estimate"
    assert response.headers["X-Cache"] in {"HIT", "MISS"}


def test_sites_comms_validates_coordinate_bounds(client):
    response = client.get("/api/v1/sites/comms", params={"lat": 95, "lon": 0})
    assert response.status_code == 422


def test_site_score_cache_sets_cache_headers(client):
    params = {"lat": -77.0, "lon": 15.0, "target": "Moon"}
    first = client.get("/api/v1/sites/score", params=params)
    second = client.get("/api/v1/sites/score", params=params)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] in {"HIT", "MISS"}
    assert second.headers["X-Cache"] == "HIT"
    assert first.json() == second.json()


def test_cors_allows_configured_frontend_origin(client):
    response = client.options(
        "/api/v1/missions",
        headers={
            "Origin": "https://chhayanautical.web.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://chhayanautical.web.app"


def test_cors_does_not_allow_unknown_origin(client):
    response = client.options(
        "/api/v1/missions",
        headers={
            "Origin": "https://not-our-frontend.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_sites_geometry_endpoint_full_contract(client):
    """Verify GET /api/v1/sites/geometry returns SPICE earth/sun vectors, psr, illumination, comms."""
    response = client.get(
        "/api/v1/sites/geometry",
        params={"lat": -84.79, "lon": 29.20, "start_date": "2026-11-01", "end_date": "2027-02-15"}
    )
    assert response.status_code == 200
    body = response.json()

    assert "earth" in body
    earth = body["earth"]
    assert isinstance(earth["elevation_deg"], (int, float))
    assert isinstance(earth["azimuth_deg"], (int, float))
    assert isinstance(earth["visible"], bool)
    assert len(earth["unit_vector"]) == 3
    uv_mag = sum(x**2 for x in earth["unit_vector"])**0.5
    assert abs(uv_mag - 1.0) < 0.01

    assert "sun" in body
    sun = body["sun"]
    assert isinstance(sun["elevation_deg"], (int, float))
    assert isinstance(sun["azimuth_deg"], (int, float))
    assert isinstance(sun["visible"], bool)
    assert len(sun["unit_vector"]) == 3

    assert "psr" in body
    assert body["psr"]["nearest_name"] in ("Faustini Rim", "Faustini PSR")
    assert 0.1 <= body["psr"]["distance_km"] <= 3.0

    assert "illumination" in body
    assert body["illumination"]["tactical_pct"] >= 0.0
    assert body["illumination"]["solar_power_status"] in ("OPTIMAL", "NOMINAL", "MARGINAL", "CRITICAL_BLACKOUT")

    assert "dte_comms" in body
    assert body["dte_comms"]["status"] in ("CONNECTED", "OCCULTED")
    assert 0.0 <= body["dte_comms"]["uptime_pct"] <= 100.0


def test_sites_geometry_extreme_polar_and_farside(client):
    """Verify geometry logic for Shackleton south pole rim and far side."""
    r_pole = client.get("/api/v1/sites/geometry", params={"lat": -89.9, "lon": 0.0})
    assert r_pole.status_code == 200
    pole_data = r_pole.json()
    assert "Shackleton" in pole_data["psr"]["nearest_name"]

    r_far = client.get("/api/v1/sites/geometry", params={"lat": 0.0, "lon": 180.0})
    assert r_far.status_code == 200
    far_data = r_far.json()
    assert far_data["earth"]["elevation_deg"] < -80.0
    assert far_data["earth"]["visible"] is False
    assert far_data["dte_comms"]["status"] == "OCCULTED"


def test_engine_outputs_science_contract(client):
    """Verify physical engine boundaries and catalog mission contracts."""
    # 1. Earth RTT within physical range [2.3s, 2.8s]
    r_im2 = client.get("/api/v1/sites/geometry", params={"site_id": "clps-prime-1-im2"})
    assert r_im2.status_code == 200
    im2 = r_im2.json()
    rtt = im2["earth"]["round_trip_light_time_s"]
    assert 2.3 <= rtt <= 2.8, f"RTT {rtt}s outside [2.3, 2.8]"

    # 2. Chang'e 4 far side direct line-of-sight occultation
    r_ce4 = client.get("/api/v1/sites/geometry", params={"site_id": "anchor-change-4"})
    assert r_ce4.status_code == 200
    ce4 = r_ce4.json()
    assert ce4["earth"]["direct_los"] is False
    assert ce4["earth"]["countdown_status"] == "no_earthrise_within_window"

    # 3. Apollo 17 terrain model verification
    r_a17 = client.get("/api/v1/sites/geometry", params={"site_id": "anchor-apollo-17"})
    assert r_a17.status_code == 200
    a17 = r_a17.json()
    assert a17["horizon_model"] == "lola_terrain_mask"
    assert a17["terrain"]["dem_product"] == "LOLA GDR LDEM_64"

    # 4. Sunset hours and formatted string both present or both null
    sun = im2["sun"]
    if sun["time_to_sunset_hours"] is not None:
        assert sun["time_to_sunset_formatted"] is not None
    else:
        assert sun["time_to_sunset_formatted"] is None

