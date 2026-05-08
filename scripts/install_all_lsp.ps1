# Master LSP installation script — installs all language servers
# Usage: .\scripts\install_all_lsp.ps1
# Or for individual languages: .\scripts\install_go_lsp.ps1 | install_cpp_lsp.ps1

Write-Host "=== LivingTree LSP Installer ===" -ForegroundColor Green
Write-Host ""

# ── Python (required, always install) ──
Write-Host "[1/4] Python LSP..." -ForegroundColor Cyan
pip install basedpyright ruff mypy python-lsp-server -q
Write-Host "  basedpyright + ruff + mypy + pylsp" -ForegroundColor Green

# ── Web/Config (always useful) ──
Write-Host "[2/4] Web/Config LSP..." -ForegroundColor Cyan
npm install -g typescript-language-server typescript vscode-langservers-extracted yaml-language-server bash-language-server dockerfile-language-server-node 2>$null
Write-Host "  TS/HTML/CSS/JSON/Markdown/YAML/Bash/Dockerfile" -ForegroundColor Green

# ── Go (on-demand) ──
$go = Get-Command go -ErrorAction SilentlyContinue
if ($go) {
    Write-Host "[3/4] Go LSP..." -ForegroundColor Cyan
    go install golang.org/x/tools/gopls@latest
    Write-Host "  gopls (Go toolchain already installed)" -ForegroundColor Green
} else {
    Write-Host "[3/4] Go LSP — skipped (run .\scripts\install_go_lsp.ps1 to install)" -ForegroundColor Yellow
}

# ── C/C++ (on-demand) ──
$clangd = Get-Command clangd -ErrorAction SilentlyContinue
if ($clangd) {
    Write-Host "[4/4] C/C++ LSP — already installed" -ForegroundColor Green
} else {
    Write-Host "[4/4] C/C++ LSP — skipped (run .\scripts\install_cpp_lsp.ps1 to install)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Run 'ruff check livingtree/' to verify." -ForegroundColor Green
