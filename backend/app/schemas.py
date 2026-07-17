"""Pydantic schemas for request/response bodies."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to timezone-aware UTC for API serialization.

    Timestamps are generated with ``datetime.now(timezone.utc)`` but SQLite's
    SQLAlchemy dialect strips the tzinfo for ``DateTime`` columns that aren't
    declared ``DateTime(timezone=True)`` (e.g. ``created_at``/``stopped_at``).
    Returning naive datetimes would serialize to offset-less ISO strings, which
    browsers (mis)interpret as local wall-clock time -- shifting the displayed
    instant by the user's UTC offset. Normalizing here guarantees every API
    response carries a ``+00:00`` suffix so the frontend ``new Date(...).toLoc-
    aleString()`` correctly converts UTC to the browser's local timezone.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---- Auth ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# ---- Users ----
class UserBase(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    role: str = "user"


class UserCreate(UserBase):
    password: str = Field(min_length=4, max_length=128)


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=4, max_length=128)
    role: str | None = None
    is_active: bool | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime | None) -> datetime | None:
        return _as_utc(value)


# ---- Environments (catalog) ----
class PortInfo(BaseModel):
    service: str
    host_port: int
    container_port: int
    url: str | None = None


class EnvironmentSummary(BaseModel):
    path: str
    name: str
    app: str
    cve: list[str] = []
    tags: list[str] = []
    images: list[str] = []


class EnvironmentDetail(EnvironmentSummary):
    readme: str | None = None
    compose: str | None = None
    declared_ports: list[PortInfo] = []


# ---- Instances ----
class InstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    env_path: str
    env_name: str
    project_name: str
    status: str
    ports: list[PortInfo] = []
    owner_id: int
    owner_username: str | None = None
    created_at: datetime
    stopped_at: datetime | None = None
    expires_at: datetime | None = None

    @field_serializer("created_at", "stopped_at", "expires_at")
    def _serialize_timestamps(self, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class InstanceCreate(BaseModel):
    env_path: str


class InstanceRenew(BaseModel):
    # Minutes to (re)set the instance's auto-stop expiry to, counting from now.
    # ``0`` / omitted means "extend by the system default TTL".
    minutes: int = Field(default=0, ge=0)


# ---- Admin settings ----
class SettingsOut(BaseModel):
    instance_default_ttl_minutes: int
    instance_max_ttl_minutes: int


class SettingsUpdate(BaseModel):
    instance_default_ttl_minutes: int | None = Field(default=None, ge=1)
    instance_max_ttl_minutes: int | None = Field(default=None, ge=1)
