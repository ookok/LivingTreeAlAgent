@echo off
chcp 65001 > nul 2>&1
title LivingTree AI Agent
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PY=pythonw.exe"
where /q pythonw.exe 2>nul || set "PY=python.exe"

start "" /B "%PY%" -c "from livingtree.tui.wt_bootstrap import main; main()" %*
exit /b 0
