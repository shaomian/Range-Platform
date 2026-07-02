#!/usr/bin/env bash
# Management helper for the Vulhub Range Platform (Linux / macOS).
# Wraps `docker compose` for the platform container defined in docker-compose.yml.
# Windows users: use manage.ps1 (PowerShell) instead.
#
# Usage (from the range-platform directory):
#   ./manage.sh <command>
#
# Commands:
#   start     Start the platform (creates the container if missing; idempotent).
#   stop      Stop the platform container (keeps it; data volume preserved).
#   restart   Restart the platform container.
#   pull      Update the vulhub catalog (git pull) then restart to reload it.
#   status    Show container status (docker compose ps).
#   logs      Follow the platform logs (Ctrl-C to exit).
#   rebuild   Rebuild the image and restart (after backend/frontend changes).
#   down      Remove the platform container (data volume preserved).
#   destroy   Remove the container AND the range-data volume (DELETES the database!).
#
# NOTE: These commands only affect the *platform* container. Running vulhub
# targets are separate compose projects and are unaffected by stop/restart.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Linux needs sudo to reach the docker daemon; macOS Docker Desktop must not.
SUDO=""
if [ "$(uname -s)" = "Linux" ] && [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

command -v docker >/dev/null 2>&1 || die "docker not found. Run ./deploy.sh first."
docker compose version >/dev/null 2>&1 || die "docker compose v2 unavailable."

dc() { $SUDO docker compose "$@"; }

usage() {
  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

cmd="${1:-}"
case "$cmd" in
  start)
    log "Starting the platform (docker compose up -d)"
    dc up -d
    dc ps
    ;;
  stop)
    log "Stopping the platform container (docker compose stop)"
    dc stop
    ;;
  restart)
    log "Restarting the platform container (docker compose restart)"
    dc restart
    dc ps
    ;;
  pull)
    # Resolve the vulhub git working directory: prefer VULHUB_HOST_PATH from
    # .env (if a compose env file exists), else the default sibling ../vulhub.
    vulhub_dir=""
    if [ -f "$SCRIPT_DIR/.env" ]; then
      vulhub_dir="$(grep -m1 '^VULHUB_HOST_PATH=' "$SCRIPT_DIR/.env" | cut -d= -f2- || true)"
    fi
    [ -n "$vulhub_dir" ] || vulhub_dir="$SCRIPT_DIR/../vulhub"
    command -v git >/dev/null 2>&1 || die "git not found in PATH."
    [ -d "$vulhub_dir" ] || die "vulhub directory not found at $vulhub_dir"
    [ -d "$vulhub_dir/.git" ] || die "$vulhub_dir is not a git repository (clone vulhub with 'git clone' first)."
    warn "This will run 'git pull' in $vulhub_dir and then restart the platform."
    printf 'Proceed? [y/N]: '
    read -r reply
    case "$reply" in
      y|Y|yes|YES) ;;
      *) log "Aborted."; exit 0 ;;
    esac
    log "Updating vulhub catalog (git pull)"
    ( cd "$vulhub_dir" && git pull ) || die "git pull failed."
    log "Restarting the platform to reload the catalog (docker compose restart)"
    dc restart
    dc ps
    ;;
  status|ps)
    dc ps
    ;;
  logs)
    log "Following platform logs (Ctrl-C to exit)"
    dc logs -f --tail=200
    ;;
  rebuild|update)
    log "Rebuilding image and restarting (docker compose up -d --build)"
    dc up -d --build
    dc ps
    ;;
  down)
    log "Removing the platform container (data volume kept)"
    dc down
    ;;
  destroy)
    warn "This removes the container AND the range-data volume (SQLite database,"
    warn "user accounts and instance records will be permanently deleted)."
    printf 'Type EXACTLY "yes" to continue: '
    read -r reply
    [ "$reply" = "yes" ] || die "Aborted."
    log "Removing container and range-data volume (docker compose down -v)"
    dc down -v
    ;;
  ""|-h|--help|help)
    usage 0
    ;;
  *)
    warn "Unknown command: $cmd"
    usage 1
    ;;
esac
