@echo off
title MathPlatform - Status
color 0A
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\status.ps1"
pause
