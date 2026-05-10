# One-click installer — LivingTree AI Agent (Windows PowerShell)
# Usage: irm https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.ps1 | iex

param([switch]$Dev, [switch]$Relay, [switch]$NoPython)

$ErrorActionPreference = "Stop"
$INSTALL_DIR = "$env:USERPROFILE\livingtree"
$VENV_DIR = "$INSTALL_DIR\.venv"
$PYTHON_MIN = "3.10"
$REPO_URL = "https://github.com/ookok/LivingTreeAlAgent.git"
$REPO_GITEE = "https://gitee.com/ookok/LivingTreeAlAgent.git"
$PORT = 8100

Write-Host @"
╔══════════════════════════════════════════════╗
║   🌳 生命之树 · LivingTree AI Agent          ║
║       One-Click Windows Installer            ║
╚══════════════════════════════════════════════╝
"@ -ForegroundColor Green

# ── Check Python ──

if (-not $NoPython) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }

    if (-not $python) {
        Write-Host "❌ Python not found. Installing via winget..." -ForegroundColor Red
        winget install Python.Python.3.12 --silent --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        refreshenv 2>$null
        $python = Get-Command python -ErrorAction SilentlyContinue
    }

    if ($python) {
        $ver = & $python.Source --version 2>&1
        Write-Host "✅ Python: $ver" -ForegroundColor Green
    } else {
        Write-Host "❌ Python installation failed. Install manually: https://python.org" -ForegroundColor Red
        exit 1
    }
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
}

# ── Clone / Update ──

if (Test-Path "$INSTALL_DIR\.git") {
    Write-Host "📥 Updating repository..." -ForegroundColor Cyan
    Push-Location $INSTALL_DIR
    git pull origin main 2>$null
    Pop-Location
} else {
    Write-Host "📥 Cloning repository..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force $INSTALL_DIR -ErrorAction SilentlyContinue
    git clone --depth 1 $REPO_URL $INSTALL_DIR 2>$null
    if (-not $?) {
        Write-Host "  Trying mirror..." -ForegroundColor Yellow
        git clone --depth 1 $REPO_GITEE $INSTALL_DIR
    }
}

Set-Location $INSTALL_DIR

# ── Setup venv ──

if (-not (Test-Path "$VENV_DIR\Scripts\python.exe")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Cyan
    & $python.Source -m venv $VENV_DIR
}

$pip = "$VENV_DIR\Scripts\pip.exe"
$py = "$VENV_DIR\Scripts\python.exe"

Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
& $pip install --upgrade pip -q
& $pip install -r requirements.txt -q

if ($Dev) {
    & $pip install -r requirements-dev.txt -q 2>$null
}

# ── Install optional tools ──

Write-Host "📦 Installing optional tools..." -ForegroundColor Cyan
& $pip install edge-tts -q 2>$null
& $pip install numpy -q 2>$null

# ── Check GPU ──

$gpu = & nvidia-smi 2>$null
if ($gpu) {
    Write-Host "✅ GPU detected (NVIDIA)" -ForegroundColor Green
}

# ── Create shortcut ──

$shortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\LivingTree.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($shortcut)
$s.TargetPath = $py
$s.Arguments = "-m livingtree web"
$s.WorkingDirectory = $INSTALL_DIR
$s.Description = "生命之树 · LivingTree AI Agent"
$s.Save()

# ── Check Node.js (for npx MCP mode) ──

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "✅ Node.js detected (npm MCP mode available)" -ForegroundColor Green
} else {
    Write-Host "💡 Install Node.js for Chrome automation: https://nodejs.org" -ForegroundColor Yellow
}

# ── Done ──

Write-Host @"

✅ Installation complete!

Start LivingTree:
  cd $INSTALL_DIR
  .venv\Scripts\python.exe -m livingtree

Or use the Start Menu shortcut: LivingTree
Web UI: http://localhost:$PORT/tree/living

CLI Management (CowAgent style):
  .venv\Scripts\python.exe -m livingtree start     # background daemon
  .venv\Scripts\python.exe -m livingtree stop      # stop service
  .venv\Scripts\python.exe -m livingtree status    # service status

"@ -ForegroundColor Green

# ── Auto-start (optional) ──

$auto = Read-Host "Auto-start LivingTree now? (y/N)"
if ($auto -eq "y" -or $auto -eq "Y") {
    Write-Host "🚀 Starting LivingTree..." -ForegroundColor Cyan
    Start-Process -FilePath $py -ArgumentList "-m livingtree web" -WorkingDirectory $INSTALL_DIR
    Start-Sleep 3
    Start-Process "http://localhost:$PORT/tree/living"
}
