import time
import datetime
import sys
from typing import Dict, Any, List

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from zoneinfo import ZoneInfo
from config import INVESTMENT_PER_STOCK, PROFIT_TARGET_INR, STOP_LOSS_INR, PRE_10AM_PROFIT_TARGET_INR
from database import get_predictions_by_date, save_outcomes, get_outcomes_by_date
from data_fetcher import fetch_intraday_1m_data, normalize_ticker, _to_scalar
from telegram_bot import send_telegram_message

def run_intraday_1m_tracker(date_str: str = None, interval_seconds: int = 60, single_pass: bool = False):
    """
    1-Minute Intraday Monitoring Service:
    Polls active morning predictions every 60 seconds during market hours.
    Evaluates +₹1 Profit Target and -₹3 Stop Loss exit conditions (with pre-10 AM +₹10 rule).
    """
    if not date_str:
        date_str = datetime.date.today().strftime("%Y-%m-%d")

    print(f"⏱️ Starting 1-Minute Intraday Stock Tracker for {date_str}...")
    predictions = get_predictions_by_date(date_str)
    if not predictions:
        print(f"⚠️ No morning predictions found for date {date_str}. Please run morning mode first.")
        return

    print(f"📌 Monitoring {len(predictions)} active stocks (Filter: < ₹500 | Allocation: ₹25,000 | Pre-10AM: +₹10 | Post-10AM Target: +₹{PROFIT_TARGET_INR:g} | Stop Loss: -₹{STOP_LOSS_INR:g})")

    active_positions = {}
    for p in predictions:
        ticker = p['ticker']
        entry_price = p['starting_price']
        qty = p.get('quantity') or max(1, int(INVESTMENT_PER_STOCK / entry_price))
        inv_amt = p.get('invested_amount') or round(qty * entry_price, 2)
        
        active_positions[ticker] = {
            'ticker': ticker,
            'entry_price': entry_price,
            'target_price': round(entry_price + PROFIT_TARGET_INR, 2),
            'stop_loss_price': round(entry_price - STOP_LOSS_INR, 2),
            'quantity': qty,
            'invested_amount': inv_amt,
            'status': 'OPEN',
            'high_price': entry_price,
            'low_price': entry_price,
            'exit_price': None,
            'exit_reason': None,
            'exit_time': None
        }

    # Load any pre-existing exits for today (Skip pending states like MARKET_NOT_OPEN_YET or SESSION_PENDING)
    existing_outcomes = get_outcomes_by_date(date_str)
    for o in existing_outcomes:
        ticker = o['ticker']
        reason = o.get('exit_reason') or ''
        if ticker in active_positions and reason and reason not in ['OPEN', 'MARKET_NOT_OPEN_YET', 'SESSION_PENDING']:
            active_positions[ticker]['status'] = 'CLOSED'
            active_positions[ticker]['exit_price'] = o['exit_price']
            active_positions[ticker]['exit_reason'] = o['exit_reason']
            active_positions[ticker]['exit_time'] = o['exit_time']

    while True:
        now_ist = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
        time_str = now_ist.strftime('%H:%M')
        is_before_10am = now_ist.time() < datetime.time(10, 0)
        open_count = sum(1 for pos in active_positions.values() if pos['status'] == 'OPEN')

        print(f"\n🔍 [{now_ist.strftime('%H:%M:%S IST')}] Polling 1-minute ticker prices ({open_count}/5 positions OPEN)...")

        for ticker, pos in list(active_positions.items()):
            if pos['status'] != 'OPEN':
                continue

            df_1m = fetch_intraday_1m_data(ticker)
            if df_1m.empty:
                print(f"  • {ticker}: Waiting for 1m bar data...")
                continue

            last_row = df_1m.iloc[-1]
            curr_price = round(_to_scalar(last_row['Close']), 2)
            bar_high = round(_to_scalar(last_row['High']), 2)
            bar_low = round(_to_scalar(last_row['Low']), 2)

            if bar_high > pos['high_price']:
                pos['high_price'] = bar_high
            if bar_low < pos['low_price']:
                pos['low_price'] = bar_low

            print(f"  • {ticker}: Entry ₹{pos['entry_price']:.2f} | Current ₹{curr_price:.2f} (High ₹{pos['high_price']:.2f} / Low ₹{pos['low_price']:.2f})")

            early_target_price = round(pos['entry_price'] + PRE_10AM_PROFIT_TARGET_INR, 2)

            if is_before_10am:
                # Before 10:00 AM IST: ONLY sell if stock rises by +10 Rupees
                if bar_high >= early_target_price:
                    pos['status'] = 'CLOSED'
                    pos['exit_price'] = early_target_price
                    pos['exit_reason'] = 'EARLY_TARGET_MET (+₹10)'
                    pos['exit_time'] = time_str
                    pnl_share = PRE_10AM_PROFIT_TARGET_INR
                    total_pnl = round(pos['quantity'] * pnl_share, 2)
                    
                    msg = f"🚀 *PRE-10AM EARLY TARGET HIT ALERT!* 🚀\nStock: *{ticker}*\nBought {pos['quantity']} shares @ ₹{pos['entry_price']:.2f}\nSold @ ₹{pos['exit_price']:.2f} (+₹10.00)\nNet Profit: *+₹{total_pnl:,.2f}*"
                    print(f"  🎉 {msg.replace('*', '')}")
                    send_telegram_message(msg)
            else:
                # After 10:00 AM IST: Target or Stop Loss
                # Check Target Hit
                if bar_high >= pos['target_price']:
                    pos['status'] = 'CLOSED'
                    pos['exit_price'] = pos['target_price']
                    pos['exit_reason'] = f'TARGET_MET (+₹{PROFIT_TARGET_INR:g})'
                    pos['exit_time'] = time_str
                    pnl_share = PROFIT_TARGET_INR
                    total_pnl = round(pos['quantity'] * pnl_share, 2)
                    
                    msg = f"🎯 *TARGET HIT ALERT!* 🚀\nStock: *{ticker}*\nBought {pos['quantity']} shares @ ₹{pos['entry_price']:.2f}\nSold @ ₹{pos['exit_price']:.2f} (+₹{PROFIT_TARGET_INR:.2f})\nNet Profit: *+₹{total_pnl:,.2f}*"
                    print(f"  🎉 {msg.replace('*', '')}")
                    send_telegram_message(msg)

                # Check Stop Loss Hit
                elif bar_low <= pos['stop_loss_price']:
                    pos['status'] = 'CLOSED'
                    pos['exit_price'] = pos['stop_loss_price']
                    pos['exit_reason'] = f'STOP_LOSS_HIT (-₹{STOP_LOSS_INR:g})'
                    pos['exit_time'] = time_str
                    pnl_share = -STOP_LOSS_INR
                    total_pnl = round(pos['quantity'] * pnl_share, 2)
                    
                    msg = f"🔴 *STOP LOSS TRIGGERED!* ⚠️\nStock: *{ticker}*\nBought {pos['quantity']} shares @ ₹{pos['entry_price']:.2f}\nSold @ ₹{pos['exit_price']:.2f} (-₹{STOP_LOSS_INR:.2f})\nNet Loss: *₹{total_pnl:,.2f}*"
                    print(f"  ⚠️ {msg.replace('*', '')}")
                    send_telegram_message(msg)

        # Sync active positions status to SQLite outcomes
        outcomes_to_save = []
        for ticker, pos in active_positions.items():
            entry_p = pos['entry_price']
            exit_p = pos['exit_price'] or pos['high_price']
            pnl_share = round(exit_p - entry_p, 2) if pos['exit_price'] else 0.0
            tot_pnl = round(pos['quantity'] * pnl_share, 2)
            pnl_pct = round((tot_pnl / pos['invested_amount']) * 100, 2) if pos['invested_amount'] > 0 else 0.0

            outcomes_to_save.append({
                'ticker': ticker,
                'starting_price': entry_p,
                'close_price': exit_p,
                'high_price': pos['high_price'],
                'low_price': pos['low_price'],
                'exit_price': exit_p,
                'exit_reason': pos['exit_reason'] or 'OPEN',
                'exit_time': pos['exit_time'] or time_str,
                'quantity': pos['quantity'],
                'invested_amount': pos['invested_amount'],
                'pnl_per_share': pnl_share,
                'total_pnl': tot_pnl,
                'pnl_pct': pnl_pct,
                'actual_gain_pct': pnl_pct,
                'max_gain_pct': round(((pos['high_price'] - entry_p) / entry_p) * 100, 2),
                'status': 'TARGET_MET' if 'TARGET' in (pos['exit_reason'] or '') else ('STOP_LOSS' if 'STOP_LOSS' in (pos['exit_reason'] or '') else 'OPEN')
            })

        save_outcomes(date_str, outcomes_to_save)

        if single_pass:
            print("✅ 1-Minute tick pass complete.")
            break

        # Check market close time (15:30 IST)
        if now_ist.hour >= 15 and now_ist.minute >= 30:
            print("🌆 Market Close Time Reached (15:30 IST). Closing 1-minute monitoring daemon.")
            break

        time.sleep(interval_seconds)

if __name__ == "__main__":
    run_intraday_1m_tracker()
