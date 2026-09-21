import yfinance as yf
import pandas as pd
import numpy as np
import datetime
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
        # Fetch last 5 days to ensure target_date candle is captured
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if df.empty:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Match date string in index
        df.index = pd.to_datetime(df.index)
        
        # Match exact date or latest available bar if market just closed
        matching_rows = df[df.index.strftime('%Y-%m-%d') == target_date_str]

        if matching_rows.empty:
            # Fallback to the latest available bar
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
