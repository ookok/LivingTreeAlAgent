# Java LSP Installer — 安装 Eclipse JDTLS + JDK
# 使用方法: .\scripts\install_java_lsp.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Java LSP: Eclipse JDT Language Server ===" -ForegroundColor Cyan

# Step 1: Install JDK 17 (Eclipse Temurin)
$java = Get-Command java -ErrorAction SilentlyContinue
if (-not $java) {
    Write-Host "JDK 未安装，正在安装 Eclipse Temurin 17..." -ForegroundColor Yellow
    winget install EclipseAdoptium.Temurin.17.JDK --accept-package-agreements --accept-source-agreements
    Write-Host "JDK 17 安装完成，请重启终端使 java 生效" -ForegroundColor Green
} else {
    Write-Host "JDK 已安装: $(java -version 2>&1 | Select-Object -First 1)" -ForegroundColor Green
}

# Step 2: Download and install JDTLS
$jdtlsDir = "$env:USERPROFILE\.jdtls"
if (Test-Path "$jdtlsDir\bin\jdtls") {
    Write-Host "JDTLS 已安装: $jdtlsDir" -ForegroundColor Green
    exit 0
}

Write-Host "下载 JDTLS..." -ForegroundColor Yellow
$url = "https://download.eclipse.org/jdtls/milestones/latest/jdt-language-server-latest.tar.gz"
$tgz = "$env:TEMP\jdtls.tar.gz"
$extract = "$env:TEMP\jdtls_extract"

try {
    Invoke-WebRequest -Uri $url -OutFile $tgz -UseBasicParsing
    New-Item -ItemType Directory -Path $extract -Force | Out-Null
    tar -xzf $tgz -C $extract
    Move-Item -Path $extract\* -Destination $jdtlsDir -Force
    Remove-Item $tgz -Force
    Remove-Item $extract -Recurse -Force
    Write-Host "JDTLS 安装完成: $jdtlsDir" -ForegroundColor Green
    Write-Host ""
    Write-Host "请在 OpenCode 配置中添加:" -ForegroundColor Cyan
    Write-Host "  [lsp.java]" -ForegroundColor White
    Write-Host '  command = "java"' -ForegroundColor White
    Write-Host "  args = [...]" -ForegroundColor White
} catch {
    Write-Host "JDTLS 下载失败: $_" -ForegroundColor Red
    Write-Host "替代方案：npm install -g java-language-server" -ForegroundColor Yellow
}
