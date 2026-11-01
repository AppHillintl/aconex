@echo off
title ACONEX PMC Control Platform - Ras El Hekma
echo ===============================================================================
echo                ACONEX PMC PROJECT CONTROLS PLATFORM
echo                        Ras El Hekma Project
echo ===============================================================================
echo.
echo Starting FastAPI & DuckDB Engine on port 8000...
echo Access the Dashboard at: http://localhost:8000
echo.

cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe"
if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" backend\main.py
) else (
    python backend\main.py
)

pause
