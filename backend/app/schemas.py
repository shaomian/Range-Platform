"""Pydantic schemas for request/response bodies."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class InstanceCreate(BaseModel):
    env_path: str
