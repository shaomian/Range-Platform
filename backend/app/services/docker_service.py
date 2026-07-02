"""Wrap docker compose CLI calls for starting/stopping vulhub environments."""
from __future__ import annotations

import json
import os
import random
import re
import secrets
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..config import settings
from .catalog import catalog
from .compose_utils import load_compose, parse_port_mapping


class DockerError(Exception):
    pass


class _QuotedStr(str):
    """A string always emitted double-quoted in YAML (e.g. port mappings)."""


def _represent_quoted(dumper: yaml.Dumper, data: _QuotedStr):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style='"')


yaml.SafeDumper.add_representer(_QuotedStr, _represent_quoted)


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def project_name_for(env_path: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", env_path.lower()).strip("_")
    return f"vulhub_{slug}"


def unique_project_name(env_path: str) -> str:
    """A per-instance compose project name so instances never collide."""
    return f"{project_name_for(env_path)}_{secrets.token_hex(4)}"


def _host_published_ports() -> set[int]:
    """Host ports currently published by ANY running container (host-daemon view).

    The platform container drives the host docker daemon through the mounted
    socket, so this sees ports opened by every container on the host -- including
    ones started manually outside the platform. An in-container ``socket.bind``
    probe cannot see those (different network namespace), which is exactly the
    blind spot that previously caused "port already allocated" failures.
    """
    try:
        res = _run(["docker", "ps", "--format", "{{.Ports}}"], timeout=30)
    except DockerError:
        return set()
    if not res.ok:
        return set()
    occupied: set[int] = set()
    for line in (res.stdout or "").splitlines():
        for m in re.finditer(r":(\d+)->", line):
            try:
                occupied.add(int(m.group(1)))
            except ValueError:
                continue
    return occupied


def allocate_host_port(reserved: set[int]) -> int:
    """Pick a random free host port within the configured range.

    ``reserved`` accumulates ports handed out during the current allocation so
    the same port is never assigned twice within one instance. We also query the
    host docker daemon for every port already published by a running container;
    that catches containers started manually outside the platform that the DB
    ``reserved`` set (which only tracks platform-managed instances) would miss.
    """
    start, end = settings.port_range_start, settings.port_range_end
    if start > end:
        start, end = end, start
    host_taken = _host_published_ports()
    candidates = list(range(start, end + 1))
    random.shuffle(candidates)
    for port in candidates:
        if port in reserved or port in host_taken:
            continue
        reserved.add(port)
        return port
    raise DockerError(
        f"no free host port available in range {start}-{end}"
    )


def build_instance_compose(
    env_path: str, reserved: set[int] | None = None
) -> tuple[str, list[dict]]:
    """Return (compose_yaml, port_map) for a fresh, isolated instance.

    Each declared host port is remapped to a random free port in the
    configured range, and any explicit ``container_name`` is stripped so
    multiple instances of the same environment can run concurrently.
    """
    if reserved is None:
        reserved = set()
    compose_file = catalog.compose_file(env_path)
    if compose_file is None:
        raise DockerError(f"docker-compose file not found for {env_path}")
    data = load_compose(compose_file)
    if not isinstance(data, dict):
        raise DockerError(f"invalid docker-compose file for {env_path}")

    # A top-level project name would otherwise fight our unique -p value.
    data.pop("name", None)

    services = data.get("services") or {}
    port_map: list[dict] = []
    if isinstance(services, dict):
        for svc_name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            svc.pop("container_name", None)
            new_ports = []
            for entry in svc.get("ports", []) or []:
                mapping = parse_port_mapping(entry)
                if mapping is None:
                    new_ports.append(entry)
                    continue
                _old_host, container_port = mapping
                host_port = allocate_host_port(reserved)
                new_ports.append(_QuotedStr(f"{host_port}:{container_port}"))
                port_map.append(
                    {
                        "service": svc_name,
                        "host_port": host_port,
                        "container_port": container_port,
                    }
                )
            if new_ports:
                svc["ports"] = new_ports

    yaml_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return yaml_text, port_map


def _run(args: list[str], cwd: Path | None = None, timeout: int = 900) -> CommandResult:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:  # docker not installed
        raise DockerError("docker executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise DockerError(f"command timed out: {' '.join(args)}") from exc
    return CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "")


def _compose(
    env_path: str,
    project: str,
    compose_yaml: str,
    *extra: str,
    timeout: int = 900,
) -> CommandResult:
    """Run a compose subcommand for a specific instance.

    When ``compose_yaml`` is provided it is written to a temporary file and
    passed via ``-f`` (with ``--project-directory`` anchored at the environment
    directory so relative build contexts / bind mounts still resolve). When it
    is empty (legacy instances) the command falls back to operating on the
    project purely by name/labels.
    """
    env_dir = catalog.env_dir(env_path)
    if not compose_yaml:
        args = ["docker", "compose", "-p", project, *extra]
        cwd = env_dir if env_dir.exists() else None
        return _run(args, cwd=cwd, timeout=timeout)

    if not env_dir.exists():
        raise DockerError(f"environment directory not found: {env_path}")
    tmp = tempfile.NamedTemporaryFile(
        "w", suffix=".yml", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(compose_yaml)
        tmp.close()
        args = [
            "docker",
            "compose",
            "--project-directory",
            str(env_dir),
            "-f",
            tmp.name,
            "-p",
            project,
            *extra,
        ]
        return _run(args, cwd=env_dir, timeout=timeout)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def compose_up(env_path: str, project: str, compose_yaml: str) -> CommandResult:
    res = _compose(env_path, project, compose_yaml, "up", "-d", timeout=1200)
    if not res.ok:
        raise DockerError(res.stderr.strip() or res.stdout.strip() or "compose up failed")
    return res


def compose_down(env_path: str, project: str, compose_yaml: str) -> CommandResult:
    return _compose(env_path, project, compose_yaml, "down", "-v", timeout=300)


def compose_logs(
    env_path: str, project: str, compose_yaml: str, tail: int = 500
) -> str:
    res = _compose(
        env_path, project, compose_yaml, "logs", "--no-color", "--tail", str(tail),
        timeout=60,
    )
    return (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")


def _parse_ps_json(raw: str) -> list[dict]:
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        pass
    items: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def compose_ps(env_path: str, project: str, compose_yaml: str) -> list[dict]:
    res = _compose(
        env_path, project, compose_yaml, "ps", "--format", "json", "--all",
        timeout=60,
    )
    if not res.ok:
        return []
    return _parse_ps_json(res.stdout)


def runtime_ports(env_path: str, project: str, compose_yaml: str) -> list[dict]:
    """Return published ports of running containers as PortInfo-like dicts."""
    ports: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for container in compose_ps(env_path, project, compose_yaml):
        service = container.get("Service") or container.get("Name") or ""
        for pub in container.get("Publishers") or []:
            published = pub.get("PublishedPort") or 0
            target = pub.get("TargetPort") or 0
            if not published:
                continue
            key = (service, int(published))
            if key in seen:
                continue
            seen.add(key)
            ports.append(
                {
                    "service": service,
                    "host_port": int(published),
                    "container_port": int(target),
                    "url": f"http://{settings.server_host}:{int(published)}",
                }
            )
    return sorted(ports, key=lambda p: p["host_port"])


def is_running(env_path: str, project: str, compose_yaml: str) -> bool:
    for container in compose_ps(env_path, project, compose_yaml):
        state = (container.get("State") or "").lower()
        if state == "running":
            return True
    return False


def docker_available() -> bool:
    """True if the host docker daemon responds (mounted socket is wired up)."""
    try:
        res = _run(["docker", "ps", "--format", "{{.ID}}"], timeout=15)
    except DockerError:
        return False
    return res.ok
