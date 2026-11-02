from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://queuepilot:queuepilot@localhost:5432/queuepilot"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "queuepilot-local-dev"
    jwt_ttl_minutes: int = 720
    dispatch_stream: str = "queuepilot:dispatch"
    worker_group: str = "queuepilot-workers"
    scheduler_interval_seconds: float = 0.5
    heartbeat_timeout_seconds: int = 15
    lease_seconds: int = 30

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
