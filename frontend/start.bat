@echo off
title Prekikoeru Frontend
echo ========================================
echo Prekikoeru Frontend Server
echo ========================================
echo.
echo Starting frontend server...
echo URL: http://localhost:5173
echo.
echo Press Ctrl+C to stop
echo.

if not exist "node_modules" (
    echo [ERROR] Dependencies not found!
    echo Please run setup.bat first to install dependencies.
    pause
    exit /b 1
)

npm run dev

echo.
echo Server stopped
echo.
pause
