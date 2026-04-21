@echo off
REM LivingTree AI Agent - Windows Startup Script
REM Usage:
REM   run.bat              - Start client (default)
REM   run.bat client       - Start desktop client
REM   run.bat relay        - Start relay server
REM   run.bat tracker      - Start tracker server
REM   run.bat all          - Start all services

setlocal enabledelayedexpansion

if "%~1"=="" goto start_client
if /i "%~1"=="client" goto start_client
if /i "%~1"=="relay" goto start_relay
if /i "%~1"=="tracker" goto start_tracker
if /i "%~1"=="all" goto start_all

echo Unknown command: %1
echo Usage: run.bat [client^|relay^|tracker^|all]
goto :eof

:start_client
echo.
echo ========================================
echo   LivingTree AI Agent - Desktop Client
echo ========================================
echo.
python main.py client
goto :eof

:start_relay
echo.
echo ========================================
echo   LivingTree AI Agent - Relay Server
echo ========================================
echo.
python main.py relay
goto :eof

:start_tracker
echo.
echo ========================================
echo   LivingTree AI Agent - Tracker Server
echo ========================================
echo.
python main.py tracker
goto :eof

:start_all
echo.
echo ========================================
echo   LivingTree AI Agent - Starting All
echo ========================================
echo.
echo Starting Relay Server...
start "Relay Server" cmd /k "python main.py relay"
timeout /t 2 /nobreak > nul

echo Starting Tracker Server...
start "Tracker Server" cmd /k "python main.py tracker"
timeout /t 2 /nobreak > nul

echo Starting Desktop Client...
python main.py client
goto :eof
