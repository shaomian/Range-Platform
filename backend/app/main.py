"""FastAPI application entrypoint for the vulhub range platform."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import SessionLocal, init_db
from .models import User
from .routers import auth, environments, instances, users
from .security import hash_password
from .services.catalog import catalog

logger = logging.getLogger("range_platform")


def _ensure_admin() -> None:
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == settings.admin_username).first()
        if exists is None:
            db.add(
                User(
                    username=settings.admin_username,
                    hashed_password=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            db.commit()
            logger.info("Created initial admin user '%s'", settings.admin_username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _ensure_admin()
    catalog.load()
    logger.info(
        "Loaded %d vulhub environments from %s",
        len(catalog.list()),
        settings.vulhub_path,
    )
    yield


app = FastAPI(title="Vulhub Range Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(environments.router)
app.include_router(instances.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environments": len(catalog.list())}


def _mount_frontend() -> None:
    """Serve the compiled frontend (SPA) when a build is present.

    Static assets are served from /assets; any other non-API path falls back to
    index.html so Vue Router's history mode works on hard refresh / deep links.
    """
    static_dir = settings.static_path
    if not static_dir.is_dir():
        logger.info("Frontend build not found at %s; serving API only", static_dir)
        return

    index_file = static_dir / "index.html"
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = static_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(index_file))

    logger.info("Serving frontend from %s", static_dir)


_mount_frontend()
