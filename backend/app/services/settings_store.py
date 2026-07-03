"""Database-backed, admin-tunable application settings (key/value store).

Static configuration still lives in ``config.Settings`` (env / .env). The
runtime-tunable knobs that an admin should change without restarting the
process live here, so they can be edited from the UI via ``/api/settings``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting


def _get(db: Session, key: str, default: str) -> str:
    row = db.get(AppSetting, key)
    if row is None:
        return default
    return row.value


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)


def get_int(db: Session, key: str, default: int) -> int:
    try:
        return int(_get(db, key, str(default)))
    except (TypeError, ValueError):
        return default


def set_int(db: Session, key: str, value: int) -> None:
    _set(db, key, str(value))


def seed_defaults(db: Session) -> None:
    """Persist default values for any admin-tunable setting that doesn't exist yet."""
    defaults = {
        "instance_default_ttl_minutes": settings.instance_default_ttl_minutes,
        "instance_max_ttl_minutes": settings.instance_max_ttl_minutes,
    }
    for key, value in defaults.items():
        if db.get(AppSetting, key) is None:
            _set(db, key, str(value))
    db.commit()


def default_ttl_minutes(db: Session) -> int:
    return get_int(db, "instance_default_ttl_minutes", settings.instance_default_ttl_minutes)


def max_ttl_minutes(db: Session) -> int:
    return get_int(db, "instance_max_ttl_minutes", settings.instance_max_ttl_minutes)