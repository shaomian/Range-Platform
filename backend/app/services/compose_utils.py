"""Helpers for parsing docker-compose files (ports, services)."""
from __future__ import annotations

from pathlib import Path

import yaml


def parse_port_mapping(entry) -> tuple[int, int] | None:
    """Parse a compose 'ports' entry into (host_port, container_port).

    Handles forms like:
      - "8080:80"
      - "127.0.0.1:8080:80"
      - "8080:80/tcp"
      - {published: 8080, target: 80}
      - 8080 (single number -> host==container)
    Returns None when the host port cannot be determined statically.
    """
    if isinstance(entry, dict):
        published = entry.get("published")
        target = entry.get("target")
        if published is None or target is None:
            return None
        try:
            return int(str(published).split("-")[0]), int(str(target).split("-")[0])
        except (ValueError, TypeError):
            return None

    text = str(entry).strip()
    if "/" in text:
        text = text.split("/", 1)[0]
    parts = text.split(":")
    try:
        if len(parts) == 1:
            p = int(parts[0])
            return p, p
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        if len(parts) >= 3:
            # host_ip:host_port:container_port
            return int(parts[-2]), int(parts[-1])
    except ValueError:
        return None
    return None


def load_compose(compose_path: Path) -> dict | None:
    try:
        with compose_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None


def extract_declared_ports(compose_path: Path) -> list[dict]:
    """Return declared published ports from a compose file.

    Result items: {"service", "host_port", "container_port"}.
    """
    data = load_compose(compose_path)
    result: list[dict] = []
    if not isinstance(data, dict):
        return result
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return result
    for svc_name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        for entry in svc.get("ports", []) or []:
            mapping = parse_port_mapping(entry)
            if mapping is None:
                continue
            host_port, container_port = mapping
            result.append(
                {
                    "service": svc_name,
                    "host_port": host_port,
                    "container_port": container_port,
                }
            )
    return result
