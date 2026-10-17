@echo off
title ACONEX PMC Control Hub - Ras El Hekma
echo ========================================================
echo   Starting ACONEX PMC Control Hub - Ras El Hekma
echo   Port: 8000
echo ========================================================
cd /d "%~dp0"
"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" platform\backend\main.py
pause
