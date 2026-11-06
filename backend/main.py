from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.endpoints import missions, sites
from backend.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from src.compute.spice_engine import load_kernels
        load_kernels()
    except Exception:
        pass
    yield
    try:
        from src.compute.spice_engine import unload_kernels
        unload_kernels()
    except Exception:
        pass

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# CORS is configurable through CORS_ORIGINS (comma-separated origins). Keep the
# production frontend and common local development ports available by default.
# CORS is configurable through CORS_ORIGINS (comma-separated origins). Keep the
# production frontend and common local development ports available by default.
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
    mode = "live" if target == primary else "mock"
    count = 16
    if target.exists():
        try:
            import json
            with target.open(encoding="utf-8") as f:
                data = json.load(f)
                count = len(data.get("missions", data) if isinstance(data, dict) else data)
        except Exception:
            pass
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "mode": mode,
        "offline": settings.offline,
        "missions_count": count,
    }
