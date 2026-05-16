@echo off
chcp 65001 >nul
title Scinet v2.0 — Smart Proxy

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo.
echo   Scinet v2.0 — Smart Proxy
echo   Auto-configures system proxy (use --no-pac to disable)
echo.
%PYTHON% -m pip install aioquic -q 2>nul
%PYTHON% scinet_launch.py %*
pause
