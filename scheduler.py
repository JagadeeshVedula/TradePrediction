import time
import datetime
import os
import subprocess
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


def is_market_day() -> bool:
    """Check if today is a weekday (Monday-Friday)."""
    return datetime.datetime.now().weekday() < 5

def run_job(mode: str):
    """Execute main.py command mode."""
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    cmd = [sys.executable, "main.py", "--mode", mode, "--date", date_str]
    print(f"\n⏰ [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Triggering scheduled job: {' '.join(cmd)}")
    subprocess.run(cmd)

def start_scheduler():
    """Daily scheduler loop monitoring market hours."""
    print("⏰ Indian Stock Trading AI Scheduler Started...")
    print("  • Scheduled Morning Prediction Run: 09:15 AM IST (NSE/BSE Open)")
    print("  • Scheduled Evening Report & Retraining Run: 04:30 PM IST (Post-Close)")
    print("Press Ctrl+C to exit.\n")

    morning_executed_today = False
    evening_executed_today = False
    current_day = datetime.date.today()

    while True:
        now = datetime.datetime.now()
        today = now.date()

        # Reset daily trigger flags at midnight
        if today != current_day:
            current_day = today
            morning_executed_today = False
            evening_executed_today = False

        if is_market_day():
            # Morning trigger around 09:15 AM
            if now.hour == 9 and now.minute >= 15 and not morning_executed_today:
                print("🌅 Market Open Time Reached! Running Morning Analysis...")
                run_job("morning")
                morning_executed_today = True

            # Evening trigger around 16:30 PM (4:30 PM)
            if now.hour == 16 and now.minute >= 30 and not evening_executed_today:
                print("🌆 Market Close Time Reached! Running Evening Report & Continuous Retraining...")
                run_job("evening")
                evening_executed_today = True

        time.sleep(30)

if __name__ == "__main__":
    start_scheduler()
