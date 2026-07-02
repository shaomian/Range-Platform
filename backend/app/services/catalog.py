"""Vulhub environment catalog: parse environments.toml and env directories."""
from __future__ import annotations

import tomllib
from pathlib import Path

from ..config import settings
from .compose_utils import extract_declared_ports


class Catalog:
    def __init__(self, root: Path):
        self.root = root
        self._envs: dict[str, dict] = {}
        self._tags: list[str] = []
        self._loaded = False

    def load(self) -> None:
        toml_path = self.root / "environments.toml"
        if not toml_path.exists():
            self._envs = {}
            self._tags = []
            self._loaded = True
            return
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        self._tags = sorted(set(data.get("tags", [])))
        envs: dict[str, dict] = {}
        for env in data.get("environment", []):
            path = env.get("path")
            if not path:
                continue
            dockerfile = env.get("dockerfile", {}) or {}
            envs[path] = {
                "path": path,
                "name": env.get("name", path),
                "app": env.get("app", ""),
                "cve": list(env.get("cve", []) or []),
                "tags": list(env.get("tags", []) or []),
                "images": list(dockerfile.keys()),
            }
        self._envs = envs
        self._loaded = True

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @property
    def tags(self) -> list[str]:
        self.ensure_loaded()
        return self._tags

    def list(
        self,
        search: str | None = None,
        tag: str | None = None,
        app: str | None = None,
    ) -> list[dict]:
        self.ensure_loaded()
        items = list(self._envs.values())
        if tag:
            items = [e for e in items if tag in e["tags"]]
        if app:
            items = [e for e in items if e["app"] == app]
        if search:
            s = search.lower()
            items = [
                e
                for e in items
                if s in e["name"].lower()
                or s in e["app"].lower()
                or s in e["path"].lower()
                or any(s in c.lower() for c in e["cve"])
            ]
        return sorted(items, key=lambda e: e["name"].lower())

    def apps(self) -> list[str]:
        self.ensure_loaded()
        return sorted({e["app"] for e in self._envs.values() if e["app"]})

    def get(self, path: str) -> dict | None:
        self.ensure_loaded()
        return self._envs.get(path)

    def env_dir(self, path: str) -> Path:
        return self.root / path

    def compose_file(self, path: str) -> Path | None:
        env_dir = self.env_dir(path)
        for name in ("docker-compose.yml", "docker-compose.yaml"):
            candidate = env_dir / name
            if candidate.exists():
                return candidate
        return None

    def detail(self, path: str) -> dict | None:
        env = self.get(path)
        if env is None:
            return None
        env_dir = self.env_dir(path)
        detail = dict(env)
        detail["readme"] = self._read_readme(env_dir)
        compose_file = self.compose_file(path)
        detail["compose"] = (
            compose_file.read_text(encoding="utf-8", errors="replace")
            if compose_file
            else None
        )
        detail["declared_ports"] = (
            extract_declared_ports(compose_file) if compose_file else []
        )
        return detail

    @staticmethod
    def _read_readme(env_dir: Path) -> str | None:
        for name in ("README.zh-cn.md", "README.md"):
            f = env_dir / name
            if f.exists():
                return f.read_text(encoding="utf-8", errors="replace")
        return None


catalog = Catalog(settings.vulhub_path)
