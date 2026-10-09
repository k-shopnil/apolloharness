"""Automated offline dry-run verification script.

Verifies:
1. OFFLINE=1 enforcement and socket guard blocking external networks.
2. Complete fallback to committed demo_fixtures/missions.json.
3. Sub-50ms latency across all endpoints with zero network dependencies.
4. Hard-gate solar power calculations offline.
"""
import os
import socket
import sys
import time
from pathlib import Path

# Enforce OFFLINE environment before loading settings
os.environ["OFFLINE"] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.config import settings
settings.offline = True

from fastapi.testclient import TestClient
from backend.main import app


class NetworkBlockedError(RuntimeError):
    pass


def install_network_guard():
    orig_connect = socket.socket.connect

    def guarded_connect(self, *args, **kwargs):
        target = args[0] if args else kwargs.get("address")
        host = target[0] if isinstance(target, tuple) and len(target) > 0 else target
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, *args, **kwargs)
        raise NetworkBlockedError(f"External network call blocked by offline guard! Target: {target}")

    socket.socket.connect = guarded_connect


def run_benchmark(name: str, fn, iterations: int = 10, max_latency_ms: float = 50.0) -> bool:
    # Warmup
    fn()

    durations = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = fn()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        durations.append(elapsed_ms)

    avg_ms = sum(durations) / len(durations)
    p95_ms = sorted(durations)[int(len(durations) * 0.95)]
    peak_ms = max(durations)

    status = "PASS" if peak_ms < max_latency_ms else "FAIL"
    print(
        f"  [{status}] {name:<35} | avg: {avg_ms:5.2f}ms | p95: {p95_ms:5.2f}ms | peak: {peak_ms:5.2f}ms (<{max_latency_ms}ms)"
    )
    return peak_ms < max_latency_ms


def main() -> int:
    print("=" * 78)
    print("  NASA MISSION PLANNER - OFFLINE RESILIENCE DRY-RUN VERIFIER")
    print("=" * 78)

    install_network_guard()
    client = TestClient(app)

    all_passed = True

    # 1. Verify Network Guard
    print("\n[1/5] Verifying Outbound Network Blocker...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("93.184.216.34", 80))
        print("  [FAIL] External connection was unexpectedly permitted!")
        all_passed = False
    except NetworkBlockedError:
        print("  [PASS] External network socket blocked cleanly.")

    # 2. Verify Health Check Endpoint
    print("\n[2/5] Testing /api/v1/health (Offline Catalog Check)...")
    r_health = client.get("/api/v1/health")
    if r_health.status_code == 200 and r_health.json().get("mode") == "mock":
        print(f"  [PASS] System reports healthy in mock mode: {r_health.json()}")
    else:
        print(f"  [FAIL] Unexpected health status: {r_health.status_code} - {r_health.text}")
        all_passed = False

    # 3. Verify Missions Fixture Fallback
    print("\n[3/5] Testing /api/v1/missions Fixtures Fallback...")
    r_missions = client.get("/api/v1/missions")
    if r_missions.status_code == 200:
        missions = r_missions.json()
        mode = r_missions.headers.get("X-Data-Mode")
        has_fixtures = any(m["id"].startswith("mock-") for m in missions)
        if mode == "mock" and has_fixtures:
            print(f"  [PASS] Loaded {len(missions)} missions from demo_fixtures with X-Data-Mode: mock")
        else:
            print(f"  [FAIL] Expected mock fixture data, got mode={mode}, missions={missions}")
            all_passed = False
    else:
        print(f"  [FAIL] Missions endpoint returned HTTP {r_missions.status_code}")
        all_passed = False

    # 4. Verify Scientific Site Evaluation & Hard-Gate Rule
    print("\n[4/5] Testing /api/v1/sites/score & Solar Hard-Gate Rule...")
    # Test Hard-Gate PSR floor
    r_psr = client.get("/api/v1/sites/score", params={"lat": -89.9, "lon": 0.0, "permanently_shadowed": True})
    data_psr = r_psr.json()
    if (
        r_psr.status_code == 200
        and data_psr["scores"]["solar_viability"] == 0.0
        and data_psr["scores"]["total_viability_score"] == 0.0
        and data_psr["hard_gate_rule"]["triggered"] is True
    ):
        print("  [PASS] Permanent shadow crater floor strictly triggered 0 total viability hard gate.")
    else:
        print(f"  [FAIL] Hard-gate rule failed: {data_psr}")
        all_passed = False

    # Test Polar Rim
    r_polar = client.get("/api/v1/sites/score", params={"lat": -89.5, "lon": 0.0, "start_date": "2026-11-01"})
    data_polar = r_polar.json()
    if r_polar.status_code == 200 and data_polar["tactical_mission_sunlight"]["percentage"] > 70:
        print(f"  [PASS] Polar Shackleton Rim tactical sunlight: {data_polar['tactical_mission_sunlight']['percentage']}%")
    else:
        print(f"  [FAIL] Polar calculation unexpected: {data_polar}")
        all_passed = False

    # 5. Latency Benchmarks (< 50ms)
    print("\n[5/5] Benchmarking Endpoint Response Times (<50ms requirement)...")
    b1 = run_benchmark("GET /api/v1/health", lambda: client.get("/api/v1/health"))
    b2 = run_benchmark("GET /api/v1/missions", lambda: client.get("/api/v1/missions"))
    b3 = run_benchmark(
        "GET /api/v1/sites/score (Polar)",
        lambda: client.get("/api/v1/sites/score", params={"lat": -89.5, "lon": 0.0}),
    )
    b4 = run_benchmark(
        "GET /api/v1/sites/score (Equatorial)",
        lambda: client.get("/api/v1/sites/score", params={"lat": 18.56, "lon": 61.81}),
    )
    b5 = run_benchmark(
        "GET /api/v1/sites/score (PSR Gate)",
        lambda: client.get("/api/v1/sites/score", params={"lat": -89.9, "lon": 0.0, "permanently_shadowed": True}),
    )

    all_passed = all_passed and all([b1, b2, b3, b4, b5])

    print("\n" + "=" * 78)
    if all_passed:
        print("  >>> ALL OFFLINE RESILIENCE ASSERTIONS PASSED SUCCESSFULLY <<<")
        print("=" * 78)
        return 0
    else:
        print("  >>> OFFLINE DRY-RUN VERIFICATION FAILED <<<")
        print("=" * 78)
        return 1


if __name__ == "__main__":
    sys.exit(main())
