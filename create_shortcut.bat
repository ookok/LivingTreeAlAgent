@echo off
cd /d "%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\LivingTree.lnk"

:: Delete old shortcut if exists
if exist "%SHORTCUT%" del "%SHORTCUT%"

:: Create VBScript to make shortcut
echo Set WshShell = WScript.CreateObject("WScript.Shell") > "%TEMP%\mkshortcut.vbs"
echo Set Shortcut = WshShell.CreateShortcut("%SHORTCUT%") >> "%TEMP%\mkshortcut.vbs"
echo Shortcut.TargetPath = "%~dp0run.bat" >> "%TEMP%\mkshortcut.vbs"
echo Shortcut.WorkingDirectory = "%~dp0" >> "%TEMP%\mkshortcut.vbs"
echo Shortcut.WindowStyle = 7 >> "%TEMP%\mkshortcut.vbs"
echo Shortcut.Save >> "%TEMP%\mkshortcut.vbs"

cscript //nologo "%TEMP%\mkshortcut.vbs"
del "%TEMP%\mkshortcut.vbs"

if exist "%SHORTCUT%" (
    echo Desktop shortcut created: LivingTree
) else (
    echo Failed. Right-click run.bat ^> Send to ^> Desktop.
)
pause
