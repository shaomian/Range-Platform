"""Interactive web terminal: exec a shell into a running instance container.

The browser opens a WebSocket to ``/api/instances/{id}/terminal``; the backend
allocates a PTY and runs ``docker exec -i -t <container> <cmd>``, bridging the
PTY to the WebSocket so the user gets a real interactive shell (xterm.js on the
frontend). Auth is via a ``token`` query param because browsers cannot set
custom headers on the WebSocket handshake.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import select
import struct
import subprocess

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Instance, User
from ..security import decode_access_token
from ..services import docker_service as ds

logger = logging.getLogger("range_platform")
router = APIRouter(prefix="/api/instances", tags=["instances"])


def _ws_auth(token: str, db: Session) -> User | None:
    """Validate a JWT passed as a query param (browsers cannot set WS headers)."""
    payload = decode_access_token(token)
    if payload is None:
        return None
    username = payload.get("sub")
    if not username:
        return None
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        return None
    return user


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    try:
        import fcntl
        import termios

        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except (OSError, ImportError):
        pass


def _set_nonblocking(fd: int) -> None:
    try:
        import fcntl

        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    except (OSError, ImportError):
        pass


def _maybe_control(text: str) -> dict | None:
    """Return a control dict if ``text`` is a JSON control message, else None."""
    if not text or text[0] != "{":
        return None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return obj if isinstance(obj, dict) and "type" in obj else None


@router.websocket("/{inst_id}/terminal")
async def terminal(ws: WebSocket, inst_id: int):
    token = ws.query_params.get("token") or ""
    cmd = ws.query_params.get("cmd") or "/bin/sh"
    try:
        cols = max(1, int(ws.query_params.get("cols") or 80))
        rows = max(1, int(ws.query_params.get("rows") or 24))
    except ValueError:
        cols, rows = 80, 24

    db = SessionLocal()
    try:
        user = _ws_auth(token, db)
        if user is None:
            await ws.close(code=4401, reason="unauthorized")
            return
        inst = db.get(Instance, inst_id)
        if inst is None:
            await ws.close(code=4404, reason="instance not found")
            return
        if user.role != "admin" and inst.owner_id != user.id:
            await ws.close(code=4403, reason="forbidden")
            return
        if inst.status != "running":
            await ws.close(code=4400, reason="instance not running")
            return
        container = ds.first_running_container(
            inst.env_path, inst.project_name, inst.compose_yaml
        )
        if not container:
            await ws.close(code=4400, reason="no running container")
            return
    finally:
        db.close()

    try:
        import pty
    except ImportError:
        await ws.close(code=4500, reason="terminal requires a Linux backend")
        return

    await ws.accept()
    master, slave = pty.openpty()
    _set_winsize(slave, rows, cols)
    _set_nonblocking(master)
    try:
        proc = subprocess.Popen(
            ["docker", "exec", "-i", "-t", container, cmd],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            start_new_session=True,
        )
    except FileNotFoundError:
        os.close(slave)
        os.close(master)
        await ws.close(code=4500, reason="docker executable not found")
        return
    except Exception as exc:
        os.close(slave)
        os.close(master)
        await ws.close(code=4500, reason=f"failed to start: {exc}")
        return
    # Parent drops the slave so EOF propagates to us when the child exits.
    os.close(slave)

    loop = asyncio.get_running_loop()
    done = asyncio.Event()
    outgoing: asyncio.Queue = asyncio.Queue()
    cleaned = False

    def _cleanup() -> None:
        nonlocal cleaned
        if cleaned:
            return
        cleaned = True
        try:
            loop.remove_reader(master)
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            os.close(master)
        except OSError:
            pass

    def on_readable() -> None:
        try:
            data = os.read(master, 65536)
        except BlockingIOError:
            return
        except OSError:
            done.set()
            return
        if not data:
            done.set()
            return
        try:
            outgoing.put_nowait(data)
        except Exception:
            done.set()

    async def sender() -> None:
        try:
            while not done.is_set():
                data = await outgoing.get()
                if data is None:
                    break
                try:
                    await ws.send_bytes(data)
                except Exception:
                    done.set()
                    break
        finally:
            done.set()

    async def writer() -> None:
        try:
            while not done.is_set():
                try:
                    msg = await ws.receive_text()
                except WebSocketDisconnect:
                    break
                ctrl = _maybe_control(msg)
                if ctrl is not None:
                    if ctrl.get("type") == "resize":
                        try:
                            _set_winsize(master, int(ctrl["rows"]), int(ctrl["cols"]))
                        except Exception:
                            pass
                    continue
                try:
                    os.write(master, msg.encode("utf-8"))
                except BlockingIOError:
                    continue
                except OSError:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            done.set()

    loop.add_reader(master, on_readable)
    t_send = asyncio.create_task(sender())
    t_write = asyncio.create_task(writer())
    try:
        await done.wait()
    finally:
        done.set()
        for t in (t_send, t_write):
            t.cancel()
        await asyncio.gather(t_send, t_write, return_exceptions=True)
        _cleanup()
        try:
            await ws.close()
        except Exception:
            pass
