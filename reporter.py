from typing import List, Dict, Any

def _get_curr_symbol(ticker: str) -> str:
    """Return ₹ for Indian stocks (default currency)."""
    return "₹"

def generate_morning_report_markdown(date_str: str, predictions: List[Dict[str, Any]]) -> str:
    """Generate detailed Morning Report formatted for Telegram and console."""
    lines = []
    lines.append(f"🌅 *TOP 5 INDIAN STOCKS GAIN PREDICTION* 🚀")
    lines.append(f"📅 *Date:* {date_str} | *NSE/BSE Market Open Analysis*")
    lines.append("───────────────────────────")
    lines.append("🤖 *AI Strategy:* Machine Learning Technical Signal Ensemble")
    lines.append("")

    for item in predictions:
        rank = item.get('rank', 1)
        ticker = item.get('ticker')
        curr = _get_curr_symbol(ticker)
        start_p = item.get('starting_price')
        exp_gain = item.get('expected_gain_pct')
        target_p = item.get('target_price')
        stop_l = item.get('stop_loss')
        conf = item.get('confidence_score')
        reasons = item.get('signal_reasons', 'Bullish Momentum')

        lines.append(f"*{rank}. {ticker}* 📈")
        lines.append(f"  • *Start Price:* {curr}{start_p:.2f}")
        lines.append(f"  • *Target Price:* {curr}{target_p:.2f} (+{exp_gain:.1f}%)")
        lines.append(f"  • *Stop Loss:* {curr}{stop_l:.2f}")
        lines.append(f"  • *AI Confidence:* {conf:.1f}%")
        lines.append(f"  • *Key Signals:* _{reasons}_")
        lines.append("")

    lines.append("───────────────────────────")
    lines.append("💡 *Note:* Target & Stop-loss apply for today's intraday/swing session.")
    lines.append("🔔 *Evening Update:* Post-close actual results & ML retraining report will be posted after market close!")
    
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
    lines.append(f"🌆 *EVENING MARKET CLOSE REPORT & ML RETRAINING* 📊")
    lines.append(f"📅 *Date:* {date_str} | *NSE/BSE Post-Close Detailed Analysis*")
    lines.append("───────────────────────────")
    lines.append(f"🎯 *Top 5 Predicted Indian Stocks vs Actual Closing Results:*")
    lines.append("")

    actual_gains = []

    for p in predictions:
        ticker = p['ticker']
        curr = _get_curr_symbol(ticker)
        start_p = p['starting_price']
        exp_gain = p['expected_gain_pct']
        
        actual = outcomes_map.get(ticker)
        if actual:
            close_p = actual['close_price']
            high_p = actual['high_price']
            low_p = actual['low_price']
            actual_gain = actual['actual_gain_pct']
            max_gain = actual['max_gain_pct']
            status = actual['status']
            actual_gains.append(actual_gain)

            if status == "TARGET_MET":
                status_emoji = "🎯 *TARGET MET*"
            elif status == "GAIN":
                status_emoji = "🟢 *GAIN*"
            else:
                status_emoji = "🔴 *FALL*"

            lines.append(f"*{p.get('rank', 1)}. {ticker}*  {status_emoji}")
            lines.append(f"  • *Start Price:* {curr}{start_p:.2f} ➔ *Close Price:* {curr}{close_p:.2f}")
            lines.append(f"  • *Intraday High/Low:* {curr}{high_p:.2f} / {curr}{low_p:.2f}")
            lines.append(f"  • *Expected Gain:* +{exp_gain:.1f}% | *Actual Return:* {actual_gain:+.2f}% (Max: +{max_gain:.2f}%)")
            lines.append("")
        else:
            lines.append(f"*{p.get('rank', 1)}. {ticker}* - Data Pending")
            lines.append("")

    avg_return = (sum(actual_gains) / len(actual_gains)) if actual_gains else 0.0

    lines.append("───────────────────────────")
    lines.append(f"📈 *DAY PERFORMANCE SUMMARY:*")
    lines.append(f"  • *Success / Target Hit:* {wins_count}/{total_count} ({win_rate:.1f}%)")
    lines.append(f"  • *Average Actual Return:* {avg_return:+.2f}%")
    lines.append("")
    lines.append(f"🧠 *STRATEGY & RETRAINING STATUS:*")
    lines.append(f"  • *Outcome Feedback:* Ingested into SQLite Database")
    lines.append(f"  • *ML Continuous Learning:* Retrained on today's price action (MAE: {mae:.4f})")
    lines.append(f"  • *Status:* Model & Strategy Updated for Next Day's Analysis 🚀")

    return "\n".join(lines)

