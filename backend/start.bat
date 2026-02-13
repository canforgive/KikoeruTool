@echo off
title Prekikoeru Backend
echo ========================================
echo Prekikoeru Backend Server
echo ========================================
echo.
echo Starting backend server...
echo URL: http://localhost:8000
echo Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.bat first to install dependencies.
    pause
    exit /b 1
)

venv\Scripts\python.exe -m app.main

echo.
echo Server stopped
echo.
pause
