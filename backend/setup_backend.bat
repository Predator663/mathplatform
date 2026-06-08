@echo off
REM ─────────────────────────────────────────────────────────────────
REM  MathPlatform — Backend Setup & Run (Windows)
REM  Usage: setup_backend.bat
REM ─────────────────────────────────────────────────────────────────

cd /d "%~dp0"

echo ══════════════════════════════════════════
echo   MathPlatform — Backend Setup (Windows)
echo ══════════════════════════════════════════

REM Check Python
python --version 2>NUL
IF ERRORLEVEL 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment
IF NOT EXIST "venv\" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo Installing Python dependencies...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo   OK: Dependencies installed

REM Migrate
echo.
echo Running database migrations...
python manage.py migrate --run-syncdb
echo   OK: Migrations done (SQLite: db.sqlite3)

REM Seed
echo.
echo Seeding demo data...
python manage.py seed_demo
echo   OK: Demo data ready

REM Run
echo.
echo ══════════════════════════════════════════
echo   API   → http://localhost:8000/api/
echo   Admin → http://localhost:8000/admin/
echo ══════════════════════════════════════════
echo.
python manage.py runserver
