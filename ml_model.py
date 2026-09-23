import os
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import joblib
import pandas as pd
import numpy as np

from typing import List, Dict, Any, Tuple
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error

from config import (
    MODEL_PATH, SCALER_PATH, DEFAULT_GAIN_TARGET_PCT, DEFAULT_STOP_LOSS_PCT,
    TOP_N_PREDICTIONS, SUPABASE_BUCKET, MAX_STOCK_PRICE, INVESTMENT_PER_STOCK,
    PROFIT_TARGET_INR, STOP_LOSS_INR
)
from data_fetcher import (
    FEATURE_COLUMNS,
    fetch_latest_ticker_features,
    fetch_historical_training_dataset,
    fetch_market_close_actuals,
    evaluate_intraday_trade_1m
)
from database import (
    save_predictions,
    save_outcomes,
    get_predictions_by_date,
    get_outcomes_by_date,
    log_retraining,
    get_all_matched_records,
    get_supabase_client
)

class TechStockPredictor:
    def __init__(self):
        self.model_rf = None
        self.model_gb = None
        self.scaler = None
        self.load_model()

    def load_model(self):
        """Load trained ML model ensemble and scaler from disk or Supabase Storage."""
        sb = get_supabase_client()
        if sb:
            try:
                model_bytes = sb.storage.from_(SUPABASE_BUCKET).download("stock_model.pkl")
                scaler_bytes = sb.storage.from_(SUPABASE_BUCKET).download("scaler.pkl")
                
                if model_bytes and scaler_bytes:
                    with open(MODEL_PATH, "wb") as f:
                        f.write(model_bytes)
                    with open(SCALER_PATH, "wb") as f:
                        f.write(scaler_bytes)
                    print(f"☁️ Downloaded ML model files from Supabase Storage bucket '{SUPABASE_BUCKET}'.")
            except Exception as e:
                print(f"Notice: Storage download ({e}). Checking local files...")

        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                saved = joblib.load(MODEL_PATH)
                self.model_rf = saved.get('rf')
                self.model_gb = saved.get('gb')
                self.scaler = joblib.load(SCALER_PATH)
            except Exception as e:
                print(f"Notice: Failed loading saved model ({e}). Will build model on demand.")

    def save_model(self):
        """Save model ensemble and scaler to disk and upload to Supabase Storage."""
        if self.model_rf and self.model_gb and self.scaler:
            joblib.dump({'rf': self.model_rf, 'gb': self.model_gb}, MODEL_PATH)
            joblib.dump(self.scaler, SCALER_PATH)

            sb = get_supabase_client()
            if sb:
                try:
                    with open(MODEL_PATH, "rb") as f:
                        m_bytes = f.read()
                    with open(SCALER_PATH, "rb") as f:
                        s_bytes = f.read()

                    try:
                        sb.storage.from_(SUPABASE_BUCKET).upload(path="stock_model.pkl", file=m_bytes, file_options={"upsert": "true"})
                    except Exception:
                        sb.storage.from_(SUPABASE_BUCKET).update(path="stock_model.pkl", file=m_bytes)

                    try:
                        sb.storage.from_(SUPABASE_BUCKET).upload(path="scaler.pkl", file=s_bytes, file_options={"upsert": "true"})
                    except Exception:
                        sb.storage.from_(SUPABASE_BUCKET).update(path="scaler.pkl", file=s_bytes)

                    print(f"☁️ Uploaded ML model files to Supabase Storage bucket '{SUPABASE_BUCKET}'.")
                except Exception as e:
                    print(f"Notice: Failed uploading model to Supabase Storage ({e}).")

    def train_baseline(self, universe_tickers: List[str]) -> Tuple[float, int]:
        """Train baseline ML model ensemble on historical multi-year stock data."""
        print("📥 Downloading multi-year historical dataset for Indian stocks...")
        X, y = fetch_historical_training_dataset(universe_tickers, period="2y")
        
        if X.empty or len(X) < 100:
            raise ValueError("Insufficient historical stock data fetched for training model.")

        print(f"📊 Training Ensemble Model on {len(X)} historical samples...")
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model_rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
        self.model_gb = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)

        self.model_rf.fit(X_scaled, y)
        self.model_gb.fit(X_scaled, y)

        preds_rf = self.model_rf.predict(X_scaled)
        preds_gb = self.model_gb.predict(X_scaled)
        preds_ensemble = (preds_rf + preds_gb) / 2.0
        
        mae = float(mean_absolute_error(y, preds_ensemble))
        self.save_model()
        print(f"✅ Training completed. Baseline Model MAE: {mae:.4f}")
        return mae, len(X)

    def _generate_signal_reason(self, features: Dict[str, float]) -> str:
        """Generate human-readable technical rationale for prediction."""
        reasons = []
        rsi = features.get('rsi_14', 50)
        macd_hist = features.get('macd_hist', 0)
        ema9_diff = features.get('ema_9_diff', 0)
        vol_ratio = features.get('volume_ratio', 1.0)
        mom1d = features.get('momentum_1d', 0)

        if rsi > 50 and rsi < 70:
            reasons.append(f"Bullish RSI ({rsi:.1f})")
        elif rsi <= 40:
            reasons.append(f"Oversold Bounce RSI ({rsi:.1f})")
            
        if macd_hist > 0:
            reasons.append("MACD Bullish Crossover")
            
        if ema9_diff > 0:
            reasons.append("Above 9 EMA Trend")
            
        if vol_ratio > 1.2:
            reasons.append(f"Volume Surge ({vol_ratio:.1f}x avg)")
            
        if mom1d > 0:
            reasons.append(f"1D Momentum +{mom1d:.1f}%")

        return ", ".join(reasons) if reasons else "Positive Technical Structure"

    def predict_top_5_gainers(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Analyze Indian stock universe and predict Top 5 expected gainers priced under Rs. 500."""
        if not self.model_rf or not self.scaler:
            print("⚠️ No pre-trained model found. Training initial model baseline...")
            self.train_baseline(tickers)

        results = []
        print(f"🔍 Analyzing technical indicators across Indian stock universe (Filter: Price < Rs. {MAX_STOCK_PRICE})...")
        
        for ticker in tickers:
            data = fetch_latest_ticker_features(ticker)
            if not data:
                continue

            starting_price = data['starting_price']
            if pd.isna(starting_price) or np.isnan(starting_price):
                continue
            starting_price = round(float(starting_price), 2)
            
            # User requirement: All 5 stocks must be less than Rs. 500
            if starting_price >= MAX_STOCK_PRICE or starting_price <= 0:
                continue


            features = data['features']
            feature_df = pd.DataFrame([features])[FEATURE_COLUMNS]
            scaled_features = self.scaler.transform(feature_df)

            pred_rf = self.model_rf.predict(scaled_features)[0]
            pred_gb = self.model_gb.predict(scaled_features)[0]
            expected_gain = (pred_rf * 0.5) + (pred_gb * 0.5)

            # Adjust confidence score based on technical alignment
            rsi = features.get('rsi_14', 50)
            vol_ratio = features.get('volume_ratio', 1.0)
            mom1d = features.get('momentum_1d', 0)
            
            confidence = 50.0 + (expected_gain * 8.0) + (10 if rsi > 50 else 0) + (10 if vol_ratio > 1.2 else 0)
            confidence = min(98.5, max(45.0, confidence))

            target_gain_pct = round(max(expected_gain, DEFAULT_GAIN_TARGET_PCT), 2)
            
            # User strategy: Exit if stock increases 1 rupee or decreases 3 rupees
            target_price = round(starting_price + PROFIT_TARGET_INR, 2)
            stop_loss = round(starting_price - STOP_LOSS_INR, 2)

            # Assume user invests Rs. 25,000 on each stock
            quantity = max(1, int(INVESTMENT_PER_STOCK / starting_price))
            invested_amount = round(quantity * starting_price, 2)

            results.append({
                'ticker': ticker,
                'starting_price': starting_price,
                'expected_gain_pct': target_gain_pct,
                'target_price': target_price,
                'stop_loss': stop_loss,
                'confidence_score': round(confidence, 1),
                'quantity': quantity,
                'invested_amount': invested_amount,
                'signal_reasons': self._generate_signal_reason(features)
            })

        # Sort by expected gain % descending and pick Top 5
        results.sort(key=lambda x: (x['expected_gain_pct'], x['confidence_score']), reverse=True)
        top_5 = results[:TOP_N_PREDICTIONS]

        for rank, item in enumerate(top_5, start=1):
            item['rank'] = rank

        return top_5

    def retrain_evening_feedback_loop(self, date_str: str, universe_tickers: List[str]) -> Dict[str, Any]:
        """Post-close market feedback loop: evaluate 1-minute intraday trades and retrain model."""
        predictions = get_predictions_by_date(date_str)
        if not predictions:
            print(f"⚠️ No morning predictions recorded for date {date_str} to evaluate.")
            return {'status': 'NO_PREDICTIONS', 'date': date_str}

        outcomes = []
        print(f"📥 Evaluating 1-minute intraday price action (+₹1 / -₹3 rules) for Top 5 predictions on {date_str}...")
        for p in predictions:
            ticker = p['ticker']
            entry_price = p['starting_price']
            quantity = p.get('quantity')
            if not quantity:
                quantity = max(1, int(INVESTMENT_PER_STOCK / entry_price))
            invested_amount = round(quantity * entry_price, 2)

            trade = evaluate_intraday_trade_1m(
                ticker=ticker,
                entry_price=entry_price,
                target_date_str=date_str,
                target_rupees=PROFIT_TARGET_INR,
                stop_loss_rupees=STOP_LOSS_INR
            )

            exit_price = trade['exit_price']
            pnl_per_share = trade['pnl_per_share']
            total_pnl = round(quantity * pnl_per_share, 2)
            pnl_pct = round((total_pnl / invested_amount) * 100, 2) if invested_amount > 0 else 0.0

            status = "TARGET_MET" if "TARGET" in trade['exit_reason'] else ("STOP_LOSS" if "STOP_LOSS" in trade['exit_reason'] else ("GAIN" if pnl_per_share > 0 else "FALL"))

            actual = {
                'ticker': ticker,
                'starting_price': entry_price,
                'close_price': trade['close_price'],
                'high_price': trade['high_price'],
                'low_price': trade['low_price'],
                'exit_price': exit_price,
                'exit_reason': trade['exit_reason'],
                'exit_time': trade['exit_time'],
                'quantity': quantity,
                'invested_amount': invested_amount,
                'pnl_per_share': pnl_per_share,
                'total_pnl': total_pnl,
                'pnl_pct': pnl_pct,
                'actual_gain_pct': pnl_pct,
                'max_gain_pct': round(((trade['high_price'] - entry_price) / entry_price) * 100, 2),
                'status': status
            }

            outcomes.append(actual)

        # Save actual outcomes to database
        if outcomes:
            save_outcomes(date_str, outcomes)

        # Evaluate performance metrics
        wins = sum(1 for o in outcomes if o['pnl_per_share'] > 0)
        total = len(outcomes)
        win_rate = (wins / total * 100) if total > 0 else 0.0


        # Retrain model with updated feedback data
        print(f"🤖 Continuous Retraining Loop: Retraining ML model with today's ({date_str}) actual market feedback...")
        X_hist, y_hist = fetch_historical_training_dataset(universe_tickers, period="6mo")
        
        if not X_hist.empty:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X_hist)
            self.model_rf.fit(X_scaled, y_hist)
            self.model_gb.fit(X_scaled, y_hist)
            self.save_model()
            
            preds_rf = self.model_rf.predict(X_scaled)
            preds_gb = self.model_gb.predict(X_scaled)
            preds_ens = (preds_rf + preds_gb) / 2.0
            mae = float(mean_absolute_error(y_hist, preds_ens))
        else:
            mae = 0.0

        notes = f"Retrained after market close. Win Rate: {win_rate:.1f}% ({wins}/{total} target/gain hit)."
        log_retraining(date_str, len(X_hist), mae, win_rate, notes)

        return {
            'date': date_str,
            'predictions': predictions,
            'outcomes': outcomes,
            'win_rate_pct': round(win_rate, 1),
            'wins_count': wins,
            'total_count': total,
            'mae': round(mae, 4),
            'retrained': True
        }
