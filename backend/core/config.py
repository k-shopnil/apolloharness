from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Mission Planner API"
    offline: bool = False  # OFFLINE=1 -> True
    data_dir: Path = ROOT_DIR / "data"
    fixtures_dir: Path = (ROOT_DIR / "offline_fixtures" if (ROOT_DIR / "offline_fixtures").exists() else ROOT_DIR / "demo_fixtures")
    cors_origins: str = "https://chhayanautical.web.app,http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"


settings = Settings()
