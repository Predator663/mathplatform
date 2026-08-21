@echo off
title MathPlatform - Launcher
color 0A
REM MathPlatform - double-click to start backend + frontend in the
REM background and open Chrome. Safe to run even if already running.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -OpenChrome
pause
