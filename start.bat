@echo off
if /I "%~1"=="setup" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
) else if /I "%~1"=="stop" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
)
exit /b %errorlevel%
