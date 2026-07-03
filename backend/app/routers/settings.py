"""Admin-tunable runtime settings (instance TTL configuration, etc.)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..deps import get_current_user, require_admin
from ..models import User
from ..schemas import SettingsOut, SettingsUpdate
from ..services import settings_store as store

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _snapshot(db: Session) -> SettingsOut:
    return SettingsOut(
        instance_default_ttl_minutes=store.default_ttl_minutes(db),
        instance_max_ttl_minutes=store.max_ttl_minutes(db),
    )


@router.get("", response_model=SettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> SettingsOut:
    # Any logged-in user may read the TTL configuration: regular users need to
    # know the default / max when choosing a renew duration.
    return _snapshot(db)


@router.put("", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> SettingsOut:
    if payload.instance_default_ttl_minutes is not None:
        store.set_int(db, "instance_default_ttl_minutes", payload.instance_default_ttl_minutes)
    if payload.instance_max_ttl_minutes is not None:
        store.set_int(db, "instance_max_ttl_minutes", payload.instance_max_ttl_minutes)
    db.commit()
    return _snapshot(db)


def seed_settings() -> None:
    """Persist default setting rows on startup idempotently."""
    db = SessionLocal()
    try:
        store.seed_defaults(db)
    finally:
        db.close()