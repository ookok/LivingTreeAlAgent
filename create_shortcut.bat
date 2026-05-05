@echo off
cd /d "%~dp0"
echo Creating desktop shortcut...

powershell -Command "
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\LivingTree.lnk')
$Shortcut.TargetPath = '%~dp0run.bat'
$Shortcut.WorkingDirectory = '%~dp0'
$Shortcut.IconLocation = '%SystemRoot%\System32\imageres.dll,65'
$Shortcut.Save()
"
echo Desktop shortcut created: LivingTree
pause
