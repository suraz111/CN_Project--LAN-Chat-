@echo off
title Simple LAN Chat - 100% Offline Hotspot & LAN Mode
cd /d "%~dp0"

echo ======================================================================
echo           SIMPLE LAN CHAT - 100%% OFFLINE / ZERO-INTERNET MODE
echo ======================================================================
echo.
echo   [SOLUTION A: MOBILE HOTSPOT SETUP]
echo   1. Turn ON Personal / Wi-Fi Hotspot on any phone.
echo      (Mobile cellular data and internet can be completely turned OFF!)
echo   2. Connect this PC/laptop and other phones to that Wi-Fi hotspot.
echo   3. All devices are now connected over a high-speed local 802.11 LAN!
echo.
echo ======================================================================

:: Resolve local hotspot / Wi-Fi IP address
for /f "tokens=*" %%i in ('python -c "from src.utils.net_utils import get_local_ip; print(get_local_ip())"') do set LOCAL_IP=%%i

if "%LOCAL_IP%"=="" set LOCAL_IP=127.0.0.1

echo.
echo   [HOST READY]
echo   - Local PC access:      http://localhost:8080
echo   - Mobile / Peer access: http://%LOCAL_IP%:8080
echo.
echo   Opening browser on this PC...
echo   Keep this terminal window open while chatting!
echo.
echo ======================================================================
echo.

:: Launch browser to local web portal after a 1 second delay
start "" http://localhost:8080

:: Start headless web gateway & network discovery engine
python web_main.py --port 8080

pause
