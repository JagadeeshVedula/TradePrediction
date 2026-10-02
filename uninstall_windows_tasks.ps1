# Windows Task Scheduler Removal Script for Automated Stock Trading AI Predictor

$Task1 = "StockAI_MorningPrediction"
$Task2 = "StockAI_EveningRetraining"

if (Get-ScheduledTask -TaskName $Task1 -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $Task1 -Confirm:$false
    Write-Host "[REMOVED] Unregistered Windows Task: $Task1" -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Windows Task not found: $Task1" -ForegroundColor Gray
}

if (Get-ScheduledTask -TaskName $Task2 -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $Task2 -Confirm:$false
    Write-Host "[REMOVED] Unregistered Windows Task: $Task2" -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Windows Task not found: $Task2" -ForegroundColor Gray
}

Write-Host "[SUCCESS] Cleaned up all Stock AI Scheduled Tasks from Windows Task Scheduler." -ForegroundColor Green
