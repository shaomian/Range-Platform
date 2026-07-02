#!/usr/bin/env bash
# One-click deployment for the Vulhub Range Platform on Linux and macOS.
# Linux: installs Docker + the compose v2 plugin if missing across all mainstream
#   distros: Debian/Ubuntu/Kali/Mint (apt), Fedora/CentOS/RHEL/Rocky/Alma/Oracle
#   (dnf|yum), Amazon Linux, openSUSE/SLES (zypper), Arch/Manjaro (pacman),
#   Alpine (apk); anything else falls back to get.docker.com.
# macOS: uses Docker Desktop (installed via Homebrew cask if missing), starts it.
# Windows users: run deploy.ps1 instead (PowerShell).
# If the sibling ../vulhub catalog is missing it is cloned from GitHub.
# In all cases it writes .env, then builds & starts via docker compose.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# Set by write_env when it generates a fresh .env, so main() can print the
# one-time admin password. Empty means an existing .env was left untouched.
NEW_ADMIN_PW=""

OS="$(uname -s)"
DISTRO_ID=""; LIKE=""
if [ "$OS" = "Linux" ]; then
  [ -r /etc/os-release ] || die "cannot read /etc/os-release; unsupported Linux system"
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO_ID="${ID:-}"; LIKE="${ID_LIKE:-}"
elif [ "$OS" != "Darwin" ]; then
  die "unsupported OS '$OS'. On Windows run deploy.ps1 in PowerShell instead."
fi

# Linux needs sudo for package installs and the docker daemon; macOS Docker
# Desktop runs as the current user and must NOT be driven with sudo.
SUDO=""
if [ "$OS" = "Linux" ] && [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

# Report the primary LAN IPv4 (used for SERVER_HOST / access URL), OS-aware.
detect_ip() {
  local ip=""
  if [ "$OS" = "Darwin" ]; then
    ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
  else
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  fi
  [ -n "$ip" ] || ip="localhost"
  printf '%s' "$ip"
}

install_docker_apt() {
  local repo="$1" codename="$2"
  log "Installing Docker from download.docker.com/linux/$repo ($codename)"
  $SUDO apt-get update -y
  $SUDO apt-get install -y ca-certificates curl gnupg
  $SUDO install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$repo/gpg" \
    | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$repo $codename stable" \
    | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
  $SUDO apt-get update -y
  $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
}

install_docker_dnf() {
  local repo="${1:-centos}"
  log "Installing Docker from download.docker.com/linux/$repo"
  if command -v dnf >/dev/null 2>&1; then
    $SUDO dnf -y install dnf-plugins-core
    $SUDO dnf config-manager --add-repo "https://download.docker.com/linux/$repo/docker-ce.repo"
    $SUDO dnf install -y docker-ce docker-ce-cli containerd.io \
      docker-buildx-plugin docker-compose-plugin
  else
    $SUDO yum -y install yum-utils
    $SUDO yum-config-manager --add-repo "https://download.docker.com/linux/$repo/docker-ce.repo"
    $SUDO yum install -y docker-ce docker-ce-cli containerd.io \
      docker-buildx-plugin docker-compose-plugin
  fi
}

install_docker_amazon() {
  log "Installing Docker for Amazon Linux"
  if command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y docker
  elif command -v amazon-linux-extras >/dev/null 2>&1; then
    $SUDO amazon-linux-extras enable docker && $SUDO yum install -y docker
  else
    $SUDO yum install -y docker
  fi
}

install_docker_zypper() { log "Installing Docker via zypper (openSUSE / SLES)"; $SUDO zypper --non-interactive install docker; }
install_docker_pacman() { log "Installing Docker via pacman (Arch family)"; $SUDO pacman -Sy --noconfirm docker; }
install_docker_apk()    { log "Installing Docker via apk (Alpine)"; $SUDO apk add --no-cache docker docker-cli-compose; }

install_docker_convenience() {
  warn "Using Docker convenience script (get.docker.com) for '$DISTRO_ID'"
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  $SUDO sh /tmp/get-docker.sh
}

# Install the Docker engine using the best method for the detected distribution.
install_docker_engine() {
  case "$DISTRO_ID" in
    ubuntu|linuxmint|pop|zorin|elementary|neon)
      install_docker_apt ubuntu "${UBUNTU_CODENAME:-${VERSION_CODENAME:-jammy}}" ;;
    kali)                     install_docker_apt debian bookworm ;;
    debian|raspbian|devuan|mx)
      install_docker_apt debian "${VERSION_CODENAME:-bookworm}" ;;
    fedora)                   install_docker_dnf fedora ;;
    centos|rhel|rocky|almalinux|ol|oracle|virtuozzo|cloudlinux)
      install_docker_dnf centos ;;
    amzn)                     install_docker_amazon ;;
    opensuse*|sles|sled|suse) install_docker_zypper ;;
    arch|manjaro|endeavouros|garuda|artix)
      install_docker_pacman ;;
    alpine)                   install_docker_apk ;;
    *)
      case " $LIKE " in
        *" ubuntu "*)            install_docker_apt ubuntu "${UBUNTU_CODENAME:-${VERSION_CODENAME:-jammy}}" ;;
        *" debian "*)            install_docker_apt debian "${VERSION_CODENAME:-bookworm}" ;;
        *" fedora "*)            install_docker_dnf fedora ;;
        *" rhel "*|*" centos "*) install_docker_dnf centos ;;
        *" suse "*)              install_docker_zypper ;;
        *" arch "*)              install_docker_pacman ;;
        *" alpine "*)            install_docker_apk ;;
        *)                       install_docker_convenience ;;
      esac ;;
  esac
}

# Guarantee the docker compose v2 plugin exists (backend uses `docker compose`).
ensure_compose_plugin() {
  docker compose version >/dev/null 2>&1 && return
  warn "docker compose v2 plugin missing; installing it from GitHub releases"
  local arch plugin_dir
  case "$(uname -m)" in
    x86_64|amd64)  arch=x86_64 ;;
    aarch64|arm64) arch=aarch64 ;;
    armv7l|armv7)  arch=armv7 ;;
    ppc64le)       arch=ppc64le ;;
    s390x)         arch=s390x ;;
    *)             arch="$(uname -m)" ;;
  esac
  plugin_dir=/usr/local/lib/docker/cli-plugins
  $SUDO mkdir -p "$plugin_dir"
  $SUDO curl -fsSL \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$arch" \
    -o "$plugin_dir/docker-compose"
  $SUDO chmod +x "$plugin_dir/docker-compose"
  docker compose version >/dev/null 2>&1 \
    || die "docker compose still unavailable; install the compose v2 plugin manually"
}

# Start and enable the Docker service across init systems (systemd / OpenRC).
start_docker() {
  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now docker || true
  elif command -v rc-update >/dev/null 2>&1; then
    $SUDO rc-update add docker boot || true
    $SUDO service docker start || true
  else
    $SUDO service docker start || true
  fi
}

# Wait until the Docker daemon is reachable (Docker Desktop can take a while).
wait_for_docker() {
  local i=0
  until docker info >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -gt 60 ] && die "Docker daemon not ready after ~120s; start Docker Desktop and re-run"
    sleep 2
  done
}

# macOS: rely on Docker Desktop (installed via Homebrew cask when missing).
ensure_docker_macos() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker already present: $(docker --version)"
  elif command -v brew >/dev/null 2>&1; then
    log "Installing Docker Desktop via Homebrew (brew install --cask docker)"
    brew install --cask docker
  else
    die "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/ (or install Homebrew then 'brew install --cask docker'), start it, then re-run ./deploy.sh"
  fi
  if ! docker info >/dev/null 2>&1; then
    log "Starting Docker Desktop and waiting for the daemon..."
    open -a Docker >/dev/null 2>&1 || true
    wait_for_docker
  fi
  docker compose version >/dev/null 2>&1 \
    || die "docker compose v2 unavailable; update Docker Desktop to a recent version"
}

ensure_docker() {
  if [ "$OS" = "Darwin" ]; then
    ensure_docker_macos
    return
  fi
  if command -v docker >/dev/null 2>&1; then
    log "Docker already present: $(docker --version)"
  else
    install_docker_engine
  fi
  start_docker
  ensure_compose_plugin
}

# Ensure git is available (needed to clone the vulhub catalog on fresh hosts).
ensure_git() {
  command -v git >/dev/null 2>&1 && return
  if [ "$OS" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then brew install git; else
      die "git not found. Run 'xcode-select --install' (or install Homebrew git), then re-run."
    fi
  else
    warn "git not found; installing it"
    if   command -v apt-get >/dev/null 2>&1; then $SUDO apt-get install -y git
    elif command -v dnf     >/dev/null 2>&1; then $SUDO dnf install -y git
    elif command -v yum     >/dev/null 2>&1; then $SUDO yum install -y git
    elif command -v zypper  >/dev/null 2>&1; then $SUDO zypper --non-interactive install git
    elif command -v pacman  >/dev/null 2>&1; then $SUDO pacman -Sy --noconfirm git
    elif command -v apk     >/dev/null 2>&1; then $SUDO apk add --no-cache git
    else die "could not install git automatically; install it and re-run."
    fi
  fi
  command -v git >/dev/null 2>&1 || die "git still unavailable after install attempt."
}

# The platform reads its catalog from a sibling ../vulhub directory. On a fresh
# deployment only range-platform/ is present, so clone the upstream catalog.
ensure_vulhub() {
  local vulhub_dir="$SCRIPT_DIR/../vulhub"
  if [ -d "$vulhub_dir/.git" ]; then
    log "vulhub catalog already present ($vulhub_dir)"
    return
  fi
  if [ -d "$vulhub_dir" ]; then
    warn "vulhub directory exists but is not a git clone; leaving it as-is"
    return
  fi
  ensure_git
  log "Cloning vulhub catalog (git clone https://github.com/vulhub/vulhub.git)"
  git clone https://github.com/vulhub/vulhub.git "$vulhub_dir" \
    || die "git clone failed; check your network and retry."
}

write_env() {
  if [ -f .env ]; then
    log ".env already exists; leaving it unchanged"
    return
  fi
  local vulhub ip secret admin_pw
  vulhub="$(cd "$SCRIPT_DIR/../vulhub" 2>/dev/null && pwd || true)"
  [ -n "$vulhub" ] || warn "vulhub not found beside range-platform/; edit .env afterwards"
  ip="$(detect_ip)"
  secret="$(openssl rand -hex 32 2>/dev/null || echo "change-me-$(date +%s)")"
  # Random admin password for this first-time deployment (16 alphanumerics).
  admin_pw="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c 16 || true)"
  [ -n "$admin_pw" ] || admin_pw="$(openssl rand -hex 8 2>/dev/null || echo "change-me-$(date +%s)")"
  NEW_ADMIN_PW="$admin_pw"
  log "Writing .env (SERVER_HOST=$ip, vulhub=$vulhub)"
  cat > .env <<EOF
# Generated by deploy.sh. Adjust as needed, then re-run the deploy script.
SECRET_KEY=$secret
SERVER_HOST=$ip
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$admin_pw
MAX_INSTANCES_PER_USER=3
# Mount vulhub at an identical host path so target relative bind mounts resolve.
VULHUB_HOST_PATH=$vulhub
VULHUB_MOUNT=$vulhub
EOF
}

main() {
  ensure_docker
  ensure_vulhub
  write_env
  log "Building and starting the platform (docker compose up -d --build)"
  $SUDO docker compose up -d --build
  local ip; ip="$(detect_ip)"
  echo
  log "Deployment complete."
  log "URL:   http://$ip:8000"
  log "Check: curl -s http://localhost:8000/api/health"
  if [ -n "$NEW_ADMIN_PW" ]; then
    echo
    warn "==================== SAVE THESE CREDENTIALS ===================="
    warn "Initial admin account (generated once, on a fresh database):"
    warn "    username: admin"
    warn "    password: $NEW_ADMIN_PW"
    warn "Stored as ADMIN_PASSWORD in $SCRIPT_DIR/.env. Change it after login."
    warn "==============================================================="
  else
    log "Existing .env kept; admin password unchanged (see ADMIN_PASSWORD in .env)."
  fi
  if [ "$OS" = "Linux" ]; then
    warn "If the platform port is blocked, open it in the firewall:"
    warn "  ufw:      sudo ufw allow 8000/tcp"
    warn "  firewalld: sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload"
    warn "SELinux (CentOS/RHEL): if targets fail to read files, run"
    warn "  sudo chcon -Rt container_file_t \"$([ -f .env ] && grep -m1 '^VULHUB_HOST_PATH=' .env | cut -d= -f2 || echo /path/to/vulhub)\""
  fi
}

main "$@"
