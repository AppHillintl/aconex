@echo off
title Deploy Staging to Production (Port 8000)
echo ========================================================
echo   PROMOTING STAGING (8001) TO PRODUCTION (8000)
echo ========================================================
cd /d "%~dp0"

echo [1/3] Syncing platform_staging to platform...
xcopy /E /I /Y /Q platform_staging\backend platform\backend
xcopy /E /I /Y /Q platform_staging\etl platform\etl
xcopy /E /I /Y /Q platform_staging\extractor platform\extractor

echo [2/3] Gracefully restarting Production Server on Port 8000...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

echo [3/3] Starting updated Production Server...
start "ACONEX PMC Live Server - Port 8000" "C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" platform\backend\main.py

timeout /t 2 >nul
echo ========================================================
echo SUCCESS: Production is updated and live at:
echo Local:   http://localhost:8000
echo Network: http://172.31.99.41:8000
echo ========================================================
pause
