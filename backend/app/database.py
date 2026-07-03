"""Database engine, session factory and declarative base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations() -> None:
    """Apply lightweight, additive schema migrations for existing databases.

    ``create_all`` never alters existing tables, so newly introduced columns
    must be added manually for databases created by older versions.
    """
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "instances" in tables:
        columns = {c["name"] for c in insp.get_columns("instances")}
        if "compose_yaml" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE instances ADD COLUMN compose_yaml TEXT DEFAULT ''")
                )
        if "expires_at" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE instances ADD COLUMN expires_at DATETIME NULL"
                    )
                )

    if "app_settings" not in tables:
        # ``create_all`` will build it from the model right after, but make the
        # migration idempotent in case create_all was already run earlier and
        # only this additive helper runs.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS app_settings ("
                    "  key VARCHAR(64) PRIMARY KEY,"
                    "  value TEXT NOT NULL DEFAULT '',"
                    "  updated_at DATETIME NOT NULL"
                    ")"
                )
            )


def init_db() -> None:
    """Create all tables. Import models so they register on the metadata."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations()
