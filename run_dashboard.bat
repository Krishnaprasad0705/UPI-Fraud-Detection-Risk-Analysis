@echo off
chcp 65001 >nul
set PYTHONUTF8=1
echo 🚀 Starting UPI Fraud Detection Dashboard...
echo.

REM Install requirements if needed
call pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install requirements.
    pause
    exit /b %errorlevel%
)

REM Start streaming in background (new window)
start "UPI Streaming" cmd /k "python start_streaming.py"

timeout /t 3 /nobreak >nul

REM Start API server
echo Starting API server on http://localhost:5000...
python fraud_detection_api_new.py

pause
