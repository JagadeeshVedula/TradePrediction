import argparse
import datetime
import sys

# Ensure UTF-8 output encoding for Windows PowerShell consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from config import DEFAULT_TECH_TICKERS
from database import init_db, save_predictions, save_outcomes

from ml_model import TechStockPredictor
from reporter import generate_morning_report_markdown, generate_evening_report_markdown
from telegram_bot import send_telegram_message, test_telegram_connection, get_telegram_chat_ids

def parse_args():
    parser = argparse.ArgumentParser(description="Top 5 Indian Stocks Gain Predictor & Retraining System")
    parser.add_argument(
        "--mode",
        choices=["morning", "evening", "train-initial", "test-telegram", "get-chats", "full-cycle"],
        default="morning",
        help="Operation mode: 'morning' (predictions), 'evening' (close results & retraining), 'train-initial', 'test-telegram', 'get-chats', or 'full-cycle'"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.date.today().strftime("%Y-%m-%d"),
        help="Target date in YYYY-MM-DD format (default: today)"
    )
    parser.add_argument(
        "--send-telegram",
        action="store_true",
        help="Force sending report to Telegram channel regardless of default mode"
    )
    return parser.parse_args()

def run_train_initial():
    print("🚀 Initializing database and training initial ML model baseline on Indian stocks...")
    init_db()
    predictor = TechStockPredictor()
    mae, samples_count = predictor.train_baseline(DEFAULT_TECH_TICKERS)
    print(f"🎉 Initial model successfully trained on {samples_count} historical samples (MAE: {mae:.4f}).")

def run_morning_mode(date_str: str, send_telegram: bool = False):
    print(f"🌅 Running Morning Analysis for Top Indian Stocks ({date_str})...")
    init_db()
    predictor = TechStockPredictor()
    
    top_5 = predictor.predict_top_5_gainers(DEFAULT_TECH_TICKERS)
    if not top_5:
        print("❌ Could not generate predictions. Check internet connection or stock tickers.")
        return

    # Save to database
    save_predictions(date_str, top_5)
    print(f"💾 Top 5 predictions saved to database for date {date_str}.")

    # Generate Morning Report
    report = generate_morning_report_markdown(date_str, top_5)
    print("\n" + report + "\n")

    if send_telegram:
        print("📤 Sending Morning Report to Telegram Channel...")
        send_telegram_message(report)

def run_evening_mode(date_str: str, send_telegram: bool = True):
    print(f"🌆 Running Evening Post-Market Close Analysis & ML Retraining for {date_str}...")
    init_db()
    predictor = TechStockPredictor()

    summary = predictor.retrain_evening_feedback_loop(date_str, DEFAULT_TECH_TICKERS)
    if summary.get('status') == 'NO_PREDICTIONS':
        print(f"⚠️ No morning predictions found for {date_str}. Running morning prediction first...")
        run_morning_mode(date_str, send_telegram=False)
        summary = predictor.retrain_evening_feedback_loop(date_str, DEFAULT_TECH_TICKERS)

    # Generate Detailed Evening Report
    report = generate_evening_report_markdown(date_str, summary)
    print("\n" + report + "\n")

    # Send Evening Report to Telegram channel (User explicitly requested detailed evening report to telegram)
    if send_telegram:
        print("📤 Sending Detailed Evening Report to Telegram Channel...")
        send_telegram_message(report)

def main():
    args = parse_args()
    date_str = args.date

    if args.mode == "train-initial":
        run_train_initial()
    elif args.mode == "morning":
        run_morning_mode(date_str, send_telegram=args.send_telegram)
    elif args.mode == "evening":
        run_evening_mode(date_str, send_telegram=True)
    elif args.mode == "test-telegram":
        print("📲 Testing Telegram Bot connectivity...")
        test_telegram_connection()
    elif args.mode == "get-chats":
        print("🔍 Fetching Telegram Chat & Group IDs...")
        get_telegram_chat_ids()
    elif args.mode == "full-cycle":
        print("🔄 Executing Full-Cycle (Morning Analysis + Evening Close Retraining)...")
        run_morning_mode(date_str, send_telegram=False)
        run_evening_mode(date_str, send_telegram=True)

if __name__ == "__main__":
    main()
