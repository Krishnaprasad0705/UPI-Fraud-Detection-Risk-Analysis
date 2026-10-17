@echo off
chcp 65001 >nul
set PYTHONUTF8=1
echo 🚀 Starting Fraud Detection API Server...
echo Install requirements first: pip install -r requirements.txt
echo Visit: http://localhost:5000
echo.

call pip install -r requirements.txt
python fraud_detection_api_new.py

pause
