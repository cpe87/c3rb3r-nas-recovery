@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 goto failed
echo Setup completed. Run start.cmd.
pause
exit /b 0
:failed
echo Setup failed. See the message above.
pause
exit /b 1
