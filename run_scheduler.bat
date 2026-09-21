@echo off
title Top 5 Tech Stock Gainers Predictor & Scheduler
cd /d "c:\Users\Jagadeesh\Documents\stock trading"
echo =======================================================
echo 🚀 Stock Trading AI Predictor & Continuous Retrainer
echo =======================================================
echo.
echo Running automated daily scheduler...
echo   • Morning Prediction: 09:15 AM (Weekdays)
echo   • Evening Retraining: 04:30 PM (Weekdays)
echo.
python scheduler.py
pause
