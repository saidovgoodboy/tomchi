from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[1] / 'database' / 'tomchi.db'}"
    device_key: str = "TOMCHI_DEMO_KEY"
    port: int = 8000
    bonus_amount: int = 20000
    bonus_per_press: int = 5000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
