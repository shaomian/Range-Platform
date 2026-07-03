"""Vulhub environment catalog routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..deps import get_current_user, get_current_user_or_query, require_admin
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


@router.get("/{env_path:path}/raw/{file_path:path}")
def get_env_file(
    env_path: str,
    file_path: str,
    _: User = Depends(get_current_user_or_query),
) -> FileResponse:
    """Serve a raw file (e.g. image asset) from a vulhub environment directory.

    Accepts the token via the ``Authorization`` header *or* a ``token`` query
    parameter, because ``<img>`` tags cannot set custom headers.
    """
    if catalog.get(env_path) is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    base_dir = catalog.env_dir(env_path).resolve()
    target = (base_dir / file_path).resolve()
    try:
        target.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target))


@router.get("/{env_path:path}", response_model=EnvironmentDetail)
def get_environment(
    env_path: str, _: User = Depends(get_current_user)
) -> dict:
    detail = catalog.detail(env_path)
    if detail is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return detail
