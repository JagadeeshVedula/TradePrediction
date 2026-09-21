import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(text: str) -> bool:
    """Send formatted text message to Telegram channel, group, or chat (supports comma-separated chat IDs)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram Bot Token or Chat ID not configured in .env file.")
        print("💡 Message was NOT sent to Telegram channel. See .env.example for instructions.")
        return False

    chat_ids = [cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(",") if cid.strip()]
    if not chat_ids:
        print("⚠️ No valid TELEGRAM_CHAT_ID found.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    overall_success = True

    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            res_json = response.json()
            
            if response.status_code == 200 and res_json.get("ok"):
                print(f"🚀 Report successfully posted to Telegram Chat/Group ({chat_id})!")
            else:
                # Try sending without parse_mode if Markdown parsing failed
                print(f"⚠️ Telegram Markdown delivery failed for {chat_id} ({res_json.get('description')}). Retrying as plain text...")
                payload.pop("parse_mode", None)
                res_plain = requests.post(url, json=payload, timeout=10)
                if res_plain.status_code == 200 and res_plain.json().get("ok"):
                    print(f"🚀 Report posted to Telegram Chat/Group ({chat_id}) as Plain Text!")
                else:
                    print(f"❌ Failed to send Telegram message to {chat_id}: {res_plain.text}")
                    overall_success = False
        except Exception as e:
            print(f"❌ Network error sending message to Telegram ({chat_id}): {e}")
            overall_success = False

    return overall_success


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
    test_msg = "🤖 *Tech Stock Gain Predictor Bot Connected!* 🎉\nYour Telegram channel/group is successfully configured to receive morning predictions & post-close retraining reports."
    return send_telegram_message(test_msg)

