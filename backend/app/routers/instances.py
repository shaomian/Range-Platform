"""Instance lifecycle routes: start/stop/logs/status."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..deps import get_current_user
from ..models import Instance, User
from ..schemas import InstanceCreate, InstanceOut, PortInfo
from ..services import docker_service as ds
from ..services.catalog import catalog

router = APIRouter(prefix="/api/instances", tags=["instances"])

logger = logging.getLogger("range_platform")


def _to_out(inst: Instance) -> InstanceOut:
    try:
        ports = [PortInfo(**p) for p in json.loads(inst.ports_json or "[]")]
    except (json.JSONDecodeError, TypeError):
        ports = []
    return InstanceOut(
        id=inst.id,
        env_path=inst.env_path,
        env_name=inst.env_name,
        project_name=inst.project_name,
        status=inst.status,
        ports=ports,
        owner_id=inst.owner_id,
        owner_username=inst.owner.username if inst.owner else None,
        created_at=inst.created_at,
        stopped_at=inst.stopped_at,
    )


@router.get("", response_model=list[InstanceOut])
def list_instances(
    all_users: bool = Query(False, alias="all"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[InstanceOut]:
    query = db.query(Instance)
    if not (all_users and current.role == "admin"):
        query = query.filter(Instance.owner_id == current.id)
    instances = query.order_by(Instance.created_at.desc()).all()
    return [_to_out(i) for i in instances]


@router.post("", response_model=InstanceOut, status_code=201)
def start_instance(
    payload: InstanceCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> InstanceOut:
    env = catalog.get(payload.env_path)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")

    if current.role != "admin":
        active = (
            db.query(Instance)
            .filter(Instance.owner_id == current.id, Instance.status == "running")
            .count()
        )
        if active >= settings.max_instances_per_user:
            raise HTTPException(
                status_code=403,
                detail=f"Instance limit reached ({settings.max_instances_per_user})",
            )

    # A unique project name plus remapped host ports lets multiple users (and
    # repeated runs) start the same environment concurrently, each fully
    # isolated with fresh containers and volumes.
    project = ds.unique_project_name(payload.env_path)
    reserved = _ports_in_use(db)
    try:
        compose_yaml, port_map = ds.build_instance_compose(payload.env_path, reserved)
        ds.compose_up(payload.env_path, project, compose_yaml)
    except ds.DockerError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start: {exc}") from exc

    ports = ds.runtime_ports(payload.env_path, project, compose_yaml)
    if not ports:
        # Fall back to the ports we allocated if `ps` hasn't reported yet.
        ports = [
            {**p, "url": f"http://{settings.server_host}:{p['host_port']}"}
            for p in port_map
        ]
    inst = Instance(
        project_name=project,
        env_path=payload.env_path,
        env_name=env["name"],
        status="running",
        ports_json=json.dumps(ports),
        compose_yaml=compose_yaml,
        owner_id=current.id,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return _to_out(inst)


def _ports_in_use(db: Session) -> set[int]:
    """Host ports already assigned to running instances (best-effort)."""
    used: set[int] = set()
    running = db.query(Instance).filter(Instance.status == "running").all()
    for inst in running:
        try:
            for p in json.loads(inst.ports_json or "[]"):
                port = p.get("host_port")
                if isinstance(port, int):
                    used.add(port)
        except (json.JSONDecodeError, TypeError):
            continue
    return used


def _get_owned(db: Session, inst_id: int, current: User) -> Instance:
    inst = db.get(Instance, inst_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    if current.role != "admin" and inst.owner_id != current.id:
        raise HTTPException(status_code=403, detail="Not permitted")
    return inst


@router.post("/{inst_id}/stop", response_model=InstanceOut)
def stop_instance(
    inst_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> InstanceOut:
    inst = _get_owned(db, inst_id, current)
    try:
        ds.compose_down(inst.env_path, inst.project_name, inst.compose_yaml)
    except ds.DockerError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to stop: {exc}") from exc
    inst.status = "stopped"
    inst.stopped_at = datetime.now(timezone.utc)
    inst.ports_json = "[]"
    db.commit()
    db.refresh(inst)
    return _to_out(inst)


@router.get("/{inst_id}/logs")
def instance_logs(
    inst_id: int,
    tail: int = 500,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> dict:
    inst = _get_owned(db, inst_id, current)
    return {
        "logs": ds.compose_logs(
            inst.env_path, inst.project_name, inst.compose_yaml, tail=tail
        )
    }


@router.get("/{inst_id}/status", response_model=InstanceOut)
def refresh_status(
    inst_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> InstanceOut:
    inst = _get_owned(db, inst_id, current)
    if ds.is_running(inst.env_path, inst.project_name, inst.compose_yaml):
        inst.status = "running"
        inst.ports_json = json.dumps(
            ds.runtime_ports(inst.env_path, inst.project_name, inst.compose_yaml)
        )
    else:
        inst.status = "stopped"
        inst.ports_json = "[]"
        if inst.stopped_at is None:
            inst.stopped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inst)
    return _to_out(inst)


@router.delete("/{inst_id}", status_code=204, response_class=Response)
def delete_instance(
    inst_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> Response:
    inst = _get_owned(db, inst_id, current)
    if inst.status == "running":
        try:
            ds.compose_down(inst.env_path, inst.project_name, inst.compose_yaml)
        except ds.DockerError:
            pass
    db.delete(inst)
    db.commit()
    return Response(status_code=204)


def reconcile_on_startup() -> None:
    """Resync DB "running" instances with the live docker daemon.

    Platform-started containers carry no restart policy, so a host reboot
    kills them while the DB keeps showing "running" -- the "我的实例" page then
    lists dead instances as running. Called once at startup; verifies each
    "running" instance with ``docker compose ps`` and flips dead ones to
    "stopped" (clearing ports, setting stopped_at). Skipped when the docker
    daemon isn't reachable yet, so we never mark stopped just because we
    couldn't query docker.
    """
    if not ds.docker_available():
        logger.warning(
            "docker daemon not reachable at startup; skipping instance reconciliation"
        )
        return
    db = SessionLocal()
    try:
        flipped = 0
        for inst in db.query(Instance).filter(Instance.status == "running").all():
            try:
                alive = ds.is_running(
                    inst.env_path, inst.project_name, inst.compose_yaml
                )
            except ds.DockerError:
                continue
            if alive:
                continue
            inst.status = "stopped"
            inst.ports_json = "[]"
            if inst.stopped_at is None:
                inst.stopped_at = datetime.now(timezone.utc)
            flipped += 1
        if flipped:
            db.commit()
            logger.info(
                "Reconciled %d stale running instance(s) to stopped on startup",
                flipped,
            )
    finally:
        db.close()
