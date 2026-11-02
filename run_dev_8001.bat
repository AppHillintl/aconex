@echo off
title ACONEX Dev Server (Staging - Port 8001)
echo ========================================================
echo   ACONEX DEVELOPMENT / STAGING SERVER
echo   Port: 8001 (Isolated from Live Production Users)
echo   Source: platform_staging
echo ========================================================
cd /d "%~dp0"

echo [1/2] Checking and freeing port 8001 if occupied...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo [2/2] Launching Staging Server on http://localhost:8001 ...
echo --------------------------------------------------------
echo Live users on port 8000 are completely unaffected!
echo Staging URL: http://localhost:8001
echo ========================================================

"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" platform_staging\backend\main.py 8001
pause
