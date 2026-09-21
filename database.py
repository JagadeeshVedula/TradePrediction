import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH, SUPABASE_URL, SUPABASE_KEY

# Optional Supabase import for cloud hosting
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False
    Client = Any

def get_supabase_client() -> Optional[Client]:
    """Return an authenticated Supabase client if configured."""
    if HAS_SUPABASE_LIB and SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"Notice: Failed connecting to Supabase ({e}). Falling back to SQLite.")
            return None
    return None

def get_sqlite_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialize local SQLite tables if running in local mode."""
    sb = get_supabase_client()
    if sb:
        print("⚡ Connected to Supabase Cloud Database.")
        return

    # Fallback SQLite init
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                rank INTEGER NOT NULL,
                starting_price REAL NOT NULL,
                expected_gain_pct REAL NOT NULL,
                target_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                confidence_score REAL NOT NULL,
                signal_reasons TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, ticker)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                starting_price REAL NOT NULL,
                close_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                actual_gain_pct REAL NOT NULL,
                max_gain_pct REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, ticker)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_retraining_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                samples_count INTEGER NOT NULL,
                mae REAL,
                win_rate_pct REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

def save_predictions(date_str: str, predictions: List[Dict[str, Any]]) -> None:
    """Save top predicted tech stocks into Supabase or SQLite."""
    sb = get_supabase_client()
    if sb:
        try:
            sb.table("predictions").delete().eq("date", date_str).execute()
            records = []
            for p in predictions:
                records.append({
                    'date': date_str,
                    'ticker': p['ticker'],
                    'rank': p['rank'],
                    'starting_price': float(p['starting_price']),
                    'expected_gain_pct': float(p['expected_gain_pct']),
                    'target_price': float(p['target_price']),
                    'stop_loss': float(p['stop_loss']),
                    'confidence_score': float(p['confidence_score']),
                    'signal_reasons': p.get('signal_reasons', '')
                })
            if records:
                sb.table("predictions").insert(records).execute()
            print(f"☁️ Saved {len(records)} predictions to Supabase for date {date_str}.")
            return
        except Exception as e:
            print(f"Error saving predictions to Supabase ({e}). Falling back to SQLite.")

    # SQLite Fallback
    init_db()
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM predictions WHERE date = ?", (date_str,))
        for p in predictions:
            cursor.execute('''
                INSERT INTO predictions 
                (date, ticker, rank, starting_price, expected_gain_pct, target_price, stop_loss, confidence_score, signal_reasons)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                p['ticker'],
                p['rank'],
                p['starting_price'],
                p['expected_gain_pct'],
                p['target_price'],
                p['stop_loss'],
                p['confidence_score'],
                p.get('signal_reasons', '')
            ))
        conn.commit()

def get_predictions_by_date(date_str: str) -> List[Dict[str, Any]]:
    """Retrieve predictions stored for a given date."""
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("predictions").select("*").eq("date", date_str).order("rank", desc=False).limit(5).execute()
            if res.data:
                return res.data
        except Exception as e:
            print(f"Error fetching predictions from Supabase ({e}). Falling back to SQLite.")

    # SQLite Fallback
    init_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE date = ? ORDER BY rank ASC LIMIT 5", (date_str,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def save_outcomes(date_str: str, outcomes: List[Dict[str, Any]]) -> None:
    """Save post-close market actual outcomes."""
    sb = get_supabase_client()
    if sb:
        try:
            sb.table("outcomes").delete().eq("date", date_str).execute()
            records = []
            for o in outcomes:
                records.append({
                    'date': date_str,
                    'ticker': o['ticker'],
                    'starting_price': float(o['starting_price']),
                    'close_price': float(o['close_price']),
                    'high_price': float(o['high_price']),
                    'low_price': float(o['low_price']),
                    'actual_gain_pct': float(o['actual_gain_pct']),
                    'max_gain_pct': float(o['max_gain_pct']),
                    'status': o['status']
                })
            if records:
                sb.table("outcomes").insert(records).execute()
            print(f"☁️ Saved {len(records)} outcomes to Supabase for date {date_str}.")
            return
        except Exception as e:
            print(f"Error saving outcomes to Supabase ({e}). Falling back to SQLite.")

    # SQLite Fallback
    init_db()
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM outcomes WHERE date = ?", (date_str,))
        for o in outcomes:
            cursor.execute('''
                INSERT INTO outcomes 
                (date, ticker, starting_price, close_price, high_price, low_price, actual_gain_pct, max_gain_pct, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date_str,
                o['ticker'],
                o['starting_price'],
                o['close_price'],
                o['high_price'],
                o['low_price'],
                o['actual_gain_pct'],
                o['max_gain_pct'],
                o['status']
            ))
        conn.commit()

def get_outcomes_by_date(date_str: str) -> List[Dict[str, Any]]:
    """Retrieve actual outcomes recorded for a given date."""
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("outcomes").select("*").eq("date", date_str).execute()
            if res.data:
                return res.data
        except Exception as e:
            print(f"Error fetching outcomes from Supabase ({e}). Falling back to SQLite.")

    # SQLite Fallback
    init_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outcomes WHERE date = ?", (date_str,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def log_retraining(date_str: str, samples_count: int, mae: float, win_rate_pct: float, notes: str = "") -> None:
    """Log retraining metrics into audit table."""
    sb = get_supabase_client()
    if sb:
        try:
            record = {
                'date': date_str,
                'samples_count': samples_count,
                'mae': float(mae),
                'win_rate_pct': float(win_rate_pct),
                'notes': notes
            }
            sb.table("model_retraining_log").insert(record).execute()
            print(f"☁️ Logged retraining performance to Supabase for date {date_str}.")
            return
        except Exception as e:
            print(f"Error logging retraining to Supabase ({e}). Falling back to SQLite.")

    # SQLite Fallback
    init_db()
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO model_retraining_log (date, samples_count, mae, win_rate_pct, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (date_str, samples_count, mae, win_rate_pct, notes))
        conn.commit()

def get_all_matched_records() -> List[Dict[str, Any]]:
    """Get paired prediction and outcome history for retraining evaluations."""
    sb = get_supabase_client()
    if sb:
        try:
            preds = sb.table("predictions").select("date, ticker, starting_price, expected_gain_pct, confidence_score").execute().data or []
            outs = sb.table("outcomes").select("date, ticker, close_price, high_price, low_price, actual_gain_pct, status").execute().data or []
            
            out_dict = {(o['date'], o['ticker']): o for o in outs}
            matched = []
            for p in preds:
                key = (p['date'], p['ticker'])
                if key in out_dict:
                    o = out_dict[key]
                    combined = {**p, **o}
                    matched.append(combined)
            return sorted(matched, key=lambda x: x['date'])
        except Exception as e:
            print(f"Error fetching matched records from Supabase ({e}). Falling back to SQLite.")

    # SQLite Fallback
    init_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.date, p.ticker, p.starting_price, p.expected_gain_pct, p.confidence_score,
                   o.close_price, o.high_price, o.low_price, o.actual_gain_pct, o.status
            FROM predictions p
            INNER JOIN outcomes o ON p.date = o.date AND p.ticker = o.ticker
            ORDER BY p.date ASC
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
