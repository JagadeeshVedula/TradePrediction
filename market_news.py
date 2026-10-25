import sys
import requests
import datetime
import xml.etree.ElementTree as ET
import html
import yfinance as yf
from typing import Dict, List, Any, Optional

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Global Index Tickers on Yahoo Finance
US_INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI"
}

ASIAN_INDICES = {
    "Singapore Straits Times": "^STI",
    "Nikkei 225": "^N225"
}

# Reliable RSS Feeds for Financial & Market News
RSS_FEEDS = [
    {
        "name": "Moneycontrol Market Reports",
        "url": "https://www.moneycontrol.com/rss/marketreports.xml"
    },
    {
        "name": "Moneycontrol Top News",
        "url": "https://www.moneycontrol.com/rss/MCtopnews.xml"
    },
    {
        "name": "Times of India Business",
        "url": "https://timesofindia.indiatimes.com/rssfeeds/1898055.cms"
    },
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
    }
]

def clean_html_text(raw_text: Optional[str]) -> str:
    """Clean HTML entities and whitespace from text."""
    if not raw_text:
        return ""
    # Unescape HTML entities (e.g. &#39; -> ', &amp; -> &)
    cleaned = html.unescape(raw_text)
    # Remove simple XML/HTML tags
    cleaned = cleaned.replace("<![CDATA[", "").replace("]]>", "")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()

def fetch_global_market_cues() -> Dict[str, Any]:
    """
    Fetch previous trading day performance for US and Asian/Singapore indices.
    Returns structured metrics including close, change, % change, and sentiment.
    """
    results = {
        "us_markets": {},
        "asian_markets": {},
        "overall_tone": "NEUTRAL",
        "summary_text": ""
    }

    all_symbols = list(US_INDICES.values()) + list(ASIAN_INDICES.values())
    try:
        data = yf.download(all_symbols, period="5d", progress=False)
        if data.empty or "Close" not in data:
            return results

        close_df = data["Close"]

        # Helper to compute change
        def get_stat(sym: str) -> Optional[Dict[str, Any]]:
            try:
                series = close_df[sym].dropna()
                if len(series) < 2:
                    return None
                last_close = float(series.iloc[-1])
                prev_close = float(series.iloc[-2])
                change = last_close - prev_close
                change_pct = (change / prev_close) * 100
                return {
                    "last_close": round(last_close, 2),
                    "prev_close": round(prev_close, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "sentiment": "BULLISH" if change_pct >= 0.2 else ("BEARISH" if change_pct <= -0.2 else "FLAT")
                }
            except Exception:
                return None

        for name, sym in US_INDICES.items():
            st = get_stat(sym)
            if st:
                results["us_markets"][name] = st

        for name, sym in ASIAN_INDICES.items():
            st = get_stat(sym)
            if st:
                results["asian_markets"][name] = st

        # Calculate overall market tone
        us_pcts = [v["change_pct"] for v in results["us_markets"].values()]
        asian_pcts = [v["change_pct"] for v in results["asian_markets"].values()]
        all_pcts = us_pcts + asian_pcts
        avg_pct = sum(all_pcts) / len(all_pcts) if all_pcts else 0.0

        if avg_pct >= 0.35:
            results["overall_tone"] = "BULLISH"
        elif avg_pct <= -0.35:
            results["overall_tone"] = "BEARISH"
        else:
            results["overall_tone"] = "MIXED/NEUTRAL"

        lines = []
        for name, st in results["us_markets"].items():
            sym_icon = "🟢" if st["change_pct"] >= 0 else "🔴"
            lines.append(f"{sym_icon} {name}: {st['last_close']:,.2f} ({st['change_pct']:+.2f}%)")
        for name, st in results["asian_markets"].items():
            sym_icon = "🟢" if st["change_pct"] >= 0 else "🔴"
            lines.append(f"{sym_icon} {name}: {st['last_close']:,.2f} ({st['change_pct']:+.2f}%)")
        results["summary_text"] = "\n".join(lines)

    except Exception as e:
        print(f"⚠️ Notice: Global cues fetch encountered issue ({e}). Continuing...")

    return results

def fetch_indian_financial_news(limit: int = 12) -> List[Dict[str, str]]:
    """
    Fetch top headlines from Moneycontrol and Times of India / Economic Times RSS feeds.
    Returns a list of dicts: {'title': ..., 'source': ..., 'summary': ...}
    """
    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    seen_titles = set()

    for feed in RSS_FEEDS:
        try:
            resp = requests.get(feed["url"], headers=headers, timeout=6)
            if resp.status_code != 200:
                continue

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            for item in items[:4]:
                title_elem = item.find("title")
                desc_elem = item.find("description")
                
                title = clean_html_text(title_elem.text if title_elem is not None else "")
                desc = clean_html_text(desc_elem.text if desc_elem is not None else "")
                
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                # Skip non-relevant articles if any
                articles.append({
                    "title": title,
                    "source": feed["name"],
                    "summary": desc[:180] + ("..." if len(desc) > 180 else "")
                })

                if len(articles) >= limit:
                    break
        except Exception:
            continue

        if len(articles) >= limit:
            break

    return articles

def fetch_stock_specific_news(ticker: str, max_items: int = 2) -> List[str]:
    """Fetch recent news headlines specifically for a given stock ticker."""
    headlines = []
    try:
        t = yf.Ticker(ticker)
        news_items = getattr(t, "news", [])
        if news_items:
            for item in news_items[:max_items]:
                # Handle both dict formats in recent yfinance versions
                title = item.get("title") or (item.get("content", {}).get("title") if isinstance(item.get("content"), dict) else None)
                if title:
                    clean_title = clean_html_text(title)
                    if clean_title:
                        headlines.append(clean_title)
    except Exception:
        pass
    return headlines

def get_market_context_summary() -> Dict[str, Any]:
    """
    Produce comprehensive market context combining US/Singapore indices and domestic news.
    Ready to pass directly to Gemini AI.
    """
    global_cues = fetch_global_market_cues()
    news_items = fetch_indian_financial_news(limit=10)

    formatted_news = []
    for idx, item in enumerate(news_items, start=1):
        formatted_news.append(f"{idx}. [{item['source']}] {item['title']}")

    return {
        "global_cues": global_cues,
        "news_items": news_items,
        "formatted_news_text": "\n".join(formatted_news),
        "overall_tone": global_cues.get("overall_tone", "NEUTRAL"),
        "summary_text": global_cues.get("summary_text", "")
    }

if __name__ == "__main__":
    print("Testing market_news module...")
    ctx = get_market_context_summary()
    print("\n🌐 Global Cues:")
    print(ctx["summary_text"])
    print(f"\nOverall Tone: {ctx['overall_tone']}")
    print("\n📰 Domestic News Headlines:")
    print(ctx["formatted_news_text"])
