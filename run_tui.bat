@echo off
cd /d "%~dp0"
set PYTHONPATH=

set PYTHON_CMD=
for %%v in (313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe
    )
)
if "%PYTHON_CMD%"=="" where python >nul 2>&1 && set PYTHON_CMD=python
if "%PYTHON_CMD%"=="" (echo Python not found & pause & exit /b 1)

"%PYTHON_CMD%" -m livingtree tui
pause
