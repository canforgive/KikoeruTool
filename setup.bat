@echo off
title Prekikoeru Setup
echo ========================================
echo Prekikoeru Setup Wizard
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found!
    echo Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

echo.
echo [1/4] Creating directories...
if not exist "test_data\input" mkdir test_data\input
if not exist "test_data\library" mkdir test_data\library
if not exist "test_data\temp" mkdir test_data\temp
if not exist "data" mkdir data
echo [OK] Directories created

echo.
echo [2/4] Installing backend dependencies...
cd backend
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Backend install failed
    pause
    exit /b 1
)
cd ..
echo [OK] Backend installed

echo.
echo [3/4] Installing frontend dependencies...
cd frontend
if not exist "node_modules" (
    echo Installing npm packages...
    npm install
    if errorlevel 1 (
        echo [ERROR] Frontend install failed
        pause
        exit /b 1
    )
)
cd ..
echo [OK] Frontend installed

echo.
echo [4/4] Checking configuration...
echo [OK] Configuration checked

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo To start:
echo   1. Double-click start-all.bat (Recommended)
echo   2. Or use backend\start.bat + frontend\start.bat
echo.
echo Access:
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
pause
