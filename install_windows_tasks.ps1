# Windows Task Scheduler Setup for Automated Stock Trading AI Predictor
$WorkDir = "c:\Users\Jagadeesh\Documents\stock trading"
$PythonPath = (Get-Command python).Source

# Define robust task settings (run on battery, catch up if missed)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Task 1: Morning Prediction at 09:15 AM Mon-Fri
$MorningAction = New-ScheduledTaskAction -Execute $PythonPath -Argument "main.py --mode morning --send-telegram" -WorkingDirectory $WorkDir
$MorningTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 09:15AM
Register-ScheduledTask -TaskName "StockAI_MorningPrediction" -Action $MorningAction -Trigger $MorningTrigger -Settings $Settings -Description "Runs Morning Top 5 Tech Stock Gainers Prediction" -Force

# Task 2: Evening Close Analysis & Retraining at 04:30 PM Mon-Fri
$EveningAction = New-ScheduledTaskAction -Execute $PythonPath -Argument "main.py --mode evening" -WorkingDirectory $WorkDir
$EveningTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 04:30PM
Register-ScheduledTask -TaskName "StockAI_EveningRetraining" -Action $EveningAction -Trigger $EveningTrigger -Settings $Settings -Description "Runs Evening Close Analysis, ML Retraining & Telegram Report" -Force

Write-Host "✅ Successfully registered Windows Tasks with battery & catch-up settings enabled:" -ForegroundColor Green
Write-Host "   1. StockAI_MorningPrediction (Daily at 09:15 AM Mon-Fri)" -ForegroundColor Yellow
Write-Host "   2. StockAI_EveningRetraining (Daily at 04:30 PM Mon-Fri)" -ForegroundColor Yellow
