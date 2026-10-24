@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title UPI Fraud Detection - Verification Suite & Smoke Test
echo ==============================================================================
echo   UPI FRAUD DETECTION SYSTEM - AUTOMATED VERIFICATION SUITE
echo ==============================================================================
echo.

python verify_project.py

echo.
echo ==============================================================================
echo   TEST COMPLETE - Take screenshot now (Press any key to close window)
echo ==============================================================================
pause >nul
