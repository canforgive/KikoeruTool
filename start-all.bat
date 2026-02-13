@echo off
title Prekikoeru Launcher
echo ========================================
echo Prekikoeru All-in-One Launcher
echo ========================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
    echo [ERROR] Backend not installed!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [ERROR] Frontend not installed!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Starting all services...
echo.

start "Prekikoeru Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m app.main"

timeout /t 3 /nobreak >nul

start "Prekikoeru Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo ========================================
echo Services started!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Docs:     http://localhost:8000/docs
echo.
echo Close the popup windows to stop services
echo.
pause
