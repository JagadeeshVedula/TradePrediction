import os
import sys
import time
import threading
import datetime
import requests
from typing import Optional, List, Dict, Any

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_MODEL
from pipeline_state import is_pipeline_enabled, set_pipeline_state, get_pipeline_status_text
from gemini_analyzer import is_gemini_configured, get_gemini_api_key

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Global flag to control listener thread
_bot_listener_thread = None
_stop_event = threading.Event()

def update_gemini_api_key(new_key: str) -> bool:
    """Save updated Gemini API key to runtime environment and .env file."""
    clean_key = new_key.strip()
    if not clean_key or len(clean_key) < 10:
        return False

    os.environ["GEMINI_API_KEY"] = clean_key
    
    # Update .env file
    env_path = ".env"
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith("GEMINI_API_KEY="):
                lines[i] = f"GEMINI_API_KEY={clean_key}\n"
                found = True
                break

    if not found:
        lines.append(f"GEMINI_API_KEY={clean_key}\n")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        print(f"Error saving Gemini key to .env: {e}")
        return False

def send_telegram_message(text: str, target_chat_id: Optional[str] = None, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    """Send formatted text message to Telegram channel, group, or user chat."""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ Telegram Bot Token not configured in .env file.")
        return False

    if target_chat_id:
        chat_ids = [str(target_chat_id).strip()]
    else:
        chat_ids = [cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(",") if cid.strip()]

    if not chat_ids:
        print("⚠️ No valid Telegram Chat ID found.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    overall_success = True

    for chat_id in chat_ids:
        # Split text into chunks if it exceeds Telegram's 4096 char limit
        chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)] if len(text) > 4000 else [text]

        for idx, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown"
            }
            # Only attach reply_markup to the last chunk
            if reply_markup and idx == len(chunks) - 1:
                payload["reply_markup"] = reply_markup

            try:
                response = requests.post(url, json=payload, timeout=12)
                res_json = response.json()
                
                if response.status_code == 200 and res_json.get("ok"):
                    pass
                else:
                    # Retry without parse_mode if Markdown parsing failed
                    payload.pop("parse_mode", None)
                    res_plain = requests.post(url, json=payload, timeout=12)
                    if not (res_plain.status_code == 200 and res_plain.json().get("ok")):
                        print(f"❌ Failed to send Telegram message to {chat_id}: {res_plain.text}")
                        overall_success = False
            except Exception as e:
                print(f"❌ Network error sending message to Telegram ({chat_id}): {e}")
                overall_success = False

    return overall_success

def get_control_panel_inline_markup() -> Dict[str, Any]:
    """Clickable inline buttons attached directly to messages."""
    return {
        "inline_keyboard": [
            [
                {"text": "🌅 Run Morning Prediction", "callback_data": "/morning"},
                {"text": "🔄 Full Pipeline (Cycle)", "callback_data": "/full_cycle"}
            ],
            [
                {"text": "🌆 Evening P&L Report", "callback_data": "/evening"},
                {"text": "📊 Pipeline Status", "callback_data": "/status"}
            ],
            [
                {"text": "🌐 Global News & Cues", "callback_data": "/news"},
                {"text": "⏸️ Pause Pipeline", "callback_data": "/stop_pipeline"}
            ]
        ]
    }

def get_persistent_reply_keyboard_markup() -> Dict[str, Any]:
    """Persistent big buttons docked at the bottom of the chat window."""
    return {
        "keyboard": [
            [{"text": "🌅 Morning Prediction"}, {"text": "🔄 Full Pipeline"}],
            [{"text": "🌆 Evening Report"}, {"text": "📊 Status"}],
            [{"text": "🌐 Market News"}, {"text": "🎛️ Menu"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def send_control_panel(chat_id: str):
    """Send interactive control panel with clickable buttons to user."""
    panel_text = (
        "🎛️ *INDIAN STOCK AI TRADING CONTROL PANEL* 🚀\n"
        "───────────────────────────\n"
        "Use the buttons below to operate the automated trading pipeline:\n\n"
        "• 🌅 *Run Morning Prediction*: Analyze Indian stocks (< ₹500) with Gemini AI & Global News\n"
        "• 🔄 *Full Pipeline (Full Cycle)*: Run Complete Cycle (Morning Prediction + 1m Intraday Tracker + Evening Report)\n"
        "• 🌆 *Evening Report*: Post-market close P&L breakdown per share\n"
        "• 📊 *Pipeline Status*: View active state & Gemini connection\n"
        "• 🌐 *Market News*: Live US & Singapore cues + Moneycontrol/TOI headlines\n"
        "• ⏸️ *Pause Pipeline*: Pause scheduled automation\n"
        "───────────────────────────\n"
        "💡 *Tap any button below to trigger actions immediately!*"
    )
    # Send with inline keyboard
    send_telegram_message(panel_text, target_chat_id=chat_id, reply_markup=get_control_panel_inline_markup())
    # Also send persistent reply keyboard so big buttons remain docked at bottom of chat
    quick_bar = "👇 *Menu controls are also docked on your keyboard below:*"
    send_telegram_message(quick_bar, target_chat_id=chat_id, reply_markup=get_persistent_reply_keyboard_markup())

def register_bot_commands() -> bool:
    """Register slash commands and menu button in Telegram for all chat types."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    commands = [
        {"command": "morning", "description": "🌅 Run Morning Prediction (< ₹500)"},
        {"command": "full_pipeline", "description": "🔄 Run Full Pipeline Cycle (Morning + Monitor + Evening)"},
        {"command": "evening", "description": "🌆 Run Evening P&L Report & Retraining"},
        {"command": "status", "description": "📊 Check Pipeline State & Gemini Status"},
        {"command": "news", "description": "🌐 View US/Singapore Cues & Market News"},
        {"command": "stop_pipeline", "description": "⏸️ Pause Automated Trading Pipeline"},
        {"command": "menu", "description": "🎛️ Open Control Panel with Clickable Buttons"},
        {"command": "help", "description": "❓ Show Help & Commands Guide"}
    ]
    try:
        # Default scope
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands", json={"commands": commands}, timeout=10)
        # Private chats
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands", json={"commands": commands, "scope": {"type": "all_private_chats"}}, timeout=10)
        # Group chats
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands", json={"commands": commands, "scope": {"type": "all_group_chats"}}, timeout=10)
        # Menu button
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatMenuButton", json={"menu_button": {"type": "commands"}}, timeout=10)
        return True
    except Exception as e:
        print(f"Notice: Failed registering Telegram commands: {e}")
        return False

def _execute_morning_command(chat_id: str):
    """Worker to run morning prediction and reply directly to the requester."""
    import main
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    send_telegram_message(
        f"⏳ *Running Morning Prediction for {date_str}...*\n"
        f"🔍 Fetching US Market Close (S&P/Nasdaq/Dow), Singapore Straits Times, and Moneycontrol/TOI news.\n"
        f"🧠 Analyzing candidates (< ₹500) with Google Gemini AI for highest confidence picks. Please wait ~15-20 seconds...",
        target_chat_id=chat_id
    )
    try:
        main.run_morning_mode(date_str, send_telegram=True, target_chat_id=chat_id)
    except Exception as e:
        send_telegram_message(f"❌ Error during morning prediction: {e}", target_chat_id=chat_id)

def _execute_full_cycle_command(chat_id: str):
    """Worker to trigger full pipeline cycle (Morning + Monitor + Evening)."""
    import main
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    send_telegram_message(
        f"🔄 *Starting Full Pipeline Cycle for {date_str}...* 🚀\n"
        f"───────────────────────────\n"
        f"• 🌅 *Phase 1:* Morning Predictions (< ₹500 stocks, Gemini AI + News)\n"
        f"• ⏱️ *Phase 2:* 1-Minute Live Intraday Tracking\n"
        f"• 🌆 *Phase 3:* Evening P&L Report & Retraining\n\n"
        f"⏳ Processing Morning Prediction now. Please wait ~15-20s...",
        target_chat_id=chat_id
    )
    try:
        main.run_full_cycle_mode(date_str, send_telegram=True, target_chat_id=chat_id)
    except Exception as e:
        send_telegram_message(f"❌ Error during full cycle execution: {e}", target_chat_id=chat_id)

def _execute_evening_command(chat_id: str):
    """Worker to run evening report and reply directly to the requester."""
    import main
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    send_telegram_message(
        f"⏳ *Generating Evening P&L Report for {date_str}...*\n"
        f"📊 Evaluating 1-minute intraday price action per share (+₹2 / -₹1) and retraining AI model...",
        target_chat_id=chat_id
    )
    try:
        main.run_evening_mode(date_str, send_telegram=True, target_chat_id=chat_id)
    except Exception as e:
        send_telegram_message(f"❌ Error during evening analysis: {e}", target_chat_id=chat_id)

def _execute_news_command(chat_id: str):
    """Worker to fetch and deliver live market news and global cues."""
    from market_news import get_market_context_summary
    send_telegram_message("🌐 *Fetching live US/Singapore market cues and top headlines...*", target_chat_id=chat_id)
    try:
        ctx = get_market_context_summary()
        tone_badge = "🟢 BULLISH" if ctx['overall_tone'] == "BULLISH" else ("🔴 BEARISH" if ctx['overall_tone'] == "BEARISH" else "🟡 MIXED/NEUTRAL")
        lines = []
        lines.append(f"🌐 *GLOBAL MARKET CUES & PRE-MARKET SENTIMENT*")
        lines.append(f"• *Market Tone:* {tone_badge}")
        lines.append("───────────────────────────")
        if ctx.get("summary_text"):
            lines.append(ctx["summary_text"])
            lines.append("")
        
        lines.append("📰 *Top Financial News (Moneycontrol & TOI):*")
        for item in ctx.get("news_items", [])[:5]:
            lines.append(f"  • *[{item['source']}]* _{item['title']}_")
        
        send_telegram_message("\n".join(lines), target_chat_id=chat_id)
    except Exception as e:
        send_telegram_message(f"❌ Error fetching news cues: {e}", target_chat_id=chat_id)

def handle_telegram_callback_query(cq: dict):
    """Handle click events on inline keyboard buttons."""
    cq_id = cq.get("id")
    from_user = cq.get("from", {})
    msg = cq.get("message", {})
    chat_id = str(msg.get("chat", {}).get("id"))
    data = cq.get("data", "").strip()

    # Acknowledge callback to stop loading spinner in Telegram
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": cq_id, "text": f"Executing {data}..."}
        )
    except Exception:
        pass

    # Treat callback_data as command
    handle_telegram_message({"chat": {"id": chat_id}, "text": data})

def handle_telegram_message(msg: dict):
    """Handle an incoming message update from Telegram."""
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id"))
    text = msg.get("text", "").strip()

    if not text:
        return

    # Extract command or text button
    parts = text.split()
    raw_cmd = parts[0].lower()
    cmd = raw_cmd.split("@")[0]
    args = parts[1:]

    # Support button labels from persistent keyboard
    clean_lower = text.lower()
    if "morning" in clean_lower and not cmd.startswith("/"):
        cmd = "/morning"
    elif "status" in clean_lower and not cmd.startswith("/"):
        cmd = "/status"
    elif (
        "full pipeline" in clean_lower or
        "full cycle" in clean_lower or
        "start pipeline" in clean_lower or
        "full-cycle" in clean_lower or
        "fullcycle" in clean_lower or
        "full_pipeline" in clean_lower or
        "pipeline" in clean_lower
    ) and not clean_lower.startswith("stop") and not cmd.startswith("/"):
        cmd = "/full_cycle"
    elif "stop pipeline" in clean_lower and not cmd.startswith("/"):
        cmd = "/stop_pipeline"
    elif "news" in clean_lower and not cmd.startswith("/"):
        cmd = "/news"
    elif "evening" in clean_lower and not cmd.startswith("/"):
        cmd = "/evening"
    elif "menu" in clean_lower and not cmd.startswith("/"):
        cmd = "/menu"

    # Normalize command aliases to trigger full cycle
    if cmd in ["/full_cycle", "/full_pipeline", "/pipeline", "/full-cycle", "/fullcycle", "/start_pipeline"]:
        cmd = "/full_cycle"

    if cmd in ["/start", "/help", "/menu"]:
        send_control_panel(chat_id)

    elif cmd == "/morning":
        threading.Thread(target=_execute_morning_command, args=(chat_id,), daemon=True).start()

    elif cmd == "/evening":
        threading.Thread(target=_execute_evening_command, args=(chat_id,), daemon=True).start()

    elif cmd == "/full_cycle":
        state = set_pipeline_state(True, source=f"Telegram ({chat_id})")
        threading.Thread(target=_execute_full_cycle_command, args=(chat_id,), daemon=True).start()

    elif cmd == "/news":
        threading.Thread(target=_execute_news_command, args=(chat_id,), daemon=True).start()

    elif cmd == "/stop_pipeline":
        state = set_pipeline_state(False, source=f"Telegram ({chat_id})")
        reply = (
            "⏸️ *Automated Trading Pipeline STOPPED!* 🛑\n\n"
            "Daily automatic morning predictions and 1-minute intraday tracking are now PAUSED.\n\n"
            "• You can still trigger on-demand predictions manually anytime using `/morning` or `/full_pipeline`!\n"
            "• To resume automated schedule and run full cycle, send `/full_pipeline`."
        )
        send_telegram_message(reply, target_chat_id=chat_id)

    elif cmd == "/status":
        from zoneinfo import ZoneInfo
        ist_now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
        is_weekday = ist_now.weekday() < 5
        pipeline_status = get_pipeline_status_text()
        
        gemini_ready = is_gemini_configured()
        gemini_badge = "🟢 CONNECTED (Active)" if gemini_ready else "🔴 NOT CONFIGURED (Provide via /set_key)"
        
        status_msg = (
            f"📊 *SYSTEM STATUS & PIPELINE OVERVIEW*\n"
            f"───────────────────────────\n"
            f"📅 *Current IST Time:* {ist_now.strftime('%Y-%m-%d %H:%M:%S IST')}\n"
            f"🏛️ *Market Day:* {'Yes (Weekday)' if is_weekday else 'No (Weekend)'}\n\n"
            f"{pipeline_status}\n\n"
            f"🧠 *Google Gemini AI:* {gemini_badge}\n"
            f"🎯 *Universe:* Top Indian Stocks < ₹500 (Assumed ₹25k Allocation per Stock)\n"
            f"⚡ *Strategy:* Pre-10am (+₹10) | Post-10am Target (+₹2) / Stop Loss (-₹1)\n"
            f"───────────────────────────\n"
            f"Send `/morning` to run predictions, `/full_pipeline` for full cycle, or `/help` for commands."
        )
        send_telegram_message(status_msg, target_chat_id=chat_id)

    elif cmd == "/set_key":
        if not args:
            send_telegram_message(
                "⚠️ *Usage:* `/set_key <YOUR_GEMINI_API_KEY>`\n"
                "Get a free Gemini API key from https://aistudio.google.com and send it here.",
                target_chat_id=chat_id
            )
        else:
            new_key = args[0].strip()
            success = update_gemini_api_key(new_key)
            if success:
                send_telegram_message(
                    "🎉 *Gemini API Key Successfully Updated & Saved!* 🧠\n"
                    "Google Gemini AI is now enabled for highest-confidence Indian stock predictions.",
                    target_chat_id=chat_id
                )
            else:
                send_telegram_message("❌ Invalid key format. Please check your Gemini API key.", target_chat_id=chat_id)

    else:
        # Fallback for unrecognized messages or casual chat
        fallback_msg = (
            f"🤖 *Received:* `{text}`\n\n"
            "Here are the available actions:\n"
            "• 🌅 `/morning` — Run Morning Prediction (< ₹500)\n"
            "• 🔄 `/full_pipeline` — Run Full Pipeline (Morning + 1m Monitor + Evening)\n"
            "• 🌆 `/evening` — Evening P&L & Retraining\n"
            "• 📊 `/status` — View Pipeline & AI Status\n"
            "• 🌐 `/news` — US & Singapore Cues + News\n"
            "• ⏸️ `/stop_pipeline` — Pause Daily Schedule\n\n"
            "👇 *Or simply tap any button below:*"
        )
        send_telegram_message(fallback_msg, target_chat_id=chat_id, reply_markup=get_control_panel_inline_markup())

def run_telegram_listener():
    """
    Continuous long-polling listener for incoming Telegram commands.
    Allows users to interactively type /morning, /start_pipeline, /stop_pipeline, /status, etc.
    """
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN not configured. Interactive Telegram listener cannot start.")
        return

    register_bot_commands()
    print("🤖 Telegram Bot Interactive Command Listener started (Listening for /morning, /start_pipeline, /stop_pipeline)...")

    offset = None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

    while not _stop_event.is_set():
        params = {"timeout": 15}
        if offset is not None:
            params["offset"] = offset

        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        if "message" in update:
                            handle_telegram_message(update["message"])
                        elif "callback_query" in update:
                            handle_telegram_callback_query(update["callback_query"])
            elif resp.status_code == 409:
                print("⚠️ Another Telegram bot instance is running. Waiting 10s...")
                time.sleep(10)
            else:
                time.sleep(2)
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            time.sleep(3)

def start_telegram_bot_background():
    """Start Telegram bot listener in a non-blocking background daemon thread."""
    global _bot_listener_thread
    if _bot_listener_thread and _bot_listener_thread.is_alive():
        return
    _stop_event.clear()
    _bot_listener_thread = threading.Thread(target=run_telegram_listener, daemon=True, name="TelegramBotListener")
    _bot_listener_thread.start()
    return _bot_listener_thread

def get_telegram_chat_ids() -> list:
    """Fetch recent chat updates to discover group/channel/user Chat IDs."""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN not configured.")
        return []

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        res_json = response.json()
        if not res_json.get("ok"):
            print(f"❌ Error fetching updates: {res_json.get('description')}")
            return []

        chats = {}
        for update in res_json.get("result", []):
            for key in ["message", "my_chat_member", "channel_post", "edited_message"]:
                if key in update and "chat" in update[key]:
                    c = update[key]["chat"]
                    cid = c.get("id")
                    title = c.get("title") or c.get("first_name") or f"Chat {cid}"
                    ctype = c.get("type", "unknown")
                    chats[cid] = {"id": cid, "title": title, "type": ctype}

        print("\n🔍 Discovered Telegram Chats/Groups:")
        if not chats:
            print("  No recent chats found. Make sure to send a message in your group or add the bot as Admin first!")
        else:
            for cid, info in chats.items():
                print(f"  • Title: '{info['title']}' | Type: {info['type']} | Chat ID: {info['id']}")
        return list(chats.values())
    except Exception as e:
        print(f"❌ Network error fetching Telegram updates: {e}")
        return []

def test_telegram_connection() -> bool:
    """Send test message to confirm Telegram bot configuration."""
    test_msg = (
        "🤖 *Tech Stock Gain Predictor Bot Connected!* 🎉\n"
        "Your Telegram channel/group is configured.\n\n"
        "Available Interactive Commands:\n"
        "• `/morning` - Trigger Morning Prediction (< ₹500)\n"
        "• `/start_pipeline` - Start daily automated trading\n"
        "• `/stop_pipeline` - Pause daily trading\n"
        "• `/status` - Check current status\n"
        "• `/news` - US & Singapore market cues"
    )
    return send_telegram_message(test_msg)

if __name__ == "__main__":
    print("Starting interactive Telegram Bot listener...")
    run_telegram_listener()
