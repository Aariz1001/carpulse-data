@echo off
REM Vehicle Data Generator - Windows batch runner
REM Usage: run.bat [mode] [options]

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if venv exists, if not create it
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Install dependencies if needed
pip show python-dotenv >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Check for .env file
if not exist ".env" (
    echo.
    echo ========================================
    echo WARNING: .env file not found!
    echo ========================================
    echo.
    echo Please create a .env file with your OpenRouter API key.
    echo You can copy .env.example and add your key.
    echo.
    pause
    exit /b 1
)

REM Run the generator with any arguments passed
echo.
echo Starting Vehicle Data Generator...
echo.
python generate_vehicles.py %*

echo.
pause
