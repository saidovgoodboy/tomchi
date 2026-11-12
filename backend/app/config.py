from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[1] / 'database' / 'tomchi.db'}"
    device_key: str = ""
    admin_username: str = ""
    admin_password: str = ""
    admin_token_secret: str = ""
    admin_token_ttl_seconds: int = Field(default=28800, ge=60, le=2592000)
    admin_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_hosts: str = ""
    port: int = 8000
    report_timezone_offset_minutes: int = 300
    bonus_amount: int = 20000
    bonus_per_press: int = 5000
    storage_dir: Path = Path(__file__).resolve().parents[1] / "storage"
    image_retention_days: int = 30
    image_storage_max_bytes: int = 536870912
    anpr_enabled: bool = True
    anpr_tesseract_cmd: str = "tesseract"
    anpr_min_confidence: float = Field(default=0.45, ge=0, le=1)
    anpr_timeout_seconds: int = Field(default=5, ge=1, le=15)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
