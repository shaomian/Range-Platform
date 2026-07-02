<#
  Management helper for the Vulhub Range Platform (Windows / PowerShell).
  Wraps `docker compose` for the platform container defined in docker-compose.yml.
  Linux / macOS users: use ./manage.sh instead.

  Usage (from the range-platform directory):
    powershell -ExecutionPolicy Bypass -File .\manage.ps1 <command>

  Commands:
    start     Start the platform (creates the container if missing; idempotent).
    stop      Stop the platform container (keeps it; data volume preserved).
    restart   Restart the platform container.
    pull      Update the vulhub catalog (git pull) then restart to reload it.
    status    Show container status (docker compose ps).
    logs      Follow the platform logs (Ctrl-C to exit).
    rebuild   Rebuild the image and restart (after backend/frontend changes).
    down      Remove the platform container (data volume preserved).
    destroy   Remove the container AND the range-data volume (DELETES the database!).

  NOTE: These commands only affect the *platform* container. Running vulhub
  targets are separate compose projects and are unaffected by stop/restart.
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('start', 'stop', 'restart', 'pull', 'status', 'ps', 'logs',
    'rebuild', 'update', 'down', 'destroy', 'help')]
  [string]$Command = 'help'
)
$ErrorActionPreference = 'Stop'

function Log  ($m) { Write-Host "==> $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "[!] $m"  -ForegroundColor Yellow }
function Die  ($m) { Write-Host "[x] $m"  -ForegroundColor Red; exit 1 }

Set-Location -Path $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Die "docker not found. Run deploy.ps1 first."
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Die "docker compose v2 unavailable." }

function Invoke-Dc { docker compose @args; if ($LASTEXITCODE -ne 0) { Die "docker compose failed." } }

function Show-Usage {
  Get-Content -Path $PSCommandPath |
    Select-Object -Skip 1 -First 20 |
    ForEach-Object { $_ -replace '^\s{0,2}', '' }
}

switch ($Command) {
  'start' {
    Log "Starting the platform (docker compose up -d)"
    Invoke-Dc up -d
    Invoke-Dc ps
  }
  'stop' {
    Log "Stopping the platform container (docker compose stop)"
    Invoke-Dc stop
  }
  'restart' {
    Log "Restarting the platform container (docker compose restart)"
    Invoke-Dc restart
    Invoke-Dc ps
  }
  'pull' {
    # Resolve the vulhub git working directory: prefer VULHUB_HOST_PATH from
    # .env (if a compose env file exists), else the default sibling ../vulhub.
    $vulhubDir = $null
    $envFile = Join-Path $PSScriptRoot '.env'
    if (Test-Path $envFile) {
      $line = Select-String -Path $envFile -Pattern '^VULHUB_HOST_PATH=' | Select-Object -First 1
      if ($line) { $vulhubDir = ($line.Line -replace '^VULHUB_HOST_PATH=', '').Trim() }
    }
    if (-not $vulhubDir) { $vulhubDir = Join-Path $PSScriptRoot '..\vulhub' }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "git not found in PATH." }
    if (-not (Test-Path $vulhubDir)) { Die "vulhub directory not found at $vulhubDir" }
    if (-not (Test-Path (Join-Path $vulhubDir '.git'))) {
      Die "$vulhubDir is not a git repository (clone vulhub with 'git clone' first)."
    }
    Warn "This will run 'git pull' in $vulhubDir and then restart the platform."
    $reply = Read-Host 'Proceed? [y/N]'
    if ($reply -notmatch '^(y|yes)$') { Log "Aborted."; return }
    Log "Updating vulhub catalog (git pull)"
    Push-Location $vulhubDir
    try { git pull; if ($LASTEXITCODE -ne 0) { Die "git pull failed." } }
    finally { Pop-Location }
    Log "Restarting the platform to reload the catalog (docker compose restart)"
    Invoke-Dc restart
    Invoke-Dc ps
  }
  { $_ -in 'status', 'ps' } {
    Invoke-Dc ps
  }
  'logs' {
    Log "Following platform logs (Ctrl-C to exit)"
    Invoke-Dc logs -f --tail=200
  }
  { $_ -in 'rebuild', 'update' } {
    Log "Rebuilding image and restarting (docker compose up -d --build)"
    Invoke-Dc up -d --build
    Invoke-Dc ps
  }
  'down' {
    Log "Removing the platform container (data volume kept)"
    Invoke-Dc down
  }
  'destroy' {
    Warn "This removes the container AND the range-data volume (SQLite database,"
    Warn "user accounts and instance records will be permanently deleted)."
    $reply = Read-Host 'Type EXACTLY "yes" to continue'
    if ($reply -ne 'yes') { Die "Aborted." }
    Log "Removing container and range-data volume (docker compose down -v)"
    Invoke-Dc down -v
  }
  default {
    Show-Usage
  }
}
