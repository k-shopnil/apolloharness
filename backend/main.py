import logging
from contextlib import asynccontextmanager
from typing import Any, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.endpoints import missions, sites
from backend.core.config import settings

logger = logging.getLogger("backend")

KERNEL_STATUS: dict[str, Any] = {"loaded": False, "error": None}
WARMUP_STATUS: dict[str, Any] = {"completed": False, "error": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Load SPICE kernels on startup
    try:
        from src.compute.spice_engine import load_kernels
        load_kernels()
        KERNEL_STATUS["loaded"] = True
        logger.info("NASA SPICE planetary ephemeris kernels loaded successfully.")
    except Exception as exc:
        KERNEL_STATUS["loaded"] = False
        KERNEL_STATUS["error"] = str(exc)
        logger.error(f"Failed to load SPICE kernels: {exc}")

    # 2. Warm up site evaluation caches and LOLA DEM indices
    try:
        from src.compute.site_evaluation import warm_up
        warm_up()
        WARMUP_STATUS["completed"] = True
        logger.info("Site evaluation engine warmed up.")
    except Exception as exc:
        WARMUP_STATUS["completed"] = False
        WARMUP_STATUS["error"] = str(exc)
        logger.warning(f"Engine warm up failed: {exc}")

    yield

    # Teardown
    try:
        from src.compute.spice_engine import unload_kernels
        unload_kernels()
    except Exception:
        pass


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# CORS configuration
allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "Authorization"],
    expose_headers=["X-Data-Mode", "X-Cache"],
)

app.include_router(missions.router, prefix="/api/v1", tags=["missions"])
app.include_router(sites.router, prefix="/api/v1", tags=["sites"])


@app.get("/api/v1/health", tags=["health"])
@app.get("/health", tags=["health"])
def health_check():
    """Service healthcheck verifying mission catalog integrity and runtime mode."""
    primary = settings.data_dir / "missions.json"
    fallback = settings.fixtures_dir / "missions.json"
    target = primary if (not settings.offline and primary.exists()) else fallback
    mode = "live" if (not settings.offline and primary.exists()) else "offline"

    count: Optional[int] = None
    if target.exists():
        try:
            import json
            with target.open(encoding="utf-8") as f:
                data = json.load(f)
                raw_missions = data.get("missions", data) if isinstance(data, dict) else data
                count = len(raw_missions) if isinstance(raw_missions, list) else None
        except Exception:
            count = None

    is_healthy = bool(count is not None and not KERNEL_STATUS.get("error"))
    return {
        "status": "healthy" if is_healthy else "degraded",
        "app_name": settings.app_name,
        "mode": mode,
        "offline": settings.offline,
        "missions_count": count,
        "spice_kernels": KERNEL_STATUS,
        "engine_warmup": WARMUP_STATUS,
    }
