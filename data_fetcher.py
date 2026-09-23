import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Tuple, Optional

def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical indicators and predictive feature set on stock dataframe."""
    df = df.copy()
    
    # Ensure correct column names from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df['Close']
    high = df['High']
    low = df['Low']
    open_p = df['Open']
    volume = df['Volume']

    # 1. RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi_14'] = 100 - (100 / (1 + rs))

    # 2. MACD
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema_12 - ema_26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # 3. Moving Averages
    df['ema_9_diff'] = (close - close.ewm(span=9, adjust=False).mean()) / close * 100
    df['ema_20_diff'] = (close - close.ewm(span=20, adjust=False).mean()) / close * 100
    df['sma_50_diff'] = (close - close.rolling(window=50).mean()) / close * 100

    # 4. Volatility & ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr_pct'] = (tr.rolling(14).mean() / close) * 100

    # 5. Volume indicators
    vol_sma20 = volume.rolling(window=20).mean()
    df['volume_ratio'] = volume / (vol_sma20 + 1e-9)

    # 6. Price Momentum
    df['momentum_1d'] = close.pct_change(1) * 100
    df['momentum_3d'] = close.pct_change(3) * 100
    df['momentum_5d'] = close.pct_change(5) * 100
    df['gap_pct'] = (open_p - close.shift(1)) / (close.shift(1) + 1e-9) * 100
    df['intraday_range'] = (high - low) / (low + 1e-9) * 100

    # Target variable for ML model training: Next day's gain percentage
    # (Next_Close - Next_Open) / Next_Open * 100
    df['target_daily_gain'] = ((close.shift(-1) - open_p.shift(-1)) / (open_p.shift(-1) + 1e-9)) * 100
    df['target_max_gain'] = ((high.shift(-1) - open_p.shift(-1)) / (open_p.shift(-1) + 1e-9)) * 100

    return df

FEATURE_COLUMNS = [
    'rsi_14', 'macd', 'macd_signal', 'macd_hist',
    'ema_9_diff', 'ema_20_diff', 'sma_50_diff',
    'atr_pct', 'volume_ratio', 'momentum_1d',
    'momentum_3d', 'momentum_5d', 'gap_pct', 'intraday_range'
]

def normalize_ticker(ticker: str) -> str:
    """Ensure Indian stock tickers have proper NSE (.NS) or BSE (.BO) suffix."""
    ticker = ticker.strip().upper()
    if not (ticker.endswith('.NS') or ticker.endswith('.BO')):
        return f"{ticker}.NS"
    return ticker

def _to_scalar(val) -> float:
    """Safely convert pandas Series, numpy array, or scalar to float."""
    if hasattr(val, 'iloc'):
        val = val.iloc[0]
    elif isinstance(val, (np.ndarray, list)):
        val = val[0]
    return float(val)

def fetch_latest_ticker_features(ticker: str, lookback_days: int = 120) -> Optional[Dict[str, Any]]:
    """Fetch latest data for an Indian stock ticker and extract latest feature row and starting price."""
    ticker = normalize_ticker(ticker)
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty or len(df) < 35:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df_ind = compute_technical_indicators(df)
        df_clean = df_ind.dropna(subset=FEATURE_COLUMNS)
        if df_clean.empty:
            return None
            
        latest_row = df_clean.iloc[-1]
        
        # Get starting (Open / Current) price
        starting_price = _to_scalar(df['Open'].iloc[-1])
        if pd.isna(starting_price) or starting_price <= 0:
            starting_price = _to_scalar(df['Close'].iloc[-1])
            
        features = {col: _to_scalar(latest_row[col]) for col in FEATURE_COLUMNS}
        
        return {
            'ticker': ticker,
            'starting_price': starting_price,
            'features': features,
            'date': str(latest_row.name.strftime('%Y-%m-%d')) if hasattr(latest_row.name, 'strftime') else str(datetime.date.today())
        }
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None


def fetch_historical_training_dataset(tickers: list, period: str = "2y") -> Tuple[pd.DataFrame, pd.Series]:
    """Fetch multi-year historical dataset across Indian stock universe for training ML model."""
    all_features = []
    all_targets = []

    for raw_ticker in tickers:
        ticker = normalize_ticker(raw_ticker)
        try:
            df = yf.download(ticker, period=period, interval="1d", progress=False)
            if df.empty or len(df) < 50:
                continue
            
            df_ind = compute_technical_indicators(df)
            # Drop rows where feature columns or target daily gain is NaN
            df_clean = df_ind.dropna(subset=FEATURE_COLUMNS + ['target_daily_gain'])
            
            if not df_clean.empty:
                X_part = df_clean[FEATURE_COLUMNS]
                y_part = df_clean['target_daily_gain']
                all_features.append(X_part)
                all_targets.append(y_part)
        except Exception as e:
            print(f"Failed loading training history for {ticker}: {e}")

    if not all_features:
        return pd.DataFrame(), pd.Series()

    X_train = pd.concat(all_features, ignore_index=True)
    y_train = pd.concat(all_targets, ignore_index=True)
    return X_train, y_train

def fetch_market_close_actuals(ticker: str, target_date_str: str) -> Optional[Dict[str, Any]]:
    """Fetch actual market close prices and calculate gain/loss for an Indian stock on target date."""
    ticker = normalize_ticker(ticker)
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df.empty:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = pd.to_datetime(df.index)
        matching_rows = df[df.index.strftime('%Y-%m-%d') == target_date_str]

        today_str = datetime.date.today().strftime('%Y-%m-%d')
        now = datetime.datetime.now()

        if matching_rows.empty:
            # If target date is today and market has not opened yet (before 09:15 AM), do not fallback to yesterday
            if target_date_str == today_str and (now.hour < 9 or (now.hour == 9 and now.minute < 15)):
                return None
            # Fallback to the latest available bar for past dates
            matching_rows = df.iloc[-1:]

        row = matching_rows.iloc[-1]
        open_price = _to_scalar(row['Open'])
        close_price = _to_scalar(row['Close'])
        high_price = _to_scalar(row['High'])
        low_price = _to_scalar(row['Low'])

        actual_gain_pct = round(((close_price - open_price) / open_price) * 100, 2)
        max_gain_pct = round(((high_price - open_price) / open_price) * 100, 2)

        status = "GAIN" if actual_gain_pct > 0 else "FALL"
        if max_gain_pct >= 2.0:
            status = "TARGET_MET"

        return {
            'ticker': ticker,
            'starting_price': round(open_price, 2),
            'close_price': round(close_price, 2),
            'high_price': round(high_price, 2),
            'low_price': round(low_price, 2),
            'actual_gain_pct': actual_gain_pct,
            'max_gain_pct': max_gain_pct,
            'status': status
        }
    except Exception as e:
        print(f"Error fetching market close actuals for {ticker}: {e}")
        return None

def fetch_intraday_1m_data(ticker: str) -> pd.DataFrame:
    """Fetch 1-minute interval intraday stock price bars for current trading session."""
    ticker = normalize_ticker(ticker)
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty:
            df = yf.download(ticker, period="5d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Error fetching 1m intraday data for {ticker}: {e}")
        return pd.DataFrame()

def evaluate_intraday_trade_1m(
    ticker: str,
    entry_price: float,
    target_date_str: str,
    target_rupees: float = 1.0,
    stop_loss_rupees: float = 3.0,
    pre_10am_target_rupees: float = 10.0
) -> Dict[str, Any]:
    """
    Evaluate intraday price action minute-by-minute against updated strategy rules:
    - Before 10:00 AM IST: Only sell if stock rises by +10 Rupees (EARLY_TARGET_MET).
    - After 10:00 AM IST: Normal +1 Rupee Target & -3 Rupee Stop Loss rules apply.
    Returns exact exit price, exit timestamp, exit reason, and per-share P&L.
    """
    ticker = normalize_ticker(ticker)
    ist = ZoneInfo("Asia/Kolkata")
    target_price = round(entry_price + target_rupees, 2)
    early_target_price = round(entry_price + pre_10am_target_rupees, 2)
    stop_loss_price = round(entry_price - stop_loss_rupees, 2)

    now_ist = datetime.datetime.now(ist)
    today_str = now_ist.strftime('%Y-%m-%d')

    # If target date is today and market has not opened yet (before 09:15 AM IST)
    if target_date_str == today_str and (now_ist.hour < 9 or (now_ist.hour == 9 and now_ist.minute < 15)):
        return {
            'ticker': ticker,
            'entry_price': entry_price,
            'exit_price': entry_price,
            'high_price': entry_price,
            'low_price': entry_price,
            'close_price': entry_price,
            'exit_reason': "MARKET_NOT_OPEN_YET",
            'exit_time': "PENDING (Open @ 09:15)",
            'pnl_per_share': 0.0
        }

    df_1m = fetch_intraday_1m_data(ticker)
    
    # Filter 1m bars for target date
    if not df_1m.empty:
        df_1m.index = pd.to_datetime(df_1m.index)
        matching_bars = df_1m[df_1m.index.strftime('%Y-%m-%d') == target_date_str]
    else:
        matching_bars = pd.DataFrame()

    if matching_bars.empty:
        # Check daily actuals for past dates
        daily_actuals = fetch_market_close_actuals(ticker, target_date_str)
        if daily_actuals:
            close_p = daily_actuals['close_price']
            high_p = daily_actuals['high_price']
            low_p = daily_actuals['low_price']

            if high_p >= early_target_price:
                exit_price = early_target_price
                exit_reason = f"EARLY_TARGET_MET (+₹{pre_10am_target_rupees:g})"
            elif high_p >= target_price:
                exit_price = target_price
                exit_reason = f"TARGET_MET (+₹{target_rupees:g})"
            elif low_p <= stop_loss_price:
                exit_price = stop_loss_price
                exit_reason = f"STOP_LOSS_HIT (-₹{stop_loss_rupees:g})"
            else:
                exit_price = close_p
                exit_reason = "MARKET_CLOSE"

            pnl_per_share = round(exit_price - entry_price, 2)
            return {
                'ticker': ticker,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'high_price': high_p,
                'low_price': low_p,
                'close_price': close_p,
                'exit_reason': exit_reason,
                'exit_time': 'EOD',
                'pnl_per_share': pnl_per_share
            }
        else:
            # Session pending or no bars recorded yet
            return {
                'ticker': ticker,
                'entry_price': entry_price,
                'exit_price': entry_price,
                'high_price': entry_price,
                'low_price': entry_price,
                'close_price': entry_price,
                'exit_reason': "SESSION_PENDING",
                'exit_time': "PENDING",
                'pnl_per_share': 0.0
            }

    exit_price = None
    exit_reason = "MARKET_CLOSE"
    exit_time = "15:30"
    high_seen = entry_price
    low_seen = entry_price

    for idx, row in matching_bars.iterrows():
        bar_high = _to_scalar(row['High'])
        bar_low = _to_scalar(row['Low'])
        bar_close = _to_scalar(row['Close'])
        
        # Convert index timestamp to IST
        idx_dt = idx
        if hasattr(idx, 'tz_convert'):
            if idx.tz is None:
                idx_dt = idx.tz_localize(ist)
            else:
                idx_dt = idx.tz_convert(ist)
        elif hasattr(idx, 'tz_localize'):
            idx_dt = idx.tz_localize('UTC').tz_convert(ist)

        bar_time_obj = idx_dt.time() if hasattr(idx_dt, 'time') else None
        time_str = idx_dt.strftime('%H:%M') if hasattr(idx_dt, 'strftime') else '15:30'

        if bar_high > high_seen:
            high_seen = bar_high
        if bar_low < low_seen:
            low_seen = bar_low

        is_before_10am = bar_time_obj is not None and bar_time_obj < datetime.time(10, 0)

        if is_before_10am:
            # Before 10:00 AM IST: ONLY exit if price reaches +₹10 gain
            if bar_high >= early_target_price:
                exit_price = early_target_price
                exit_reason = f"EARLY_TARGET_MET (+₹{pre_10am_target_rupees:g})"
                exit_time = time_str
                break
        else:
            # After 10:00 AM IST: Target & Stop Loss rules
            if bar_high >= target_price:
                exit_price = target_price
                exit_reason = f"TARGET_MET (+₹{target_rupees:g})"
                exit_time = time_str
                break

            if bar_low <= stop_loss_price:
                exit_price = stop_loss_price
                exit_reason = f"STOP_LOSS_HIT (-₹{stop_loss_rupees:g})"
                exit_time = time_str
                break

    # If neither triggered during session, exit at final bar close
    if exit_price is None:
        last_row = matching_bars.iloc[-1]
        exit_price = round(_to_scalar(last_row['Close']), 2)
        exit_reason = "MARKET_CLOSE"
        exit_time = "15:30"

    pnl_per_share = round(exit_price - entry_price, 2)

    return {
        'ticker': ticker,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'high_price': round(high_seen, 2),
        'low_price': round(low_seen, 2),
        'close_price': round(_to_scalar(matching_bars.iloc[-1]['Close']), 2),
        'exit_reason': exit_reason,
        'exit_time': exit_time,
        'pnl_per_share': pnl_per_share
    }


