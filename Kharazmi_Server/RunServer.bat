@echo off
title Kharazmi Server - Do Not Close!
color 0A
echo ===================================================
echo      KHARAZMI INSTITUTE SERVER IS STARTING...
echo ===================================================
echo.
echo YOUR SERVER IP ADDRESS:
ipconfig | findstr /i "ipv4"
echo.
echo.

cd /d "%~dp0"

:: اجرای سرور با دستور ساده پایتون
python -m uvicorn main:app --host 0.0.0.0 --port 8000

pause
