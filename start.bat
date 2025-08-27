@echo off
REM CodeTrace AI - Quick Start Batch Script
REM This is a simple batch wrapper for the PowerShell scripts

echo ======================================
echo  CodeTrace AI - Quick Start
echo ======================================

REM Check if PowerShell is available
powershell -Command "if ($PSVersionTable.PSVersion.Major -ge 5) { exit 0 } else { exit 1 }"
if %errorlevel% neq 0 (
    echo ERROR: PowerShell 5.0 or higher required
    echo Please install PowerShell and try again
    pause
    exit /b 1
)

REM Set execution policy temporarily
powershell -Command "Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force"

REM Check what action to take
if "%1"=="setup" (
    echo Starting environment setup...
    powershell -File "%~dp0setup-environment.ps1"
) else if "%1"=="stop" (
    echo Stopping services...
    powershell -File "%~dp0stop-services.ps1"
) else if "%1"=="status" (
    echo Checking status...
    powershell -File "%~dp0status.ps1"
) else (
    echo Starting services...
    powershell -File "%~dp0start-services.ps1"
)

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Operation failed
    pause
    exit /b 1
)

echo.
echo SUCCESS: Operation completed
if "%1"=="" (
    echo.
    echo Services should now be running at:
    echo   Frontend: http://localhost:3000
    echo   Backend:  http://localhost:8009
    echo.
    echo Press any key to exit...
    pause >nul
)
