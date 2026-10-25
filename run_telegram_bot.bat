@echo off
title Indian Stock AI Telegram Bot
echo ========================================================
echo Starting Indian Stock AI Interactive Telegram Bot...
echo Commands supported:
echo   - /morning : Run Morning Prediction with Gemini AI (< Rs 500)
echo   - /start_pipeline : Start automated daily trading scheduler
echo   - /stop_pipeline  : Pause/stop automated trading pipeline
echo   - /status : View pipeline state & Gemini connection
echo   - /news : US & Singapore cues + Moneycontrol/TOI headlines
echo   - /evening : Run Evening P&L Report & Retraining
echo ========================================================
python main.py --mode telegram-bot
pause
