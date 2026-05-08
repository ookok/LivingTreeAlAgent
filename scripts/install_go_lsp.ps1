# Install Go toolchain + gopls LSP server
# Usage: .\scripts\install_go_lsp.ps1
# On-demand installation — only run when Go LSP needed

$ErrorActionPreference = "Stop"

Write-Host "Installing Go toolchain..." -ForegroundColor Cyan

# Try winget first
$goInstalled = $false
try {
    winget install --id GoLang.Go --silent --accept-package-agreements 2>$null
    if ($LASTEXITCODE -eq 0) { $goInstalled = $true }
} catch {
    Write-Host "winget not available, trying direct download..." -ForegroundColor Yellow
}

if (-not $goInstalled) {
    $goVersion = "1.24.3"
    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
    $url = "https://go.dev/dl/go$goVersion.windows-$arch.msi"
    $msi = "$env:TEMP\go-installer.msi"
    Write-Host "Downloading Go $goVersion..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $url -OutFile $msi
    Start-Process msiexec.exe -ArgumentList "/i", $msi, "/quiet", "/norestart" -Wait
    Remove-Item $msi -Force
}

# Refresh PATH
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "Installing gopls (Go LSP)..." -ForegroundColor Cyan
go install golang.org/x/tools/gopls@latest

Write-Host "Done. gopls installed at: $(go env GOPATH)\bin\gopls.exe" -ForegroundColor Green
Write-Host "Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
