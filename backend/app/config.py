"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Security
    secret_key: str = "change-me-to-a-random-secret-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    # Database
    database_url: str = "sqlite:///./vulhub_hub.db"

    # Vulhub catalog
    vulhub_root: str = "../../vulhub"

    # Compiled frontend directory served by FastAPI (single-container deployment)
    static_dir: str = "../frontend/dist"

    # Networking
    server_host: str = "localhost"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Initial admin
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # Resource limits
    max_instances_per_user: int = 3

    # Default instance TTL (auto-stop timeout) in minutes, applied when a new
    # instance is started. Admin-tunable via the /api/settings endpoint.
    instance_default_ttl_minutes: int = 60
    # Maximum TTL (minutes) a regular user may request when renewing an
    # instance. Admin-tunable; admins bypass the cap.
    instance_max_ttl_minutes: int = 1440

    # Per-instance host port allocation range (inclusive). Each started
    # environment gets its declared host ports remapped to random free ports
    # within this range so multiple instances never collide.
    port_range_start: int = 10000
    port_range_end: int = 12000

    @property
    def vulhub_path(self) -> Path:
        p = Path(self.vulhub_root)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        return p

    @property
    def static_path(self) -> Path:
        p = Path(self.static_dir)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
