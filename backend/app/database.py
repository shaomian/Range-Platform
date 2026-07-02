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
    if "instances" not in insp.get_table_names():
        return
    columns = {c["name"] for c in insp.get_columns("instances")}
    if "compose_yaml" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE instances ADD COLUMN compose_yaml TEXT DEFAULT ''")
            )


def init_db() -> None:
    """Create all tables. Import models so they register on the metadata."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations()
