"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")  # admin | user
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    instances: Mapped[list["Instance"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Instance(Base):
    """A running (or recorded) deployment of a vulhub environment."""

    __tablename__ = "instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # environment identifier == vulhub relative path, e.g. "geoserver/CVE-2024-36401"
    env_path: Mapped[str] = mapped_column(String(255), index=True)
    env_name: Mapped[str] = mapped_column(String(255))
    project_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    # JSON encoded list of {service, host_port, container_port, url}
    ports_json: Mapped[str] = mapped_column(Text, default="[]")
    # Rewritten docker-compose YAML actually used to start this instance
    # (declared host ports remapped to random free ports). Persisted so
    # stop/logs/status reuse the exact same compose definition.
    compose_yaml: Mapped[str] = mapped_column(Text, default="")

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="instances")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # When the instance should be auto-stopped (UTC). ``None`` disables the
    # auto-stop countdown for this instance (kept for backwards compat).
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AppSetting(Base):
    """Key/value store for admin-tunable runtime settings."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
