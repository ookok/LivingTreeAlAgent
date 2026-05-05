# LivingTree — One-Command Auto-Deploy (PowerShell)
# Usage: powershell -c "irm https://raw...install.ps1 | iex"
#        .\install.ps1 -Port 8100 -Relay

param(
    [int]$Port = 8100,
    [switch]$Relay = $false,
    [string]$InstallDir = "$env:USERPROFILE\livingtree"
)

$ErrorActionPreference = "Stop"
$Mode = if ($Relay) { "relay" } else { "client" }

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  LivingTree Auto-Deploy (PowerShell)      ║" -ForegroundColor Cyan
Write-Host "║  Mode: $Mode  Port: $Port" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# [1/7] Python
Write-Host "[1/7] Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "   Python not found. Downloading Python 3.14..."
    $pyUrl = "https://mirrors.huaweicloud.com/python/3.14.0/python-3.14.0-amd64.exe"
    $pyInstaller = "$env:TEMP\python314.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -TimeoutSec 120
    Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=0 Include_test=0" -Wait
    Write-Host "   Python 3.14 installed. Re-run this script."
    return
}
& python --version

# [2/7] Clone
Write-Host "[2/7] Downloading project..." -ForegroundColor Yellow
$githubUrl = "https://github.com/ookok/LivingTreeAlAgent.git"
$giteeUrl = "https://gitee.com/ookok/LivingTreeAlAgent.git"

if (Test-Path $InstallDir) {
    Write-Host "   Directory exists — updating..."
    Set-Location $InstallDir
    git pull --ff-only origin main 2>$null
} else {
    try {
        git clone --depth 1 $githubUrl $InstallDir 2>$null
    } catch {
        Write-Host "   GitHub failed, trying Gitee mirror..."
        git clone --depth 1 $giteeUrl $InstallDir 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Cannot clone. Check network." -ForegroundColor Red
            return
        }
    }
}
Set-Location $InstallDir

# [3/7] Venv
Write-Host "[3/7] Virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    & python -m venv .venv
}
& .venv\Scripts\Activate.ps1

# [4/7] Deps
Write-Host "[4/7] Installing dependencies..." -ForegroundColor Yellow
pip install -e . --quiet 2>$null
pip install aiohttp pyyaml pydantic loguru rich textual --quiet 2>$null

# [5/7] Verify
Write-Host "[5/7] Verifying..." -ForegroundColor Yellow
.venv\Scripts\python.exe -c "from livingtree.tui.app import LivingTreeTuiApp; print('OK')" 2>$null

# [6/7] Launcher
Write-Host "[6/7] Creating launcher..." -ForegroundColor Yellow
@"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
if "%1"=="relay" (
    python relay_server.py --port $Port %2 %3 %4 %5
) else (
    python -m livingtree tui %*
)
"@ | Out-File -FilePath "livingtree.bat" -Encoding ASCII

[Environment]::SetEnvironmentVariable("Path", "$InstallDir;" + [Environment]::GetEnvironmentVariable("Path", "User"), "User")

# [7/7] Done
Write-Host "[7/7] Done!" -ForegroundColor Green
Write-Host ""
if ($Relay) {
    Write-Host "Starting relay server on port $Port..." -ForegroundColor Cyan
    & .venv\Scripts\python.exe relay_server.py --port $Port
} else {
    Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  LivingTree installed successfully!      ║" -ForegroundColor Green
    Write-Host "║                                          ║" -ForegroundColor Green
    Write-Host "║  livingtree         Launch TUI           ║" -ForegroundColor Green
    Write-Host "║  livingtree relay   Start relay server   ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
}
