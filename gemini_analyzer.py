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
  * Post-10:00 AM IST: Standard profit target at +₹{PROFIT_TARGET_INR:.2f} gain per share; Stop-Loss at -₹{STOP_LOSS_INR:.2f} per share.

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
3. Select the TOP 5 Highest-Confidence Winners: Pick the 5 stocks with the strongest catalyst alignment (Technical breakout + volume + macro/news tailwind) to achieve +₹2.00 target or early +₹10.00 target.
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
    "catalyst": "Global commodity rally & domestic PSU demand"
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
