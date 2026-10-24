@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title UPI Fraud Detection - Deep Learning Model Benchmark & Accuracy Test
echo ==============================================================================
echo   UPI FRAUD DETECTION SYSTEM - DEEP LEARNING MODEL ACCURACY TEST
echo ==============================================================================
echo.

python model_accuracy_test.py

echo.
echo ==============================================================================
echo   TEST COMPLETE - Take screenshot now (Press any key to close window)
echo ==============================================================================
pause >nul
