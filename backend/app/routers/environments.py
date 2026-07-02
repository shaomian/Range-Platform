"""Vulhub environment catalog routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user, require_admin
from ..models import User
from ..schemas import EnvironmentDetail, EnvironmentSummary
from ..services.catalog import catalog

router = APIRouter(prefix="/api/environments", tags=["environments"])


@router.get("/meta")
def meta(_: User = Depends(get_current_user)) -> dict:
    """Available tags and applications for filtering."""
    return {"tags": catalog.tags, "apps": catalog.apps()}


@router.post("/reload")
def reload_catalog(_: User = Depends(require_admin)) -> dict:
    """Rescan environments.toml and refresh the in-memory catalog (admin only)."""
    catalog.load()
    return {"count": len(catalog.list())}


@router.get("", response_model=list[EnvironmentSummary])
def list_environments(
    search: str | None = None,
    tag: str | None = None,
    app: str | None = None,
    _: User = Depends(get_current_user),
) -> list[dict]:
    return catalog.list(search=search, tag=tag, app=app)


@router.get("/{env_path:path}", response_model=EnvironmentDetail)
def get_environment(
    env_path: str, _: User = Depends(get_current_user)
) -> dict:
    detail = catalog.detail(env_path)
    if detail is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return detail
