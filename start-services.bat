@echo off
echo Starting CodeTrace AI Services...

echo.
echo Starting Backend (FastAPI)...
start "CodeTrace Backend" cmd /k "cd /d %~dp0backend && python main.py"

echo.
echo Waiting for backend to start...
timeout /t 3 /nobreak > nul

echo.
echo Starting Frontend (React + Vite)...
start "CodeTrace Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Services are starting...
echo Backend: http://localhost:8009
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8009/docs
echo.
echo Press any key to exit this window (services will continue running)...
pause > nul
