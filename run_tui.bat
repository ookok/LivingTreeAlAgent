@echo off
chcp 65001 > nul
title LivingTree AI Agent

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo      LivingTree AI Agent v2.0.0
echo      ============================
echo.

REM Check if WT is available, download if not
python -c "from livingtree.tui.wt_bootstrap import ensure_wt; ensure_wt()" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Launch failed.
    echo Try: pip install textual aiohttp pydantic loguru pyyaml litellm
    echo.
    pause
)
