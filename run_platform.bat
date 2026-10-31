@echo off
title ACONEX PMC Control Hub - Ras El Hekma
echo ========================================================
echo   Starting ACONEX PMC Control Hub - Ras El Hekma
echo   Port: 8000
echo ========================================================
cd /d "%~dp0"

echo [1/2] Checking and freeing port 8000 if occupied...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo [2/2] Launching FastApi Server...
echo ========================================================

"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" platform\backend\main.py
pause
