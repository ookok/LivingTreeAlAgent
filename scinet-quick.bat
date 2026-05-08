@echo off
chcp 65001 >nul
title Scinet v2.0 — Smart Proxy

:: Activate venv if exists
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo Starting Scinet v2.0...
echo.
%PYTHON% scinet_launch.py %*
pause
