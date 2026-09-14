# backend/app/config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the repo root no matter where alembic/uvicorn is run from.
# backend/app/config.py -> backend/ -> repo root
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    # --- existing ---
    cors_origins: str = "http://localhost:3000"
    jwt_secret: str = "dev-secret"
    database_url: str = "postgresql+psycopg://jobboard:jobboard@localhost:5432/jobboard"

    # --- LLM ---
    google_api_key: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()