# Vulhub Range Platform

<p align="center">
  <img src=".github/assets/banner.png" alt="Vulhub Range Platform" height="auto" />
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/shaomian/Range-Platform?style=social)](https://github.com/shaomian/Range-Platform/stargazers)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

**语言 / Language**: **English** | [中文](README.zh-cn.md)

A web-based platform for managing vulnerability ranges — browse, start, stop, and monitor local [vulhub](https://github.com/vulhub/vulhub) environments.

- **Backend**: FastAPI + SQLAlchemy (SQLite) + JWT auth, driving containers via `docker compose`.
- **Frontend**: Vue 3 + Vite + Element Plus + Pinia.
- **Features**: multi-user auth, catalog search (name / CVE / app / tags), README & compose preview, one-click start/stop, live ports & access URLs, container logs, user management, per-user concurrent-instance limits, **instance auto-stop with a live countdown + manual renewal + admin-tunable TTL settings**.
- **Deployment**: single-container Docker (`docker compose up -d --build`), plus one-click scripts for **Linux / macOS (`deploy.sh`) and Windows (`deploy.ps1`)** — see [Docker deployment (single container)](#docker-deployment-single-container) and [One-click deployment](#one-click-deployment-linux--macos--windows).

## Quick Start

Prerequisites: **Docker** and **docker compose** installed on the target host (if missing, the `deploy` scripts will try to install them automatically).

```bash
# 1. Clone this repository
git clone https://github.com/shaomian/Range-Platform.git
cd Range-Platform

# 2. One-click deploy (auto: install Docker if missing, clone vulhub,
#    generate random secret & admin password, build and start)
#    Linux:   sudo ./deploy.sh
#    macOS:   ./deploy.sh
#    Windows: powershell -ExecutionPolicy Bypass -File .\deploy.ps1

# 3. Open http://<host-ip>:8000 in a browser
#    Log in with the admin username / password printed once at the end of the
#    script (also available in .env)
```

Day-to-day operations (affect the platform container only):

```bash
./manage.sh restart     # restart the platform (Windows: .\manage.ps1 restart)
./manage.sh pull        # git pull the vulhub catalog, then restart
./manage.sh logs        # follow logs
```

> For manual, step-by-step deployment or cross-platform details, read on.

## Project structure

```
range-platform/
├── backend/            # FastAPI backend
│   ├── app/            # application code (routers/services/models...)
│   ├── requirements.txt
│   └── .env.example    # config template
└── frontend/           # Vue 3 frontend
```

## Requirements

- Python 3.10+
- Node.js 18+
- Docker Desktop (with `docker compose` enabled)
- A sibling `vulhub/` directory (catalog source, configurable via `VULHUB_ROOT`); if missing, the `deploy` scripts will `git clone` it automatically.

## Local development (optional)

For development without Docker, run the backend and frontend separately:

```powershell
# Backend -> http://127.0.0.1:8000 (API docs at /docs)
cd range-platform/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend -> http://localhost:5173
cd ../frontend
npm install
npm run dev        # production build: npm run build -> frontend/dist
```

On first launch the SQLite database is created and the admin account is initialized.

## Docker deployment (single container)

In single-container mode the backend serves both the API and the frontend static assets (same origin, no CORS needed), and drives the host's Docker daemon (DooD) to start/stop vulhub ranges by mounting the host Docker socket.

Prerequisites: Docker and `docker compose` installed on the host; a sibling `vulhub/` directory (compose uses `../vulhub` as the mount source by default; the `deploy` scripts `git clone` it when missing).

```powershell
cd range-platform
docker compose up -d --build
```

The platform listens on `http://<host>:8000` by default; log in with the [default account](#default-account). The SQLite database persists in a volume named `range-data`, so data survives container rebuilds.

Quick verification after deployment:

```powershell
# Health check: returns {"status":"ok","environments":<loaded range count>}
Invoke-RestMethod http://localhost:8000/api/health

# Container status and live logs
docker compose ps
docker compose logs -f
```

**Configurable options** (optional, create `.env` under `range-platform/` to override):

| Variable | Description | Default |
| ------------------------ | -------------------------------- | ----------------- |
| `PLATFORM_PORT`          | Host port mapping               | 8000              |
| `SECRET_KEY`             | JWT signing key (change in prod) | change-me...      |
| `ADMIN_USERNAME`         | Initial admin username          | admin             |
| `ADMIN_PASSWORD`         | Initial admin password          | admin123          |
| `SERVER_HOST`            | Host used when building access URLs | localhost      |
| `MAX_INSTANCES_PER_USER` | Max concurrent instances per normal user | 3        |
| `PORT_RANGE_START`       | Instance port allocation range (start) | 10000      |
| `PORT_RANGE_END`         | Instance port allocation range (end)   | 12000      |
| `INSTANCE_DEFAULT_TTL_MINUTES` | Default instance auto-stop TTL (minutes); admin-tunable at runtime via System Settings | 60  |
| `INSTANCE_MAX_TTL_MINUTES`     | Max renewal duration (minutes) for non-admin users; admin-tunable at runtime | 1440 |
| `CORS_ORIGINS`           | Extra allowed CORS origins (not needed for same origin) | empty |
| `VULHUB_HOST_PATH`       | Host vulhub directory (mount source) | ../vulhub    |
| `VULHUB_MOUNT`           | vulhub mount path inside the container | /vulhub    |

> `SERVER_HOST` should be an address the browser can reach (e.g. server IP or domain); otherwise the "access URL" links point to localhost.

**About bind-mount path consistency (important)**: ranges are started by the host Docker daemon. If a vulhub `docker-compose.yml` uses a relative bind mount (e.g. `./conf:/etc/conf`), compose resolves it to the path seen inside the container and hands that to the host daemon, which then fails because the path does not exist on the host. The fix is to make the in-container mount path identical to the host absolute path:

```powershell
# e.g. host vulhub absolute path is /opt/vulhub
$env:VULHUB_HOST_PATH="/opt/vulhub"
$env:VULHUB_MOUNT="/opt/vulhub"
docker compose up -d --build
```

Most ranges that only build images / map ports do not need this.

Update the platform (rebuild image and restart after backend/frontend code changes): `docker compose up -d --build`.

Stop the platform: `docker compose down` (adding `-v` also deletes the `range-data` database volume).

## Service management (start / stop / restart)

After deployment, use the management scripts to wrap `docker compose` for convenient start/stop of the platform service (**they affect the platform container only**; running vulhub ranges are independent compose projects and are not affected by these commands).

**Linux / macOS (`manage.sh`)**:

```bash
cd range-platform
chmod +x manage.sh
./manage.sh restart      # restart the platform (Linux adds sudo automatically)
```

**Windows (`manage.ps1`)**:

```powershell
cd range-platform
powershell -ExecutionPolicy Bypass -File .\manage.ps1 restart
```

Supported commands (identical across both scripts):

| Command | Description |
| ---- | ---- |
| `start`           | Start the platform (creates the container if absent; idempotent) |
| `stop`            | Stop the platform container (keeps container and volume) |
| `restart`         | Restart the platform container |
| `status` (`ps`)   | Show container status |
| `logs`            | Follow platform logs (`--tail=200`, Ctrl-C to exit) |
| `pull`            | `git pull` the vulhub catalog, then restart (asks for y/N confirmation) |
| `rebuild` (`update`) | Rebuild the image and restart (use after backend/frontend code changes) |
| `down`            | Remove the platform container (keeps the `range-data` volume) |
| `destroy`         | Remove the container and delete the `range-data` volume (**wipes the database**, requires typing `yes` to confirm) |

> For a fuller feature and change list, see [`CHECKLIST.md`](CHECKLIST.md).

## One-click deployment (Linux / macOS / Windows)

The image is **built locally on each host**, so nothing needs to be migrated across operating systems. One-click scripts are provided for the three major systems:

| System | Script | Docker source |
| ---- | ---- | ----------- |
| Linux (major distros) | `deploy.sh` | Script auto-installs Docker Engine + compose plugin per distro |
| macOS | `deploy.sh` | Docker Desktop (installed via Homebrew `brew install --cask docker` if missing) |
| Windows | `deploy.ps1` | Docker Desktop (installed via `winget` if missing; start it manually, then re-run) |

### Option 1: one-click script (recommended)

**Linux / macOS** — sync this repository to the host and run (the script uses `uname` to detect the OS; on Linux it auto-detects the distro to choose the install method):

```bash
cd range-platform
chmod +x deploy.sh
sudo ./deploy.sh      # macOS: no sudo needed: ./deploy.sh
```

> macOS note: the script depends on Docker Desktop. If not installed, it tries `brew install --cask docker`; after install it runs `open -a Docker` and waits for the daemon to be ready. **Do not run with sudo on macOS** (Docker Desktop runs as the current user).

**Windows** — run in PowerShell (requires Docker Desktop with the WSL2 or Hyper-V backend):

```powershell
cd range-platform
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

> Windows note: if Docker is not installed, the script installs it via `winget install -e --id Docker.DockerDesktop`; then **start Docker Desktop manually and complete first-time setup**, and re-run the script. `deploy.ps1` behaves the same as `deploy.sh`: random `SECRET_KEY`/admin password, write `.env`, `docker compose up -d --build`, and print credentials once.

The script automatically: detects the distro → installs Docker and the compose plugin (and enables it at boot) if missing → generates `.env` (random `SECRET_KEY`, **random admin password**, auto-fills the host IP as `SERVER_HOST`, mounts vulhub at the **same path**) → runs `docker compose up -d --build` → prints the access URL, health-check command, and the **admin username/password generated this run, once** (record it immediately; afterwards it is only viewable in `.env`). Re-running is idempotent: an existing `.env` is not overwritten and the admin password does not change.

It auto-detects the distro and installs Docker + the compose v2 plugin — covering Debian/Ubuntu/Kali/Mint (apt), RHEL/CentOS/Rocky/Alma/Oracle/Fedora/Amazon Linux (dnf/yum), openSUSE/SLES (zypper), Arch/Manjaro (pacman) and Alpine (apk), falling back to `get.docker.com` for others. It fetches the compose plugin from GitHub Releases when missing and supports both systemd and OpenRC.

> The random password only takes effect on **the first deployment (fresh database)** — the admin account is created according to `.env`'s `ADMIN_PASSWORD` when the backend first starts with an empty database; changing `.env` afterwards does not automatically change an existing account's password.

### Reset the random admin password

Because the backend only creates the admin from `.env`'s `ADMIN_PASSWORD` when **the database is empty**, editing the password in `.env` and restarting **does not** change an existing account. To have the script generate a new random password, you must wipe the database volume and re-run:

Linux / macOS:

```bash
cd range-platform
sudo docker compose down -v   # macOS: drop sudo; -v deletes the range-data volume (SQLite DB), clearing accounts/instances
rm -f .env                    # remove the old .env so the script regenerates a random SECRET_KEY and admin password
sudo ./deploy.sh              # redeploy; the new admin credentials are printed once at the end
```

Windows (PowerShell):

```powershell
cd range-platform
docker compose down -v        # delete the range-data volume (with the DB)
Remove-Item .env -ErrorAction SilentlyContinue
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

> To change the password while **keeping existing data**, log in and change it under "User Management", or use the admin account's in-app password-change flow — do not use the `-v` command above, which wipes the entire database.

### Option 2: manual steps

The one-click script automates everything below; use these only when the script cannot run.

1. **Install Docker + compose plugin** per the [official Docker docs](https://docs.docker.com/engine/install/) (Debian/Ubuntu/Kali via apt, RHEL/CentOS/Fedora via dnf, etc.), then `sudo systemctl enable --now docker`. On macOS / Windows just install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. **Create `.env`** (key: keep vulhub paths identical inside and outside the container):

   ```bash
   cd range-platform
   VULHUB=$(cd ../vulhub && pwd)
   cat > .env <<EOF
   SECRET_KEY=$(openssl rand -hex 32)
   SERVER_HOST=$(hostname -I | awk '{print $1}')
   VULHUB_HOST_PATH=$VULHUB
   VULHUB_MOUNT=$VULHUB
   EOF
   ```
3. **Build, start, verify**:

   ```bash
   sudo docker compose up -d --build
   curl -s http://localhost:8000/api/health   # should return status ok and the range count
   ```

### Cross-platform differences and caveats

- **Image rebuilt on the target host, no artifact migration**: each host runs `docker compose up -d --build` independently, not relying on another system's build artifacts, avoiding cross-platform binary issues.
- **bind-mount path consistency (most important, per system)**: ranges are started by the host Docker daemon; vulhub environments using relative bind mounts (e.g. `./conf:/etc/conf`) require the in-container path to match a host path the daemon can resolve.
  - **Linux**: mounting vulhub at the **same absolute path** is fully compatible (the script handles this: `VULHUB_HOST_PATH=VULHUB_MOUNT=<abs path>`).
  - **macOS**: consistency is also achievable — set `VULHUB_MOUNT` to vulhub's absolute path on the Mac (e.g. `/Users/you/.../vulhub`, ensuring it is within Docker Desktop's File Sharing scope); `deploy.sh` handles this.
  - **Windows**: the host path is `C:\...` and cannot equal a Linux path inside the container, so **ranges using relative bind mounts may fail to start**; `deploy.ps1` defaults to `VULHUB_MOUNT=/vulhub`. Ranges that **only map ports** (most of them) are unaffected and start normally.
- **Docker socket / engine**: on Linux the platform container runs as root and accesses `/var/run/docker.sock` directly; on macOS / Windows Docker Desktop provides the socket, and DooD works the same.
- **SELinux (CentOS/RHEL)**: in enforcing mode the container may be denied when reading the mounted directory or accessing docker.sock. If the health check shows `environments` = 0 or logs show `permission denied`, run `sudo chcon -Rt container_file_t <vulhub abs path>`; if a test environment still fails, temporarily `sudo setenforce 0`.
- **Firewall**: open the platform port and each range's ports. ufw: `sudo ufw allow 8000/tcp`; firewalld: `sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload`.
- **Build network**: building needs access to Docker Hub / npm / PyPI. On restricted networks configure a proxy or mirrors; if `npm ci` hits an occasional network drop, retry `sudo docker compose build`.
- **Line endings must be LF**: `deploy.sh` and vulhub `docker-compose.yml` files must use LF. If transferred via Windows and turned into CRLF, fix with `sed -i 's/\r$//' deploy.sh`.

## Default account

| Username | Password | Role |
| ------ | ---------- | ----- |
| admin  | admin123   | admin |

> The table above is the default credential for local development / manual deployment (when `ADMIN_PASSWORD` is not set). **When deploying via `deploy.sh`, the admin password is randomly generated** — use the value printed at the end of the script (or `ADMIN_PASSWORD` in `.env`).
>
> In production, be sure to change `SECRET_KEY` and `ADMIN_PASSWORD` in `.env`.

## Main configuration (backend/.env)

| Variable | Description | Default |
| ------------------------ | -------------------------------------- | ------------------------- |
| `SECRET_KEY`             | JWT signing key (must change)          | change-me...              |
| `DATABASE_URL`           | Database connection                    | sqlite:///./range_platform.db |
| `VULHUB_ROOT`            | vulhub directory path (relative to backend/) | ../../vulhub        |
| `SERVER_HOST`            | Host used when building access URLs    | localhost                 |
| `ADMIN_USERNAME`         | Initial admin username                 | admin                     |
| `ADMIN_PASSWORD`         | Initial admin password                 | admin123                  |
| `MAX_INSTANCES_PER_USER` | Max concurrent running instances per normal user | 3               |
| `INSTANCE_DEFAULT_TTL_MINUTES` | Default instance auto-stop TTL (minutes). Seeded into the DB on first start; afterwards admin-tunable from the UI (System Settings) without a restart | 60  |
| `INSTANCE_MAX_TTL_MINUTES`     | Max renewal duration (minutes) for non-admin users. Seeded into the DB; admin-tunable from the UI | 1440 |
| `CORS_ORIGINS`           | Allowed frontend origins (comma-separated) | http://localhost:5173,... |

## Usage flow

1. After logging in, go to the **range list** and filter by name / CVE / app / tags.
2. Click **Details** to view the README and `docker-compose.yml`.
3. Click **Start**; the platform runs `docker compose up -d` and returns the access URL (host port).
4. In **My Instances**, view status, access URL, and logs, or stop / delete instances. Each running instance shows a **live countdown** to its auto-stop time; click **Renew** to push the deadline back (non-admins are capped by the configured max TTL).
5. Admins can create / edit / disable users under **User Management**, view all users' instances, and tune the default / max TTL under **System Settings**.

## Instance auto-stop & renewal

To prevent forgotten test environments from running indefinitely, every started instance is assigned an auto-stop deadline (`expires_at` = start time + the default TTL):

- A background reaper checks every 15s; any running instance past its deadline is stopped with `docker compose down -v` (same as a manual stop) and marked stopped.
- The **My Instances** page shows a per-second **countdown** (turns orange under 5 minutes, red under 1 minute) and auto-refreshes every 30s so auto-stops are reflected without a manual reload.
- **Renew**: click **Renew** on a running instance and choose a duration in minutes — the deadline is reset to `now + N minutes`. Non-admin users are limited to the configured max TTL; admins can pick any positive duration.
- **Admin configuration**: under **System Settings** an admin can change the **default TTL** (applied to newly started instances) and the **max renewal TTL** (the cap for non-admin renewals). These are stored in the database and take effect immediately — no restart needed. The `INSTANCE_DEFAULT_TTL_MINUTES` / `INSTANCE_MAX_TTL_MINUTES` env vars only seed the initial values on first startup.
- Existing running instances keep their already-assigned `expires_at` after a settings change; users extend them on demand via **Renew**.

## Adding and maintaining ranges

Whether a range is usable depends on two things: an entry registered in `environments.toml` (determines discoverability) + a `docker-compose.yml` in the corresponding directory (determines whether it can start).

**Sync new environments from official vulhub**:

```powershell
cd vulhub
git pull
```

**Add a custom range** (follow vulhub conventions: lowercase software directory, uppercase CVE directory, file name must be `docker-compose.yml`, LF line endings):

1. Create a directory under `VULHUB_ROOT` (e.g. `myapp/CVE-2025-0001/`) and add a `docker-compose.yml` (optional `README.md` / `README.zh-cn.md`).
2. Append an entry at the end of `environments.toml`; `path` must match the directory's relative path:

   ```toml
   [[environment]]
   name = "My App RCE"
   cve = ["CVE-2025-0001"]
   app = "myapp"
   path = "myapp/CVE-2025-0001"
   tags = ["RCE"]
   ```

   > `tags` should preferably come from values already defined in the top-level `tags = [...]`, otherwise they will not appear in the filter dropdown.

**Refresh the catalog (hot reload)**: the catalog is cached in memory. After changing the above, an admin can click the "Refresh catalog" button on the **range list** page to apply changes without restarting the backend (equivalent endpoint: `POST /api/environments/reload`, admin only).

## Notes and caveats

- Every start generates a unique compose project name and remaps the host ports declared in the range's `docker-compose.yml` to random free ports within `PORT_RANGE_START`–`PORT_RANGE_END`; therefore multiple users (or the same range started multiple times) can run concurrently without conflict, and "Environment is already running" no longer occurs. Actual mapped ports are still read from `docker compose ps` after start.
- Each instance is an independent, brand-new set of containers and volumes; stopping an instance runs `docker compose down -v`, removing that instance's containers, networks, and volumes, leaving no leftover data from the previous test.
- Some range images (e.g. older nginx) do not write logs to stdout, so the log panel may be empty — this is normal.
- If a range pins a globally unique resource such as a custom network subnet (`ipam` fixed subnet) in its `docker-compose.yml`, concurrent instances may still conflict — an inherent limitation of that particular range.
- On Windows, `docker` subprocess output is decoded uniformly as UTF-8 to avoid GBK encoding errors.
