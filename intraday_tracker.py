import time
import datetime
import sys
from typing import Dict, Any, List

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from zoneinfo import ZoneInfo
from config import (
    INVESTMENT_PER_STOCK, PROFIT_TARGET_INR, STOP_LOSS_INR, PRE_10AM_PROFIT_TARGET_INR,
    TRAILING_SL_PUSH_INR, TRAILING_SL_STEP_INR
)
from database import get_predictions_by_date, save_outcomes, get_outcomes_by_date
from data_fetcher import fetch_intraday_1m_data, normalize_ticker, _to_scalar
from telegram_bot import send_telegram_message

def run_intraday_1m_tracker(date_str: str = None, interval_seconds: int = 60, single_pass: bool = False):
    """
    1-Minute Intraday Monitoring Service:
    Polls active morning predictions every 60 seconds during market hours.
    Evaluates:
    - Pre-10:00 AM IST: Early target exit at +₹10.00
    - Post-10:00 AM IST:
      * When stock reaches target amount (+₹2, e.g. 400 -> 402):
        Stop loss is pushed to +2 (from 399 -> 401, locking in profit).
      * For every +₹1 increase in stock price (e.g. 403, 404):
        Stop loss increases by 1 (e.g. 402, 403).
      * If price hits trailing stop loss: Exits to lock in maximum profit.
      * If stock does not reach target: Initial stop loss (-₹1, e.g. 399) triggers.
    """
    if not date_str:
        date_str = datetime.date.today().strftime("%Y-%m-%d")

    print(f"⏱️ Starting 1-Minute Intraday Stock Tracker for {date_str}...")
    predictions = get_predictions_by_date(date_str)
    if not predictions:
        print(f"⚠️ No morning predictions found for date {date_str}. Please run morning mode first.")
        return

    print(f"📌 Monitoring {len(predictions)} active stocks (Filter: < ₹500 | Allocation: ₹25,000 | Pre-10AM: +₹10 | Post-10AM Target: +₹{PROFIT_TARGET_INR:g} with +₹1 Trailing SL | Initial SL: -₹{STOP_LOSS_INR:g})")

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
            'initial_stop_loss': round(entry_price - STOP_LOSS_INR, 2),
            'target_hit': False,
            'quantity': qty,
            'invested_amount': inv_amt,
            'status': 'OPEN',
            'high_price': entry_price,
            'low_price': entry_price,
            'current_price': entry_price,
            'exit_price': None,
            'exit_reason': None,
            'exit_time': None
        }

    # Load any pre-existing exits for today (Skip pending states like MARKET_NOT_OPEN_YET or SESSION_PENDING)
    existing_outcomes = get_outcomes_by_date(date_str)
    for o in existing_outcomes:
        ticker = o['ticker']
        reason = o.get('exit_reason') or ''
        if ticker in active_positions:
            if reason and reason not in ['OPEN', 'MARKET_NOT_OPEN_YET', 'SESSION_PENDING']:
                active_positions[ticker]['status'] = 'CLOSED'
                active_positions[ticker]['exit_price'] = o['exit_price']
                active_positions[ticker]['exit_reason'] = o['exit_reason']
                active_positions[ticker]['exit_time'] = o['exit_time']
                active_positions[ticker]['high_price'] = max(active_positions[ticker]['high_price'], o.get('high_price', active_positions[ticker]['entry_price']))
                active_positions[ticker]['low_price'] = min(active_positions[ticker]['low_price'], o.get('low_price', active_positions[ticker]['entry_price']))
            else:
                # If still open, restore high_price and trailing stop loss
                high_seen = o.get('high_price', active_positions[ticker]['entry_price'])
                if high_seen > active_positions[ticker]['high_price']:
                    active_positions[ticker]['high_price'] = high_seen
                if active_positions[ticker]['high_price'] >= active_positions[ticker]['target_price']:
                    active_positions[ticker]['target_hit'] = True
                    steps = int(max(0.0, active_positions[ticker]['high_price'] - active_positions[ticker]['target_price']))
                    new_sl = round(active_positions[ticker]['initial_stop_loss'] + TRAILING_SL_PUSH_INR + steps * TRAILING_SL_STEP_INR, 2)
                    active_positions[ticker]['stop_loss_price'] = max(active_positions[ticker]['stop_loss_price'], new_sl)

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

            pos['current_price'] = curr_price
            if bar_high > pos['high_price']:
                pos['high_price'] = bar_high
            if bar_low < pos['low_price']:
                pos['low_price'] = bar_low

            target_status = "🎯 TARGET HIT (TRAILING)" if pos['target_hit'] else f"Target ₹{pos['target_price']:.2f}"
            print(f"  • {ticker}: Entry ₹{pos['entry_price']:.2f} | Current ₹{curr_price:.2f} (High ₹{pos['high_price']:.2f} / Low ₹{pos['low_price']:.2f}) | SL ₹{pos['stop_loss_price']:.2f} | {target_status}")

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
                # After 10:00 AM IST: Trailing Stop Loss Strategy
                # 1. Check if Target amount reached (e.g., 402 for 400 entry)
                first_target_hit = False
                if bar_high >= pos['target_price'] or pos['target_hit']:
                    if not pos['target_hit']:
                        pos['target_hit'] = True
                        first_target_hit = True

                    # Target reached: stop loss is pushed to +2 (from 399 -> 401)
                    # and after that for every +1 increase, stop loss increases by 1 (e.g. 403 -> 402)
                    points_above_target = max(0.0, pos['high_price'] - pos['target_price'])
                    trailing_steps = int(points_above_target)
                    new_stop_loss = round(pos['initial_stop_loss'] + TRAILING_SL_PUSH_INR + trailing_steps * TRAILING_SL_STEP_INR, 2)

                    if new_stop_loss > pos['stop_loss_price']:
                        old_sl = pos['stop_loss_price']
                        pos['stop_loss_price'] = new_stop_loss

                        if first_target_hit:
                            msg = (
                                f"🎯 *TARGET REACHED! TRAILING STOP ACTIVATED!* 🚀\n"
                                f"Stock: *{ticker}*\n"
                                f"Bought {pos['quantity']} shares @ ₹{pos['entry_price']:.2f}\n"
                                f"Target ₹{pos['target_price']:.2f} reached! (High: ₹{pos['high_price']:.2f})\n"
                                f"🛡️ Stop Loss pushed to: *₹{pos['stop_loss_price']:.2f}* (+₹{TRAILING_SL_PUSH_INR:.2f} to lock in profit)\n"
                                f"Rule: Trailing +₹1 stop loss for every +₹1 increase in price."
                            )
                            print(f"  🎉 {msg.replace('*', '')}")
                            send_telegram_message(msg)
                        else:
                            msg = (
                                f"📈 *TRAILING STOP LOSS RAISED!* 🛡️\n"
                                f"Stock: *{ticker}*\n"
                                f"New High: ₹{pos['high_price']:.2f}\n"
                                f"Stop Loss moved from ₹{old_sl:.2f} ➔ *₹{pos['stop_loss_price']:.2f}* (+₹{pos['stop_loss_price'] - pos['entry_price']:.2f}/share locked profit) 💰"
                            )
                            print(f"  📈 {msg.replace('*', '')}")
                            send_telegram_message(msg)

                # 2. Check Stop Loss Hit
                sl_triggered = False
                if pos['target_hit']:
                    # Trailing stop loss check (exits when current price or bar low drops to/below stop loss)
                    if first_target_hit:
                        if curr_price <= pos['stop_loss_price']:
                            sl_triggered = True
                    else:
                        if curr_price <= pos['stop_loss_price'] or bar_low <= pos['stop_loss_price']:
                            sl_triggered = True

                    if sl_triggered:
                        pos['status'] = 'CLOSED'
                        pos['exit_price'] = pos['stop_loss_price']
                        pnl_share = round(pos['exit_price'] - pos['entry_price'], 2)
                        pos['exit_reason'] = f'TARGET_MET_TRAILING_STOP (+₹{pnl_share:g})'
                        pos['exit_time'] = time_str
                        total_pnl = round(pos['quantity'] * pnl_share, 2)

                        msg = (
                            f"🎯 *TRAILING STOP LOSS HIT! (PROFIT LOCKED)* 💰\n"
                            f"Stock: *{ticker}*\n"
                            f"Bought {pos['quantity']} shares @ ₹{pos['entry_price']:.2f}\n"
                            f"Sold @ ₹{pos['exit_price']:.2f} (+₹{pnl_share:.2f}/share)\n"
                            f"Profit Locked: *+₹{total_pnl:,.2f}* 🎉"
                        )
                        print(f"  🎉 {msg.replace('*', '')}")
                        send_telegram_message(msg)

                else:
                    # Initial Stop Loss mode (before target hit)
                    if curr_price <= pos['stop_loss_price'] or bar_low <= pos['stop_loss_price']:
                        pos['status'] = 'CLOSED'
                        pos['exit_price'] = pos['stop_loss_price']
                        pos['exit_reason'] = f'STOP_LOSS_HIT (-₹{STOP_LOSS_INR:g})'
                        pos['exit_time'] = time_str
                        pnl_share = -STOP_LOSS_INR
                        total_pnl = round(pos['quantity'] * pnl_share, 2)

                        msg = (
                            f"🔴 *STOP LOSS TRIGGERED!* ⚠️\n"
                            f"Stock: *{ticker}*\n"
                            f"Bought {pos['quantity']} shares @ ₹{pos['entry_price']:.2f}\n"
                            f"Sold @ ₹{pos['exit_price']:.2f} (-₹{STOP_LOSS_INR:.2f})\n"
                            f"Net Loss: *₹{total_pnl:,.2f}*"
                        )
                        print(f"  ⚠️ {msg.replace('*', '')}")
                        send_telegram_message(msg)

        # Sync active positions status to SQLite outcomes
        outcomes_to_save = []
        for ticker, pos in active_positions.items():
            entry_p = pos['entry_price']
            exit_p = pos['exit_price'] or pos.get('current_price') or pos['high_price']
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

        if now_ist.weekday() >= 5:
            print("🏛️ Market is closed today (Weekend). Closing 1-minute monitoring daemon.")
            break

        # Check market close time (15:30 IST)
        if now_ist.hour >= 15 and now_ist.minute >= 30:
            print("🌆 Market Close Time Reached (15:30 IST). Closing 1-minute monitoring daemon.")
            # Ensure any still-open positions are closed at current market price
            final_outcomes = []
            for ticker, pos in active_positions.items():
                if pos['status'] == 'OPEN':
                    pos['status'] = 'CLOSED'
                    close_p = pos.get('current_price') or pos['high_price']
                    pos['exit_price'] = close_p
                    pnl_share = round(close_p - pos['entry_price'], 2)
                    pos['exit_reason'] = f'TARGET_MET_MARKET_CLOSE (+₹{pnl_share:g})' if pos.get('target_hit') else 'MARKET_CLOSE'
                    pos['exit_time'] = '15:30'

                entry_p = pos['entry_price']
                exit_p = pos['exit_price']
                pnl_share = round(exit_p - entry_p, 2)
                tot_pnl = round(pos['quantity'] * pnl_share, 2)
                pnl_pct = round((tot_pnl / pos['invested_amount']) * 100, 2) if pos['invested_amount'] > 0 else 0.0

                final_outcomes.append({
                    'ticker': ticker,
                    'starting_price': entry_p,
                    'close_price': exit_p,
                    'high_price': pos['high_price'],
                    'low_price': pos['low_price'],
                    'exit_price': exit_p,
                    'exit_reason': pos['exit_reason'],
                    'exit_time': pos['exit_time'] or '15:30',
                    'quantity': pos['quantity'],
                    'invested_amount': pos['invested_amount'],
                    'pnl_per_share': pnl_share,
                    'total_pnl': tot_pnl,
                    'pnl_pct': pnl_pct,
                    'actual_gain_pct': pnl_pct,
                    'max_gain_pct': round(((pos['high_price'] - entry_p) / entry_p) * 100, 2),
                    'status': 'TARGET_MET' if 'TARGET' in (pos['exit_reason'] or '') else ('STOP_LOSS' if 'STOP_LOSS' in (pos['exit_reason'] or '') else 'CLOSE')
                })
            save_outcomes(date_str, final_outcomes)
            break

        time.sleep(interval_seconds)

if __name__ == "__main__":
    run_intraday_1m_tracker()
