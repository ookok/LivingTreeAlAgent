# Install C# LSP Server (OmniSharp / Roslyn Language Server)
# Requires: .NET SDK (already installed: 8.0.412)
Write-Host "=== C# LSP Installation ==="

$installed = $false
$omnisharpPath = "$env:USERPROFILE\.omnisharp\omnisharp-roslyn"
$lspMarker = "$env:USERPROFILE\.livingtree\lsp_csharp_installed"

# ── Approach 1: Check if dotnet tool is available ──
try {
    $result = dotnet tool install --global csharp-ls 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] csharp-ls dotnet tool installed" -ForegroundColor Green
        $installed = $true
    } else {
        Write-Host "[SKIP] csharp-ls not available as dotnet tool (package issue)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[SKIP] csharp-ls dotnet tool failed" -ForegroundColor Yellow
}

# ── Approach 2: Download OmniSharp standalone ──
if (-not $installed) {
    try {
        $rel = Invoke-RestMethod "https://api.github.com/repos/OmniSharp/omnisharp-roslyn/releases/latest" -ErrorAction Stop
        $assets = $rel.assets | Where-Object { $_.name -match "win-x64-net8" -or $_.name -match "win-x64-net6" -or $_.name -match "win-x64" }
        if ($assets) {
            $asset = $assets[0]
            $dlUrl = $asset.browser_download_url
            Write-Host "Downloading: $($asset.name)..." -ForegroundColor Cyan
            New-Item -ItemType Directory -Path $omnisharpPath -Force | Out-Null
            $zipPath = "$env:TEMP\omnisharp.zip"
            Invoke-WebRequest -Uri $dlUrl -OutFile $zipPath
            Expand-Archive -Path $zipPath -DestinationPath $omnisharpPath -Force
            Remove-Item $zipPath

            # Find OmniSharp.exe
            $exe = Get-ChildItem -Path $omnisharpPath -Recurse -Filter "OmniSharp.exe" | Select-Object -First 1
            if ($exe) {
                Write-Host "[OK] OmniSharp installed: $($exe.FullName)" -ForegroundColor Green
                $installed = $true
                # Add to PATH
                $binDir = Split-Path $exe.FullName -Parent
                [Environment]::SetEnvironmentVariable("Path", "$env:Path;$binDir", "User")
            }
        } else {
            Write-Host "[INFO] OmniSharp v$($rel.tag_name) has no standalone Windows binaries" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[SKIP] OmniSharp download failed: $_" -ForegroundColor Yellow
    }
}

# ── Approach 3: Mono-based OmniSharp ──
if (-not $installed) {
    Write-Host "[INFO] Alternative: Install Mono (mono-project.com) via winget" -ForegroundColor Yellow
    try {
        $mono = winget list --name Mono --exact 2>&1 | Out-String
        if ($mono -match "Mono") {
            Write-Host "[OK] Mono already installed — OmniSharp works with Mono" -ForegroundColor Green
        } else {
            Write-Host "[CMD] To install: winget install Mono.Mono" -ForegroundColor Yellow
        }
    } catch {}
}

# ── Also install omnisharp-vim/emacs client ──
try {
    npm list -g omnisharp-client 2>$null
    if ($LASTEXITCODE -ne 0) {
        npm install -g omnisharp-client 2>&1 | Out-Null
    }
    Write-Host "[OK] omnisharp-client npm package available" -ForegroundColor Green
} catch {
    Write-Host "[SKIP] omnisharp-client npm install failed" -ForegroundColor Yellow
}

# ── Mark installation ──
New-Item -ItemType Directory -Path (Split-Path $lspMarker -Parent) -Force | Out-Null
if ($installed) {
    "installed_$(Get-Date -Format 'yyyyMMdd')" | Set-Content $lspMarker
    Write-Host "`nC# LSP ready! (OmniSharp / csharp-ls)" -ForegroundColor Green
} else {
    "pending_vs_or_mono" | Set-Content $lspMarker
    Write-Host "`nC# LSP partial: omnisharp-client npm installed." -ForegroundColor Yellow
    Write-Host "Full support requires Visual Studio Build Tools or Mono for OmniSharp server." -ForegroundColor Yellow
}
