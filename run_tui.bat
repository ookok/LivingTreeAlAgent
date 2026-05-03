@echo off
chcp 65001 > nul
title LivingTree AI Agent - TUI

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo      LivingTree AI Agent v2.0.0
echo      Digital Lifeform - TUI Mode
echo      ============================
echo.

python -m livingtree tui %*

if errorlevel 1 (
    echo.
    echo [ERROR] Launch failed.
    echo Make sure dependencies are installed: pip install textual aiohttp pydantic loguru pyyaml
    echo.
    pause
)
