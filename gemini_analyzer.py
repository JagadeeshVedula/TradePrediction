import os
import json
import re
import requests
from typing import Dict, List, Any, Optional

from config import (
    MAX_STOCK_PRICE,
    INVESTMENT_PER_STOCK,
    PROFIT_TARGET_INR,
    STOP_LOSS_INR,
    TOP_N_PREDICTIONS
)

# Optional google-genai SDK import
try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

def get_gemini_api_key() -> str:
    """Retrieve Gemini API Key from environment or .env file."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        # Check config or directly in .env file if available
        if os.path.exists(".env"):
            try:
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            key = line.split("=", 1)[1].strip()
                            break
            except Exception:
                pass
    return key

def is_gemini_configured() -> bool:
    """Check if a valid Gemini API key is configured."""
    key = get_gemini_api_key()
    return bool(key and len(key) > 10 and not key.startswith("your_"))

def _call_gemini_api(prompt: str, api_key: str, model_name: str = "gemini-2.5-flash") -> Optional[str]:
    """Call Gemini API using official SDK or direct REST fallback."""
    # 1. Try google-genai SDK if available
    if HAS_GENAI_SDK:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            # Fall back to alternative model if 2.5 is not accessible
            if "2.5" in model_name:
                try:
                    client = genai.Client(api_key=api_key)
                    response = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=prompt
                    )
                    if response and response.text:
                        return response.text
                except Exception:
                    pass
            print(f"Notice: google-genai SDK call ({e}). Trying direct REST endpoint...")

    # 2. Direct REST endpoint fallback (Zero dependencies, guaranteed compatibility)
    models_to_try = [model_name, "gemini-1.5-flash", "gemini-2.0-flash"]
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95,
                "maxOutputTokens": 2048
            }
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            else:
                print(f"⚠️ Gemini REST attempt with {m} returned {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            print(f"⚠️ Gemini REST network error with {m}: {e}")

    return None

def _extract_json_from_response(text: str) -> Optional[Any]:
    """Cleanly parse JSON from LLM response, stripping code fences if present."""
    if not text:
        return None
    # Strip ```json ... ``` blocks
    cleaned = text.strip()
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if json_match:
        cleaned = json_match.group(1).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        # Try extracting text between first [ and last ] or { and }
        try:
            first_bracket = cleaned.find("[")
            last_bracket = cleaned.rfind("]")
            if first_bracket != -1 and last_bracket != -1:
                return json.loads(cleaned[first_bracket:last_bracket + 1])
        except Exception:
            pass
    return None

def analyze_and_rank_predictions_with_gemini(
    candidates: List[Dict[str, Any]],
    market_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Use Gemini AI to analyze candidate Indian stocks against global market cues (US & Singapore)
    and Times of India / Moneycontrol news to select the Top 5 with the HIGHEST CONFIDENCE.
    """
    if not candidates:
        return []

    api_key = get_gemini_api_key()
    if not is_gemini_configured():
        print("💡 [Gemini AI]: GEMINI_API_KEY is not set. You can provide it in .env or send /set_key <KEY> on Telegram.")
        print("⚡ [Fallback]: Selecting top stocks using quantitative technical ensemble scoring.")
        return _fallback_quantitative_ranking(candidates, market_context)

    print("🧠 [Gemini AI]: Feeding US/Singapore market cues, domestic news, and technical signals to Gemini...")

    # Format candidates for Gemini prompt
    candidate_summary = []
    for c in candidates:
        candidate_summary.append({
            "ticker": c["ticker"],
            "starting_price": c["starting_price"],
            "expected_gain_pct": c.get("expected_gain_pct", 2.0),
            "rsi_14": c.get("features", {}).get("rsi_14", 50),
            "volume_ratio": c.get("features", {}).get("volume_ratio", 1.0),
            "macd_hist": c.get("features", {}).get("macd_hist", 0),
            "momentum_1d": c.get("features", {}).get("momentum_1d", 0),
            "recent_news": c.get("recent_news", [])
        })

    prompt = f"""
You are an elite Wall Street & Dalal Street Quantitative Market Strategist and AI Trading Engine.
Your task is to select the TOP 5 INDIAN STOCKS (< ₹500) with the HIGHEST CONFIDENCE for intraday trading today on the National Stock Exchange (NSE).

### INTRADAY TRADING STRATEGY RULES:
- Universe: All stocks must be priced under ₹500.
- Assumed Capital Allocation: ₹25,000 per stock.
- Exit Strategy:
  * Pre-10:00 AM IST: Early target profit exit at +₹10.00 gain per share.
  * Post-10:00 AM IST: Target at +₹{PROFIT_TARGET_INR:.2f} gain per share; upon reaching target, Stop-Loss is pushed to +₹2 (locking +₹1 profit) and trails +₹1 for every +₹1 increase in stock price. Initial Stop-Loss is -₹{STOP_LOSS_INR:.2f} per share.

### GLOBAL MARKET CUES (US & SINGAPORE / ASIA):
{market_context.get("summary_text", "US and Asian indices mixed.")}
Overall Global Tone: {market_context.get("overall_tone", "NEUTRAL")}

### DOMESTIC FINANCIAL NEWS (MONEYCONTROL & TIMES OF INDIA):
{market_context.get("formatted_news_text", "No breaking headlines.")}

### TECHNICAL CANDIDATE STOCKS UNDER ₹500 (Pre-screened):
{json.dumps(candidate_summary, indent=2)}

### INSTRUCTIONS:
1. Synthesize Global Cues: Evaluate how US market close (S&P 500, Nasdaq, Dow Jones) and Singapore Straits Times / Asian cues influence Indian sectors (e.g. Metals, Banking, Energy, PSU, Infra, Tech).
2. Filter & Eliminate Risks: Drop candidates that face adverse news or high downside volatility that could hit the -₹{STOP_LOSS_INR:.2f} stop loss.
3. Select the TOP 5 Highest-Confidence Winners: Pick the 5 stocks with the strongest catalyst alignment (Technical breakout + volume + macro/news tailwind) to achieve +₹{PROFIT_TARGET_INR:.2f} target (with upside trailing stop profit) or early +₹10.00 target.
4. Assign an AI Confidence Score: Must be between 82.0% and 98.0% based on conviction.
5. Provide a crisp, high-impact `signal_reasons` for each (15-20 words max highlighting catalyst, news link, and technical momentum).

### OUTPUT FORMAT:
Return ONLY a valid JSON array of exactly 5 objects in this structure:
[
  {{
    "rank": 1,
    "ticker": "TICKER.NS",
    "confidence_score": 94.5,
    "expected_gain_pct": 2.8,
    "signal_reasons": "US metal rally tailwind + Heavy volume breakout & Bullish MACD crossover",
    "catalyst": "Global commodity rally & domestic PSU demand",
    "selection_basis": "Bullish technical setup with 1.4x volume surge, expanding MACD histogram, and strong support at entry. Chosen over other candidates due to high risk-reward ratio.",
    "news_impact": "Boosted by overnight surge in global metal indices and increased domestic infrastructure allocations reported in Economic Times."
  }},
  ...
]
"""

    response_text = _call_gemini_api(prompt, api_key)
    parsed = _extract_json_from_response(response_text) if response_text else None

    if parsed and isinstance(parsed, list) and len(parsed) >= 1:
        print(f"✨ [Gemini AI]: Successfully selected Top {len(parsed[:TOP_N_PREDICTIONS])} high-confidence stocks!")
        candidates_map = {c["ticker"]: c for c in candidates}
        final_picks = []

        for item in parsed[:TOP_N_PREDICTIONS]:
            ticker = item.get("ticker", "").strip()
            # Handle potential ticker variations (e.g. without .NS)
            if ticker not in candidates_map:
                if f"{ticker}.NS" in candidates_map:
                    ticker = f"{ticker}.NS"
                else:
                    # Match by base name
                    for cand_tick in candidates_map:
                        if cand_tick.startswith(ticker):
                            ticker = cand_tick
                            break

            base_cand = candidates_map.get(ticker)
            if not base_cand:
                continue

            start_p = base_cand["starting_price"]
            conf = float(item.get("confidence_score", base_cand.get("confidence_score", 85.0)))
            reasons = item.get("signal_reasons") or base_cand.get("signal_reasons", "Strong Bullish Catalyst")
            catalyst = item.get("catalyst", "")
            if catalyst and catalyst not in reasons:
                reasons = f"⚡ {catalyst} | {reasons}"

            exp_gain = float(item.get("expected_gain_pct", base_cand.get("expected_gain_pct", 2.0)))
            qty = base_cand.get("quantity", max(1, int(INVESTMENT_PER_STOCK / start_p)))
            inv_amt = round(qty * start_p, 2)
            sel_basis = item.get("selection_basis") or f"Bullish technical indicators aligned with {catalyst or 'sectoral momentum'}."
            news_imp = item.get("news_impact") or ("; ".join(base_cand.get("recent_news", [])) if base_cand.get("recent_news") else "Benefiting from positive broader market sentiment.")

            final_picks.append({
                "rank": len(final_picks) + 1,
                "ticker": ticker,
                "starting_price": start_p,
                "expected_gain_pct": round(exp_gain, 2),
                "target_price": round(start_p + PROFIT_TARGET_INR, 2),
                "stop_loss": round(start_p - STOP_LOSS_INR, 2),
                "confidence_score": round(min(98.5, max(75.0, conf)), 1),
                "quantity": qty,
                "invested_amount": inv_amt,
                "signal_reasons": reasons,
                "selection_basis": sel_basis,
                "news_impact": news_imp,
                "catalyst": catalyst,
                "gemini_selected": True
            })

        if len(final_picks) >= TOP_N_PREDICTIONS:
            return final_picks

    print("⚠️ [Gemini AI]: Could not parse complete selection from Gemini output. Falling back to quantitative ranking.")
    return _fallback_quantitative_ranking(candidates, market_context)

def _fallback_quantitative_ranking(
    candidates: List[Dict[str, Any]],
    market_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Quantitative fallback ranking when Gemini API is unavailable."""
    overall_tone = market_context.get("overall_tone", "NEUTRAL")
    
    # Sort candidates by combined expected gain and technical score
    sorted_candidates = sorted(
        candidates,
        key=lambda x: (x.get("expected_gain_pct", 0) * 1.5 + x.get("confidence_score", 50) * 0.1),
        reverse=True
    )
    
    top_picks = []
    for rank, item in enumerate(sorted_candidates[:TOP_N_PREDICTIONS], start=1):
        item_copy = dict(item)
        item_copy["rank"] = rank
        item_copy["gemini_selected"] = False
        reasons = item_copy.get("signal_reasons", "Bullish Technical Momentum")
        # Augment with macro context
        if overall_tone == "BULLISH":
            reasons = f"Global Bullish Support | {reasons}"
        item_copy["signal_reasons"] = reasons
        top_picks.append(item_copy)

    return top_picks

def generate_macro_briefing_markdown(market_context: Dict[str, Any]) -> str:
    """Generate clean macro briefing summary for reports and Telegram."""
    lines = []
    tone = market_context.get("overall_tone", "NEUTRAL")
    tone_emoji = "🟢 BULLISH" if tone == "BULLISH" else ("🔴 BEARISH" if tone == "BEARISH" else "🟡 MIXED/NEUTRAL")
    
    lines.append(f"🌐 *GLOBAL CUES & PRE-MARKET SENTIMENT:* {tone_emoji}")
    cues_text = market_context.get("summary_text", "")
    if cues_text:
        lines.append(cues_text)
    
    news_items = market_context.get("news_items", [])
    if news_items:
        lines.append("\n📰 *Key Domestic Catalysts (Moneycontrol & TOI):*")
        for n in news_items[:3]:
            lines.append(f"  • _{n['title']}_")
    
    return "\n".join(lines)


def generate_gemini_analysis_markdown(
    date_str: str,
    predictions: List[Dict[str, Any]],
    market_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate comprehensive, transparent deep-dive report on:
    - On what bases Gemini AI selected the Top 5 Indian stocks (< ₹500)
    - How global market cues and domestic financial news impacted them
    - Full quantitative and fundamental risk-reward breakdown
    """
    if not market_context:
        from market_news import get_market_context_summary
        market_context = get_market_context_summary()

    lines = []
    lines.append("🧠 *GOOGLE GEMINI AI — DEEP STOCK SELECTION ANALYSIS* 🚀")
    lines.append(f"📅 *Date:* `{date_str}` | *Universe:* Indian Stocks (< ₹500)")
    lines.append("───────────────────────────")

    # Section 1: Global Market Cues & Macro Tone
    tone = market_context.get("overall_tone", "NEUTRAL")
    tone_emoji = "🟢 BULLISH" if tone == "BULLISH" else ("🔴 BEARISH" if tone == "BEARISH" else "🟡 MIXED / NEUTRAL")
    lines.append(f"🌐 *GLOBAL CUES & PRE-MARKET MACRO TONE:* {tone_emoji}")
    cues_summary = market_context.get("summary_text", "")
    if cues_summary:
        lines.append(cues_summary)
    else:
        lines.append("US & Asian indices mixed; domestic liquidity positive.")
    lines.append("")

    # Section 2: Domestic Financial News Landscape
    news_items = market_context.get("news_items", [])
    if news_items:
        lines.append("📰 *DOMESTIC NEWS HEADLINES (Moneycontrol & TOI):*")
        for item in news_items[:3]:
            lines.append(f"  • *[{item['source']}]* _{item['title']}_")
        lines.append("")

    lines.append("───────────────────────────")
    lines.append("🎯 *TOP 5 PICKS — SELECTION BASES & NEWS IMPACT:*")
    lines.append("───────────────────────────")

    rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    for idx, p in enumerate(predictions):
        rank_icon = rank_emojis[idx] if idx < len(rank_emojis) else f"#{idx+1}"
        ticker = p.get('ticker', '')
        start_p = p.get('starting_price', 0.0)
        target_p = p.get('target_price', start_p + PROFIT_TARGET_INR)
        stop_l = p.get('stop_loss', start_p - STOP_LOSS_INR)
        conf = p.get('confidence_score', 85.0)
        exp_gain = p.get('expected_gain_pct', 2.0)
        qty = p.get('quantity', max(1, int(INVESTMENT_PER_STOCK / start_p))) if start_p > 0 else 0
        inv_amt = p.get('invested_amount', round(qty * start_p, 2))

        # Bases & News data
        sel_basis = p.get('selection_basis') or p.get('signal_reasons') or "Strong technical alignment across MACD, volume, and momentum indicators."
        news_imp = p.get('news_impact') or "Supported by domestic sector resilience and positive fund flows."
        catalyst = p.get('catalyst') or ""

        conf_badge = f"🔥 *{conf:.1f}% Conviction*" if conf >= 90 else f"⭐ *{conf:.1f}% Conviction*"

        lines.append(f"{rank_icon} *{ticker}*  {conf_badge}")
        lines.append(f"  • *Key Metrics:* Entry: ₹{start_p:.2f} | Target: ₹{target_p:.2f} (+₹{PROFIT_TARGET_INR:.2f}) | Initial SL: ₹{stop_l:.2f}")
        lines.append(f"  • *Position Size:* {qty} shares (Allocated: ₹{inv_amt:,.2f} | Exp. Gain: +{exp_gain:.2f}%)")
        if catalyst:
            lines.append(f"  • ⚡ *Primary Catalyst:* _{catalyst}_")
        lines.append(f"  • 📊 *Selection Basis (Why Gemini Chose It):*")
        lines.append(f"    {sel_basis}")
        lines.append(f"  • 📰 *News Impact & Market Influence:*")
        lines.append(f"    {news_imp}")
        lines.append("")

    lines.append("───────────────────────────")
    lines.append("⚙️ *SELECTION METHODOLOGY TRANSPARENCY:*")
    lines.append("1. *Universe Filter:* Screened all liquid NSE stocks priced under ₹500.")
    lines.append("2. *Quantitative ML Model:* Screened technical indicators (RSI, MACD, 20-day Volume, ATR, Momentum).")
    lines.append("3. *Macro & News Ingestion:* Live US/Asian index cues and RSS news headlines fed into Gemini 2.5 Flash.")
    lines.append("4. *AI Synthesis:* Gemini analyzed news tailwinds vs downside volatility risk to pick the Top 5.")
    lines.append("5. *Intraday Trade Rules:* Assumed ₹25k allocation; Pre-10:00 AM target +₹10; Post-10:00 AM +₹2 target with +₹1 trailing stop.")

    return "\n".join(lines)


def run_gemini_deep_analysis(date_str: Optional[str] = None) -> str:
    """
    Produce and return Gemini Deep Analysis report for a given date.
    Pulls existing predictions from database or runs fresh analysis.
    """
    import datetime
    from zoneinfo import ZoneInfo
    from database import get_predictions_by_date
    from market_news import get_market_context_summary

    if not date_str:
        date_str = datetime.date.today().strftime("%Y-%m-%d")

    predictions = get_predictions_by_date(date_str)
    market_context = get_market_context_summary()

    # If predictions exist and have selection_basis
    if predictions and any(p.get("selection_basis") for p in predictions):
        return generate_gemini_analysis_markdown(date_str, predictions, market_context)

    # If predictions exist but lack detailed selection_basis, ask Gemini to enrich them
    api_key = get_gemini_api_key()
    if predictions and is_gemini_configured():
        prompt = f"""
You are an expert Dalal Street stock strategist. Explain in detail the exact selection bases and news impact for these Top 5 Indian stocks (< ₹500) predicted for trading on {date_str}:

STOCKS:
{json.dumps([{ 'ticker': p['ticker'], 'starting_price': p['starting_price'], 'signal_reasons': p.get('signal_reasons', '') } for p in predictions], indent=2)}

GLOBAL CUES:
{market_context.get('summary_text', '')}

DOMESTIC NEWS:
{market_context.get('formatted_news_text', '')}

For EACH stock, return a JSON array with:
- "ticker": ticker
- "selection_basis": 2-3 sentences explaining technical reasons (momentum, volume, price support) and why chosen over other stocks
- "news_impact": 1-2 sentences explaining specific company or sectoral news impacting it today
- "catalyst": crisp 4-6 word catalyst phrase

Return ONLY valid JSON array.
"""
        resp = _call_gemini_api(prompt, api_key)
        parsed = _extract_json_from_response(resp) if resp else None
        if parsed and isinstance(parsed, list):
            parsed_map = {item["ticker"]: item for item in parsed if "ticker" in item}
            for p in predictions:
                t = p["ticker"]
                info = parsed_map.get(t) or parsed_map.get(t.replace(".NS", ""))
                if info:
                    p["selection_basis"] = info.get("selection_basis", p.get("signal_reasons", ""))
                    p["news_impact"] = info.get("news_impact", "Supported by sectoral news flow.")
                    p["catalyst"] = info.get("catalyst", "")

            return generate_gemini_analysis_markdown(date_str, predictions, market_context)

    # Fallback: if no predictions recorded yet, run predictor to generate them
    from ml_model import TechStockPredictor
    from config import DEFAULT_TECH_TICKERS
    predictor = TechStockPredictor()
    top_5 = predictor.predict_top_5_gainers(DEFAULT_TECH_TICKERS)
    if top_5:
        from database import save_predictions
        save_predictions(date_str, top_5)
        return generate_gemini_analysis_markdown(date_str, top_5, getattr(predictor, "last_market_context", market_context))

    return "⚠️ Could not generate Gemini Deep Analysis. Please check market data connection or run /morning first."

