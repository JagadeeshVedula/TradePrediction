import time
import datetime
import os
import subprocess
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


from zoneinfo import ZoneInfo

def is_market_day() -> bool:
    """Check if today is a weekday (Monday-Friday) in IST."""
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata")).weekday() < 5

def run_job(mode: str):
    """Execute main.py command mode."""
    ist = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    date_str = now_ist.strftime("%Y-%m-%d")
    cmd = [sys.executable, "main.py", "--mode", mode, "--date", date_str]
    print(f"\n⏰ [{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}] Triggering scheduled job: {' '.join(cmd)}")
    subprocess.run(cmd)

def start_scheduler():
    """Daily scheduler loop monitoring market hours in IST."""
    ist = ZoneInfo("Asia/Kolkata")
    print("⏰ Indian Stock Trading AI Scheduler Started (< ₹500 Universe)...")
    print("  • Scheduled Morning Prediction Run: 09:15 AM IST")
    print("  • Intraday 1-Minute Live Monitoring: 09:15 AM - 03:30 PM IST (Pre-10 AM: +₹10 | Post-10 AM Target: +₹2 / Stop Loss: -₹1)")
    print("  • Scheduled Evening Report & Retraining Run: 04:30 PM IST")
    print("Press Ctrl+C to exit.\n")

    morning_executed_today = False
    evening_executed_today = False
    current_day = datetime.datetime.now(ist).date()

    while True:
        now = datetime.datetime.now(ist)
        today = now.date()

        # Reset daily trigger flags at midnight IST
        if today != current_day:
            current_day = today
            morning_executed_today = False
            evening_executed_today = False

        if is_market_day():
            # Morning trigger around 09:15 AM IST
            if now.hour == 9 and now.minute >= 15 and not morning_executed_today:
                print("🌅 Market Open Time Reached (09:15 AM IST)! Running Morning Analysis (< ₹500 stocks)...")
                run_job("morning")
                morning_executed_today = True

            # Intraday 1-minute monitoring during market hours (09:15 - 15:30 IST)
            if (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and (now.hour < 15 or (now.hour == 15 and now.minute <= 30)):
                if morning_executed_today and not evening_executed_today:
                    print("⏱️ Running 1-minute intraday price check pass...")
                    date_str = today.strftime("%Y-%m-%d")
                    cmd = [sys.executable, "main.py", "--mode", "monitor", "--date", date_str]
                    subprocess.run(cmd)

            # Evening trigger around 16:30 PM IST (4:30 PM)
            if now.hour == 16 and now.minute >= 30 and not evening_executed_today:
                print("🌆 Market Close Time Reached (04:30 PM IST)! Running Evening Report & Continuous Retraining...")
                run_job("evening")
                evening_executed_today = True

        time.sleep(60)

if __name__ == "__main__":
    start_scheduler()

