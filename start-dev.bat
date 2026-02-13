@echo off
chcp 65001 >nul
title Prekikoeru 开发服务器

echo ========================================
echo    Prekikoeru Local Dev Server
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
echo [OK] Python found

REM Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Node.js found

REM Check 7z
where 7z >nul 2>&1
if errorlevel 1 (
    echo [WARNING] 7-Zip not found. Extraction may not work properly.
) else (
    echo [OK] 7-Zip found
)

REM Create directories
if not exist "test_data\input" mkdir test_data\input
if not exist "test_data\library" mkdir test_data\library
if not exist "test_data\temp" mkdir test_data\temp
if not exist "data" mkdir data
echo [OK] Directories created

echo.
echo [1/4] Setting up Python environment...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies
    pause
    exit /b 1
)
cd ..
echo [OK] Backend ready

echo.
echo [2/4] Checking frontend dependencies...
cd frontend
if not exist "node_modules" (
    echo Installing npm packages...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies
        pause
        exit /b 1
    )
)
cd ..
echo [OK] Frontend ready

echo.
echo [3/4] Starting services...
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo.

REM Start backend in new window
start "Prekikoeru Backend" cmd /k "cd %CD%\backend && call venv\Scripts\activate.bat && python -m app.main"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM Start frontend
cd frontend
npm run dev

echo.
echo Stopping services...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

echo.
echo Services stopped
echo.
pause
