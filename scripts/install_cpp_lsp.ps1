# Install LLVM/clangd for C/C++ LSP support
# Usage: .\scripts\install_cpp_lsp.ps1
# On-demand installation — only run when C/C++ LSP needed

$ErrorActionPreference = "Stop"

Write-Host "Installing LLVM/clangd (C/C++ LSP)..." -ForegroundColor Cyan

$installed = $false

# Try winget (smaller download, just LLVM tools)
try {
    winget install --id LLVM.LLVM --silent --accept-package-agreements 2>$null
    if ($LASTEXITCODE -eq 0) { $installed = $true }
} catch {
    Write-Host "winget unavailable" -ForegroundColor Yellow
}

if (-not $installed) {
    # Direct download of clangd standalone (much smaller than full LLVM)
    $version = "20.1.0"
    $url = "https://github.com/clangd/clangd/releases/download/$version/clangd-windows-$version.zip"
    $zip = "$env:TEMP\clangd.zip"
    $dest = "$env:LOCALAPPDATA\clangd"

    Write-Host "Downloading clangd $version (standalone)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $url -OutFile $zip

    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    Remove-Item $zip -Force

    # Add to PATH
    $binPath = "$dest\clangd_$version\bin"
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$binPath*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$binPath", "User")
    }
    $env:Path += ";$binPath"
    Write-Host "clangd installed to: $binPath" -ForegroundColor Green
}

Write-Host "Done. Verify: clangd --version" -ForegroundColor Green
Write-Host "Restart your terminal for PATH to take effect." -ForegroundColor Yellow
