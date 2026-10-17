@echo off
echo ===================================================
echo Enabling Port 8000 for LAN Access in Windows Firewall
echo ===================================================
netsh advfirewall firewall add rule name="Aconex PMC Platform Port 8000" dir=in action=allow protocol=TCP localport=8000
echo.
if %errorlevel% equ 0 (
    echo [SUCCESS] Port 8000 is now open! Other devices on the Wi-Fi can connect.
) else (
    echo [ERROR] Please right-click this file and choose 'Run as administrator'.
)
echo.
pause
