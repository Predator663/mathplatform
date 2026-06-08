@echo off
cd /d "%~dp0"
echo ══════════════════════════════════════════
echo   MathPlatform PWA — Frontend Setup
echo ══════════════════════════════════════════
node --version 2>NUL || (echo Node.js not found. Install from https://nodejs.org && pause && exit /b 1)
echo Installing dependencies...
npm install
echo.
echo ══════════════════════════════════════════
echo   Dev server → http://localhost:5173
echo   For PWA test: npm run build then npm run preview
echo ══════════════════════════════════════════
npm run dev
