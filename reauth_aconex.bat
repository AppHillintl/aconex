@echo off
title Aconex - Interactive 2FA Re-Authentication
cd /d "C:\Users\bimst\Downloads\ACONEX"
echo =====================================================================
echo  ACONEX INTERACTIVE 2FA SESSION RE-AUTHENTICATION
echo =====================================================================
echo Launching visible Chrome browser...
"C:\Users\bimst\AppData\Local\Programs\Python\Python314\python.exe" "scripts\reauth_aconex.py"
echo.
pause
