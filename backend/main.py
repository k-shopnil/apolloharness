from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.endpoints import missions, sites
from backend.core.config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")

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
    missions_list, mode = missions.load_missions()
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "mode": mode,
        "offline": settings.offline,
        "missions_count": len(missions_list),
    }
