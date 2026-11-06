"""Automated tests for offline resilience and fixture fallback."""
import os
import socket
import time
from fastapi.testclient import TestClient
import pytest
from backend.core.config import settings
from backend.main import app


class NetworkBlockedError(RuntimeError):
    """Raised when an outbound network call is attempted in offline mode."""
    pass


@pytest.fixture(autouse=True)
def enforce_offline_and_block_network(monkeypatch):
    """
    Simulate strict offline conditions:
    1. Set OFFLINE=1 and settings.offline = True
    2. Guard socket connection attempts to block any external network access
    """
    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setattr(settings, "offline", True)

    orig_connect = socket.socket.connect

    def blocked_connect(self, *args, **kwargs):
        target = args[0] if args else kwargs.get("address")
        host = target[0] if isinstance(target, tuple) and len(target) > 0 else target
        # Allow internal Windows asyncio loop self-pipe loopback
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, *args, **kwargs)
        raise NetworkBlockedError(f"Network call blocked: OFFLINE mode is active! Target: {target}")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_offline_mode_returns_mock_header(client):
    """Verify that in offline mode, X-Data-Mode is set to mock."""
    r = client.get("/api/v1/missions")
    assert r.status_code == 200
    assert r.headers["X-Data-Mode"] == "mock"


def test_offline_missions_fall_back_to_fixtures(client):
    """Verify missions catalog loads strictly from committed demo_fixtures/missions.json."""
    r = client.get("/api/v1/missions")
    assert r.status_code == 200
    missions = r.json()
    assert len(missions) > 0

    ids = [m["id"] for m in missions]
    # Fixtures are prefixed with mock- or represent committed fixture IDs
    assert any(m_id.startswith("mock-") or m_id.startswith("clps-") for m_id in ids), f"Expected mock fixtures, got IDs: {ids}"


def test_offline_even_if_primary_data_dir_missing(client, monkeypatch, tmp_path):
    """Verify system remains fully operational when primary data directory is absent."""
    non_existent = tmp_path / "does_not_exist_data"
    monkeypatch.setattr(settings, "data_dir", non_existent)

    r = client.get("/api/v1/missions")
    assert r.status_code == 200
    assert r.headers["X-Data-Mode"] == "mock"
    assert len(r.json()) > 0


def test_offline_latency_under_50ms_for_missions_endpoint(client):
    """Confirm response times stay strictly under 50ms (0.050s) with no network overhead."""
    # Warm up client
    client.get("/api/v1/missions")

    durations_ms = []
    for _ in range(15):
        start = time.perf_counter()
        r = client.get("/api/v1/missions")
        duration = (time.perf_counter() - start) * 1000.0
        durations_ms.append(duration)
        assert r.status_code == 200
        assert r.headers["X-Data-Mode"] == "mock"

    max_duration = max(durations_ms)
    avg_duration = sum(durations_ms) / len(durations_ms)
    print(f"\n[LATENCY BENCHMARK] Missions: max={max_duration:.2f}ms, avg={avg_duration:.2f}ms")
    assert max_duration < 50.0, f"Max latency exceeded 50ms: {max_duration:.2f}ms"


def test_offline_latency_under_50ms_for_sites_score_endpoint(client):
    """Confirm site evaluation response times stay strictly under 50ms."""
    params = {"lat": -89.5, "lon": 0.0, "start_date": "2026-11-01", "end_date": "2027-02-15"}
    client.get("/api/v1/sites/score", params=params)

    durations_ms = []
    for _ in range(15):
        start = time.perf_counter()
        r = client.get("/api/v1/sites/score", params=params)
        duration = (time.perf_counter() - start) * 1000.0
        durations_ms.append(duration)
        assert r.status_code == 200
        assert r.headers["X-Data-Mode"] == "mock"

    max_duration = max(durations_ms)
    avg_duration = sum(durations_ms) / len(durations_ms)
    print(f"\n[LATENCY BENCHMARK] Sites Score: max={max_duration:.2f}ms, avg={avg_duration:.2f}ms")
    assert max_duration < 50.0, f"Max latency exceeded 50ms: {max_duration:.2f}ms"


def test_offline_network_calls_blocked_guard_effective():
    """Verify that any external socket connection attempts are trapped and blocked."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(NetworkBlockedError):
        sock.connect(("8.8.8.8", 53))


def test_offline_hard_gate_functional_offline(client):
    """Verify that hard-gate solar evaluation runs completely offline without network."""
    r = client.get("/api/v1/sites/score", params={"lat": -89.9, "lon": 0.0, "permanently_shadowed": True})
    assert r.status_code == 200
    data = r.json()
    assert data["scores"]["solar_viability"] == 0.0
    assert data["scores"]["total_viability_score"] == 0.0
    assert data["scores"]["hard_gate_triggered"] is True
    assert data["hard_gate_rule"]["solar_gate_passed"] is False


def test_offline_sites_geometry_structure_and_mock_mode(client):
    """Verify that GET /api/v1/sites/geometry serves valid celestial geometry in offline mode."""
    params = {"lat": -84.79, "lon": 29.20, "start_date": "2026-11-01", "end_date": "2027-02-15"}
    r = client.get("/api/v1/sites/geometry", params=params)
    assert r.status_code == 200
    assert r.headers["X-Data-Mode"] == "mock"
    data = r.json()

    # Validate exact required schema
    for key in ("earth", "sun", "psr", "illumination", "dte_comms"):
        assert key in data, f"Missing key '{key}' in geometry response"

    assert "elevation_deg" in data["earth"]
    assert "azimuth_deg" in data["earth"]
    assert "visible" in data["earth"]
    assert "unit_vector" in data["earth"]
    assert len(data["earth"]["unit_vector"]) == 3

    assert "elevation_deg" in data["sun"]
    assert "azimuth_deg" in data["sun"]
    assert "visible" in data["sun"]
    assert "unit_vector" in data["sun"]
    assert len(data["sun"]["unit_vector"]) == 3

    assert "nearest_name" in data["psr"]
    assert "distance_km" in data["psr"]
    assert data["psr"]["distance_km"] >= 0.0

    assert "tactical_pct" in data["illumination"]
    assert "solar_power_status" in data["illumination"]

    assert "status" in data["dte_comms"]
    assert "uptime_pct" in data["dte_comms"]


def test_offline_latency_under_50ms_for_sites_geometry_endpoint(client):
    """Confirm site geometry evaluation response times stay strictly under 50ms offline."""
    params = {"lat": -84.79, "lon": 29.20, "start_date": "2026-11-01", "end_date": "2027-02-15"}
    # Warm up cache
    client.get("/api/v1/sites/geometry", params=params)

    durations_ms = []
    for _ in range(15):
        start = time.perf_counter()
        r = client.get("/api/v1/sites/geometry", params=params)
        duration = (time.perf_counter() - start) * 1000.0
        durations_ms.append(duration)
        assert r.status_code == 200
        assert r.headers["X-Data-Mode"] == "mock"

    max_duration = max(durations_ms)
    avg_duration = sum(durations_ms) / len(durations_ms)
    print(f"\n[LATENCY BENCHMARK] Sites Geometry: max={max_duration:.2f}ms, avg={avg_duration:.2f}ms")
    assert max_duration < 50.0, f"Max latency exceeded 50ms: {max_duration:.2f}ms"
