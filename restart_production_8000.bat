@echo off
title ACONEX Production Server Restart
echo ========================================================
echo   Restarting ACONEX Live Server (Port 8000)
echo ========================================================
cd /d "%~dp0"

echo [1/2] Stopping existing port 8000 process...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo [2/2] Starting fresh Production Server on Port 8000...
"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" platform\backend\main.py
pause
