@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title LivingTree Relay — Win2008 Deployment
echo ================================================
echo  LivingTree Relay Server — Win2008 Deploy
echo ================================================
echo.

set TARGET=%1
if "%TARGET%"=="" (
    echo Usage: deploy_win2008.bat ^<target_ip_or_path^>
    echo   deploy_win2008.bat 192.168.1.100
    echo   deploy_win2008.bat C:\LivingTree
    echo.
    echo This script deploys relay_server.exe to Windows Server 2008.
    echo Python installation NOT required on target.
    echo.
    exit /b 1
)

:: Check if exe was built
if not exist "dist\relay_server.exe" (
    echo [ERROR] dist\relay_server.exe not found.
    echo Run build_relay_exe.py first:
    echo   .venv\Scripts\python.exe build_relay_exe.py
    exit /b 1
)

echo [1/4] Creating deployment package...
set PKG=dist\relay_package
if exist "%PKG%" rmdir /s /q "%PKG%"
mkdir "%PKG%"
mkdir "%PKG%\config" 2>nul
mkdir "%PKG%\.livingtree" 2>nul
mkdir "%PKG%\logs" 2>nul

:: Copy main exe
copy /y dist\relay_server.exe "%PKG%\" >nul

:: Copy config
if exist config\secrets.enc copy /y config\secrets.enc "%PKG%\config\" >nul

:: Copy CRT DLLs for Win2008 (if present)
if exist "C:\Windows\System32\vcruntime140.dll" copy /y "C:\Windows\System32\vcruntime140.dll" "%PKG%\" >nul
if exist "C:\Windows\System32\ucrtbase.dll" copy /y "C:\Windows\System32\ucrtbase.dll" "%PKG%\" >nul
if exist "C:\Windows\System32\msvcp140.dll" copy /y "C:\Windows\System32\msvcp140.dll" "%PKG%\" >nul

:: Create launcher
(
echo @echo off
echo title LivingTree Relay Server
echo echo Starting LivingTree Relay Server...
echo echo Port: 8888
echo echo.
echo :: Check for CRT DLLs
echo if exist "vcruntime140.dll" echo [OK] vcruntime140.dll bundled
echo if exist "ucrtbase.dll" echo [OK] ucrtbase.dll bundled
echo if exist "msvcp140.dll" echo [OK] msvcp140.dll bundled
echo echo.
echo relay_server.exe
echo set RC=%%ERRORLEVEL%%
echo if %%RC%% NEQ 0 (
echo     echo.
echo     echo [ERROR] Relay server failed with exit code %%RC%%
echo     echo.
echo     echo TROUBLESHOOTING for Windows Server 2008:
echo     echo 1. Install VC++ 2015-2022 Redistributable:
echo     echo    https://aka.ms/vs/17/release/vc_redist.x64.exe
echo     echo 2. If that doesn't help, try bundled DLLs:
echo     echo    Copy vcruntime140.dll and ucrtbase.dll next to relay_server.exe
echo     echo.
echo     pause
echo ^)
) > "%PKG%\start_relay.bat"

:: Create install CRT script
(
echo @echo off
echo echo Installing VC++ Redistributables for Windows Server 2008...
echo echo.
echo :: Download and install VC++ 2022 redist
echo bitsadmin /transfer "VC_Redist" "https://aka.ms/vs/17/release/vc_redist.x64.exe" "%%TEMP%%\vc_redist.x64.exe"
echo if exist "%%TEMP%%\vc_redist.x64.exe" ^(
echo     echo Installing...
echo     "%%TEMP%%\vc_redist.x64.exe" /quiet /norestart
echo     del "%%TEMP%%\vc_redist.x64.exe"
echo     echo Done.
echo ^) else ^(
echo     echo Download failed. Install manually from:
echo     echo https://aka.ms/vs/17/release/vc_redist.x64.exe
echo ^)
echo pause
) > "%PKG%\install_crt.bat"

echo [2/4] Package ready: %PKG%\
dir /s "%PKG%"

:: Check firewall
echo.
echo [3/4] Windows Firewall — remember to open port 8888:
echo   netsh advfirewall firewall add rule name="Relay8888" dir=in action=allow protocol=TCP localport=8888

:: Deploy
echo.
echo [4/4] Deploying...

:: Check if target is a remote path (UNC or IP)
echo !TARGET! | find "\\" >nul
if !ERRORLEVEL! EQU 0 goto :copy_remote

echo !TARGET! | find "." >nul
if !ERRORLEVEL! EQU 0 goto :copy_ip

:: Local path
echo Copying to !TARGET! ...
xcopy /e /i /h /y "%PKG%\*" "!TARGET!\"
echo Done. Run: !TARGET!\start_relay.bat
goto :end

:copy_remote
echo Copying to remote path !TARGET! ...
xcopy /e /i /h /y "%PKG%\*" "!TARGET!\"
echo Done.
goto :end

:copy_ip
echo Copying to \\!TARGET!\C$\LivingTree\ ...
net use \\!TARGET!\IPC$ /user:Administrator *
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Cannot connect to !TARGET!
    echo Try: net use \\!TARGET!\C$ /user:Administrator password
    echo Or copy manually: xcopy dist\relay_package\* \\!TARGET!\C$\LivingTree\
    goto :end
)
xcopy /e /i /h /y "%PKG%\*" "\\!TARGET!\C$\LivingTree\"
echo Done.
echo Run on !TARGET!: C:\LivingTree\start_relay.bat

:end
echo.
echo ================================================
echo  To start the relay on the target server:
echo    1. Run: install_crt.bat  (first-time only)
echo    2. Run: start_relay.bat
echo    3. Open: http://!TARGET!:8888/admin
echo ================================================
