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
from intraday_tracker import run_intraday_1m_tracker

def parse_args():
    parser = argparse.ArgumentParser(description="Top 5 Indian Stocks (< ₹500) Gain Predictor & Intraday 1m Tracker System")
    parser.add_argument(
        "--mode",
        choices=["morning", "evening", "monitor", "train-initial", "test-telegram", "get-chats", "full-cycle", "full_cycle", "full_pipeline", "telegram-bot", "news"],
        default="morning",
        help="Operation mode: 'morning', 'evening', 'monitor', 'telegram-bot', 'news', 'train-initial', 'test-telegram', 'get-chats', or 'full-cycle' ('full_pipeline')"
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

from typing import Optional

def run_morning_mode(date_str: str, send_telegram: bool = False, target_chat_id: Optional[str] = None):
    print(f"🌅 Running Morning Analysis for Top Indian Stocks under ₹500 ({date_str})...")
    init_db()
    predictor = TechStockPredictor()
    
    top_5 = predictor.predict_top_5_gainers(DEFAULT_TECH_TICKERS)
    if not top_5:
        print("❌ Could not generate predictions. Check internet connection or stock tickers.")
        return

    # Save to database
    save_predictions(date_str, top_5)
    print(f"💾 Top 5 predictions (< ₹500) saved to database for date {date_str}.")

    # Generate Morning Report with Global Cues and Gemini Insights
    report = generate_morning_report_markdown(
        date_str,
        top_5,
        market_context=getattr(predictor, 'last_market_context', None)
    )
    print("\n" + report + "\n")

    if send_telegram:
        print("📤 Sending Morning Report to Telegram Channel...")
        send_telegram_message(report, target_chat_id=target_chat_id)
    return report

def run_evening_mode(date_str: str, send_telegram: bool = True, target_chat_id: Optional[str] = None):
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
        send_telegram_message(report, target_chat_id=target_chat_id)
    return report

def run_full_cycle_mode(date_str: str, send_telegram: bool = True, target_chat_id: Optional[str] = None):
    """
    Execute complete end-to-end trading pipeline cycle:
    1. Morning Prediction (Gemini AI + Global Cues) -> Telegram
    2. 1-Minute Live Intraday Tracker (active during market hours until 15:30 IST)
    3. Evening Post-Market Close P&L Breakdown & Continuous ML Retraining -> Telegram
    """
    from zoneinfo import ZoneInfo
    print(f"🔄 Executing Full Pipeline Cycle for {date_str}...")
    
    # Phase 1: Morning Prediction
    print("🌅 Phase 1: Generating Morning Predictions (< ₹500 stocks)...")
    run_morning_mode(date_str, send_telegram=send_telegram, target_chat_id=target_chat_id)

    # Phase 2: Intraday 1-Minute Monitoring
    now_ist = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    is_trading_hours = (
        now_ist.weekday() < 5
        and (now_ist.hour > 9 or (now_ist.hour == 9 and now_ist.minute >= 15))
        and (now_ist.hour < 15 or (now_ist.hour == 15 and now_ist.minute <= 30))
    )

    if is_trading_hours:
        print("⏱️ Phase 2: Live 1-Minute Intraday Monitoring until Market Close (15:30 IST)...")
        run_intraday_1m_tracker(date_str=date_str)
    else:
        print("ℹ️ Phase 2: Outside market hours. Running single-pass intraday price sync...")
        run_intraday_1m_tracker(date_str=date_str, single_pass=True)

    # Phase 3: Evening P&L & Retraining
    print("🌆 Phase 3: Generating Evening P&L Report & Retraining ML Model...")
    run_evening_mode(date_str, send_telegram=send_telegram, target_chat_id=target_chat_id)

def main():
    args = parse_args()
    date_str = args.date

    if args.mode == "train-initial":
        run_train_initial()
    elif args.mode == "morning":
        run_morning_mode(date_str, send_telegram=args.send_telegram)
    elif args.mode == "evening":
        run_evening_mode(date_str, send_telegram=True)
    elif args.mode == "monitor":
        run_intraday_1m_tracker(date_str=date_str)
    elif args.mode == "test-telegram":
        print("📲 Testing Telegram Bot connectivity...")
        test_telegram_connection()
    elif args.mode == "get-chats":
        print("🔍 Fetching Telegram Chat & Group IDs...")
        get_telegram_chat_ids()
    elif args.mode == "telegram-bot":
        from telegram_bot import run_telegram_listener
        print("🤖 Launching Standalone Interactive Telegram Bot Listener...")
        run_telegram_listener()
    elif args.mode == "news":
        from market_news import get_market_context_summary
        print("🌐 Fetching Global Market Cues & Pre-Market Financial News...")
        ctx = get_market_context_summary()
        print("\n" + ctx.get("summary_text", ""))
        print("\n📰 Domestic News Headlines:")
        print(ctx.get("formatted_news_text", ""))
    elif args.mode in ["full-cycle", "full_cycle", "full_pipeline"]:
        run_full_cycle_mode(date_str, send_telegram=True)

if __name__ == "__main__":
    main()

