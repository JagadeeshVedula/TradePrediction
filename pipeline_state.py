import json
import os
import sys
import datetime
from typing import Dict, Any

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

STATE_FILE = "pipeline_state.json"

DEFAULT_STATE = {
    "enabled": True,
    "status": "RUNNING",
    "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "updated_by": "System",
    "notes": "Daily Indian Stock Trading AI Pipeline active."
}

def load_pipeline_state() -> Dict[str, Any]:
    """Load current state from file, or initialize with defaults."""
    if not os.path.exists(STATE_FILE):
        save_pipeline_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception:
        return DEFAULT_STATE.copy()

def save_pipeline_state(state: Dict[str, Any]) -> None:
    """Save state dictionary to JSON file."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving pipeline state: {e}")

def is_pipeline_enabled() -> bool:
    """Check if automated scheduler pipeline is enabled."""
    state = load_pipeline_state()
    return bool(state.get("enabled", True))

def set_pipeline_state(enabled: bool, source: str = "Telegram") -> Dict[str, Any]:
    """Enable or stop the pipeline."""
    state = {
        "enabled": enabled,
        "status": "RUNNING" if enabled else "STOPPED",
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_by": source,
        "notes": "Pipeline enabled by user" if enabled else "Pipeline stopped/paused by user"
    }
    save_pipeline_state(state)
    return state

def get_pipeline_status_text() -> str:
    """Generate a clean human-readable summary of pipeline state."""
    state = load_pipeline_state()
    status_icon = "🟢 RUNNING" if state.get("enabled") else "🔴 STOPPED (PAUSED)"
    return (
        f"🤖 *Pipeline Status:* {status_icon}\n"
        f"🕒 *Last Modified:* {state.get('updated_at', 'N/A')} by {state.get('updated_by', 'System')}\n"
        f"📝 *Note:* {state.get('notes', '')}"
    )
