@echo off
title MathPlatform - Restart
color 0A
REM MathPlatform - double-click to restart backend + frontend
REM (stops them, then starts them again and opens Chrome).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart.ps1" -OpenChrome
pause
