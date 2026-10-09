from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Mission Planner API"
    offline: bool = False  # OFFLINE=1 -> True
    data_dir: Path = ROOT_DIR / "data"
    fixtures_dir: Path = ROOT_DIR / "demo_fixtures"


settings = Settings()
