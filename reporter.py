from typing import List, Dict, Any

from config import PROFIT_TARGET_INR, STOP_LOSS_INR

def _get_curr_symbol(ticker: str) -> str:
    """Return ₹ for Indian stocks (default currency)."""
    return "₹"

def generate_morning_report_markdown(date_str: str, predictions: List[Dict[str, Any]]) -> str:
    """Generate detailed Morning Report formatted for Telegram and console."""
    lines = []
    lines.append(f"🌅 *TOP 5 INDIAN STOCKS (< ₹500) GAIN PREDICTION* 🚀")
    lines.append(f"📅 *Date:* {date_str} | *NSE Intraday Trading Strategy*")
    lines.append("───────────────────────────")
    lines.append("💼 *Investment Rules:* Assumed ₹25,000 on each stock (Total: ₹1,25,000)")
    lines.append(f"🎯 *Exit Strategy:* Pre-10:00 AM Sell on +₹10.00 | Post-10:00 AM Target +₹{PROFIT_TARGET_INR:.2f} / Stop Loss -₹{STOP_LOSS_INR:.2f}")
    lines.append("───────────────────────────")
    lines.append("")

    total_allocated = 0.0

    for item in predictions:
        rank = item.get('rank', 1)
        ticker = item.get('ticker')
        curr = _get_curr_symbol(ticker)
        start_p = item.get('starting_price', 0.0)
        target_p = item.get('target_price', start_p + PROFIT_TARGET_INR)
        stop_l = item.get('stop_loss', start_p - STOP_LOSS_INR)
        conf = item.get('confidence_score', 0.0)
        qty = item.get('quantity', max(1, int(25000 / start_p)) if start_p > 0 else 0)
        inv_amt = item.get('invested_amount', round(qty * start_p, 2))
        total_allocated += inv_amt
        reasons = item.get('signal_reasons', 'Bullish Technical Momentum')

        lines.append(f"*{rank}. {ticker}* 📈")
        lines.append(f"  • *Entry Price:* {curr}{start_p:.2f} (< ₹500)")
        lines.append(f"  • *Shares Quantity:* {qty} shares")
        lines.append(f"  • *Capital Invested:* {curr}{inv_amt:,.2f}")
        lines.append(f"  • *Target Sell Price:* {curr}{target_p:.2f} (+₹{PROFIT_TARGET_INR:.2f})")
        lines.append(f"  • *Stop Loss Price:* {curr}{stop_l:.2f} (-₹{STOP_LOSS_INR:.2f})")
        lines.append(f"  • *AI Confidence:* {conf:.1f}%")
        lines.append(f"  • *Key Signals:* _{reasons}_")
        lines.append("")

    lines.append("───────────────────────────")
    lines.append(f"💰 *TOTAL PORTFOLIO ALLOCATION:* {curr}{total_allocated:,.2f}")
    lines.append("⏱️ *1-Minute Tracker:* Continuous live price check every 60 seconds")
    lines.append("🔔 *Evening Report:* Detailed profit/loss breakdown per share will be generated after close!")
    
    return "\n".join(lines)


def generate_evening_report_markdown(date_str: str, summary: Dict[str, Any]) -> str:
    """Generate detailed Evening Closing Market Analysis & Retraining Report."""
    predictions = summary.get('predictions', [])
    outcomes = summary.get('outcomes', [])
    win_rate = summary.get('win_rate_pct', 0.0)
    wins_count = summary.get('wins_count', 0)
    total_count = summary.get('total_count', 0)
    mae = summary.get('mae', 0.0)

    # Index outcomes by ticker
    outcomes_map = {o['ticker']: o for o in outcomes}

    lines = []
    lines.append(f"🌆 *EVENING INTRADAY PROFIT & LOSS REPORT* 📊")
    lines.append(f"📅 *Date:* {date_str} | *NSE Intraday Performance (< ₹500 Stocks)*")
    lines.append("───────────────────────────")
    lines.append(f"🎯 *SHARE-BY-SHARE PROFIT & LOSS BREAKDOWN:*")
    lines.append("")

    total_invested_portfolio = 0.0
    total_pnl_portfolio = 0.0
    targets_met_count = 0
    stop_loss_count = 0
    market_close_count = 0

    for p in predictions:
        ticker = p['ticker']
        curr = _get_curr_symbol(ticker)
        start_p = p['starting_price']
        
        actual = outcomes_map.get(ticker)
        if actual:
            exit_p = actual.get('exit_price', actual['close_price'])
            exit_reason = actual.get('exit_reason', 'MARKET_CLOSE')
            exit_time = actual.get('exit_time', '15:30')
            qty = actual.get('quantity', max(1, int(25000 / start_p)))
            inv_amt = actual.get('invested_amount', round(qty * start_p, 2))
            pnl_share = actual.get('pnl_per_share', round(exit_p - start_p, 2))
            stock_pnl = actual.get('total_pnl', round(qty * pnl_share, 2))
            pnl_pct = actual.get('pnl_pct', round((stock_pnl / inv_amt) * 100, 2) if inv_amt > 0 else 0.0)

            total_invested_portfolio += inv_amt
            total_pnl_portfolio += stock_pnl

            if "EARLY_TARGET" in exit_reason:
                status_badge = "🚀 *PRE-10AM EARLY TARGET HIT (+₹10.00)*"
                targets_met_count += 1
            elif "TARGET" in exit_reason:
                status_badge = f"🎯 *TARGET HIT (+₹{PROFIT_TARGET_INR:.2f})*"
                targets_met_count += 1
            elif "STOP_LOSS" in exit_reason:
                status_badge = f"🔴 *STOP-LOSS HIT (-₹{STOP_LOSS_INR:.2f})*"
                stop_loss_count += 1
            elif "MARKET_NOT_OPEN" in exit_reason or "PENDING" in exit_reason:
                status_badge = "⏳ *MARKET SESSION PENDING*"
            else:
                market_close_count += 1
                status_badge = "🟢 *GAIN (CLOSE)*" if stock_pnl >= 0 else "🔻 *LOSS (CLOSE)*"

            pnl_emoji = "🟢" if stock_pnl >= 0 else "🔴"

            lines.append(f"*{p.get('rank', 1)}. {ticker}*  {status_badge}")
            lines.append(f"  • *Entry Price:* {curr}{start_p:.2f}  ➔  *Exit Price:* {curr}{exit_p:.2f} (Time: {exit_time})")
            lines.append(f"  • *Quantity Bought:* {qty} shares @ ₹25,000 allocation ({curr}{inv_amt:,.2f})")
            clean_reason = exit_reason.replace('_', ' ')
            lines.append(f"  • *Exit Reason:* _{clean_reason}_")

            lines.append(f"  • *P&L per Share:* {curr}{pnl_share:+.2f}")
            lines.append(f"  • *Stock Net P&L:* {pnl_emoji} *{curr}{stock_pnl:+,.2f}* ({pnl_pct:+.2f}%)")
            lines.append("")
        else:
            lines.append(f"*{p.get('rank', 1)}. {ticker}* - Data Pending")
            lines.append("")

    overall_pnl_pct = (total_pnl_portfolio / total_invested_portfolio * 100) if total_invested_portfolio > 0 else 0.0
    overall_emoji = "🎉 🟢" if total_pnl_portfolio >= 0 else "⚠️ 🔴"

    lines.append("───────────────────────────")
    lines.append(f"📊 *OVERALL PORTFOLIO SUMMARY:*")
    lines.append(f"  • *Total Amount Invested:* {curr}{total_invested_portfolio:,.2f}")
    lines.append(f"  • *Overall Net Profit/Loss:* {overall_emoji} *{curr}{total_pnl_portfolio:+,.2f}*")
    lines.append(f"  • *Overall Return:* *{overall_pnl_pct:+.2f}%*")
    lines.append(f"  • *Execution Summary:* 🎯 {targets_met_count} Target Met | 🔴 {stop_loss_count} Stop-Loss Hit | 🕒 {market_close_count} Closed at EOD")
    lines.append("")
    lines.append(f"🧠 *AI LEARNING & RETRAINING STATUS:*")
    lines.append(f"  • *Outcome Database:* 1-Minute Ticks Recorded in SQLite")
    lines.append(f"  • *Continuous Retraining:* Updated on today's trades (MAE: {mae:.4f})")
    lines.append(f"  • *Status:* Ready for Next Trading Session 🚀")

    return "\n".join(lines)


