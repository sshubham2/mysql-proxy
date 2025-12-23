@echo off
REM ChronosProxy Startup Script (Windows)

echo ======================================
echo ChronosProxy Startup Script
echo ======================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Virtual environment not found. Creating...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment
        exit /b 1
    )
    echo Virtual environment created
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import mysql_mimic" 2>nul
if %errorlevel% neq 0 (
    echo Dependencies not installed. Installing...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Failed to install dependencies
        exit /b 1
    )
    echo Dependencies installed
)

REM Check if .env exists
if not exist ".env" (
    echo Warning: .env file not found
    echo Copying .env.example to .env
    copy .env.example .env
    echo Please edit .env and set MYSQL_PASSWORD before continuing
    exit /b 1
)

REM Start ChronosProxy
echo Starting ChronosProxy...
echo.
python src\main.py %*
