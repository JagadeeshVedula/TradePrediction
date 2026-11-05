import sys
import unittest
import pandas as pd
import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import (
    TOP_N_PREDICTIONS, PROFIT_TARGET_INR, STOP_LOSS_INR,
    TRAILING_SL_PUSH_INR, TRAILING_SL_STEP_INR
)
from data_fetcher import evaluate_intraday_trade_1m
from reporter import generate_morning_report_markdown, generate_evening_report_markdown
from database import save_predictions, get_predictions_by_date, save_outcomes, get_outcomes_by_date
from ml_model import TechStockPredictor

class TestTrailingStopLossAndPipeline(unittest.TestCase):

    def test_top_n_is_2(self):
        """Verify Top 5 was reduced to Top 2."""
        self.assertEqual(TOP_N_PREDICTIONS, 2)

    def test_trailing_stop_loss_profit_locked(self):
        """
        Verify that when a stock reaches target (+Rs 2), stop loss trails upward,
        and exiting on trailing stop loss locks in positive profit.
        """
        entry_price = 400.0
        target_date_str = "2026-11-04"
        ist = ZoneInfo("Asia/Kolkata")

        # Create mock 1m bars
        # 10:05 AM: Reaches 402.5 (+2.5) -> target hit, SL pushed to 401 (+1)
        # 10:15 AM: Reaches 404.0 (+4.0) -> steps=2, SL trailed to 403 (+3)
        # 10:30 AM: Drops to 402.8 -> low=402.5 <= 403 -> Triggers trailing stop loss @ 403
        timestamps = [
            datetime.datetime(2026, 11, 4, 10, 5, tzinfo=ist),
            datetime.datetime(2026, 11, 4, 10, 15, tzinfo=ist),
            datetime.datetime(2026, 11, 4, 10, 30, tzinfo=ist),
            datetime.datetime(2026, 11, 4, 15, 29, tzinfo=ist),
        ]
        mock_df = pd.DataFrame({
            'Open': [400.0, 402.5, 403.8, 395.0],
            'High': [402.5, 404.0, 403.8, 396.0],
            'Low': [400.0, 402.0, 402.5, 394.0],
            'Close': [402.5, 403.8, 402.8, 395.0]
        }, index=timestamps)

        with patch('data_fetcher.fetch_intraday_1m_data', return_value=mock_df):
            result = evaluate_intraday_trade_1m(
                ticker="TEST.NS",
                entry_price=entry_price,
                target_date_str=target_date_str
            )

        self.assertIn("TARGET_MET_TRAILING_STOP", result['exit_reason'])
        self.assertEqual(result['exit_price'], 403.0)
        self.assertEqual(result['pnl_per_share'], 3.0)
        self.assertGreater(result['pnl_per_share'], 0)

    def test_pre_10am_target_tracked_for_trailing_sl(self):
        """
        Verify that if target is reached before 10:00 AM, trailing stop loss
        is active post-10:00 AM and does NOT trigger an initial stop loss loss.
        """
        entry_price = 400.0
        target_date_str = "2026-11-04"
        ist = ZoneInfo("Asia/Kolkata")

        # 09:30 AM: Stock reaches 403.0 (+3) -> target hit
        # 10:05 AM: Stock pulls back to 399.5 -> in old code, it triggered initial SL (-1).
        # In fixed code, target_hit is True, trailing SL is at least 401 (+1)
        timestamps = [
            datetime.datetime(2026, 11, 4, 9, 30, tzinfo=ist),
            datetime.datetime(2026, 11, 4, 10, 5, tzinfo=ist),
            datetime.datetime(2026, 11, 4, 15, 29, tzinfo=ist),
        ]
        mock_df = pd.DataFrame({
            'Open': [400.0, 402.0, 398.0],
            'High': [403.0, 402.0, 398.5],
            'Low': [399.8, 399.5, 397.0],
            'Close': [402.5, 400.0, 397.5]
        }, index=timestamps)

        with patch('data_fetcher.fetch_intraday_1m_data', return_value=mock_df):
            result = evaluate_intraday_trade_1m(
                ticker="TEST.NS",
                entry_price=entry_price,
                target_date_str=target_date_str
            )

        self.assertIn("TARGET_MET_TRAILING_STOP", result['exit_reason'])
        self.assertGreaterEqual(result['exit_price'], 401.0)
        self.assertGreater(result['pnl_per_share'], 0)

    def test_market_close_exit_does_not_wipe_trailed_profit(self):
        """
        Verify that if price hits target and never triggered trailing SL,
        at market close it cannot exit below the trailed stop loss.
        """
        entry_price = 400.0
        target_date_str = "2026-11-04"
        ist = ZoneInfo("Asia/Kolkata")

        # Reached 402.5 at 10:15 (SL = 401)
        # At close 15:29: close is 402.0 (above SL 401)
        timestamps = [
            datetime.datetime(2026, 11, 4, 10, 15, tzinfo=ist),
            datetime.datetime(2026, 11, 4, 15, 29, tzinfo=ist),
        ]
        mock_df = pd.DataFrame({
            'Open': [400.0, 402.0],
            'High': [402.5, 402.2],
            'Low': [401.5, 401.8],
            'Close': [402.2, 402.0]
        }, index=timestamps)

        with patch('data_fetcher.fetch_intraday_1m_data', return_value=mock_df):
            result = evaluate_intraday_trade_1m(
                ticker="TEST.NS",
                entry_price=entry_price,
                target_date_str=target_date_str
            )

        self.assertIn("TARGET_MET", result['exit_reason'])
        self.assertGreater(result['pnl_per_share'], 0)

    def test_retrain_evening_feedback_loop_preserves_live_tracker_outcomes(self):
        """
        Verify that retrain_evening_feedback_loop uses existing live outcomes
        and does not overwrite them with simulated close losses.
        """
        date_str = "2026-11-04"
        mock_predictions = [
            {
                'date': date_str,
                'ticker': 'TATASTEEL.NS',
                'rank': 1,
                'starting_price': 150.0,
                'expected_gain_pct': 2.5,
                'target_price': 152.0,
                'stop_loss': 149.0,
                'confidence_score': 95.0,
                'quantity': 166,
                'invested_amount': 24900.0
            },
            {
                'date': date_str,
                'ticker': 'BEL.NS',
                'rank': 2,
                'starting_price': 280.0,
                'expected_gain_pct': 2.2,
                'target_price': 282.0,
                'stop_loss': 279.0,
                'confidence_score': 92.0,
                'quantity': 89,
                'invested_amount': 24920.0
            }
        ]
        # Live tracker recorded profit with trailing stop
        live_outcomes = [
            {
                'date': date_str,
                'ticker': 'TATASTEEL.NS',
                'starting_price': 150.0,
                'close_price': 149.5,
                'high_price': 153.0,
                'low_price': 149.0,
                'actual_gain_pct': 1.33,
                'max_gain_pct': 2.0,
                'status': 'TARGET_MET',
                'quantity': 166,
                'invested_amount': 24900.0,
                'exit_price': 152.0,
                'exit_reason': 'TARGET_MET_TRAILING_STOP (+₹2.00)',
                'exit_time': '11:45',
                'pnl_per_share': 2.0,
                'total_pnl': 332.0,
                'pnl_pct': 1.33
            },
            {
                'date': date_str,
                'ticker': 'BEL.NS',
                'starting_price': 280.0,
                'close_price': 279.0,
                'high_price': 283.0,
                'low_price': 278.5,
                'actual_gain_pct': 0.71,
                'max_gain_pct': 1.07,
                'status': 'TARGET_MET',
                'quantity': 89,
                'invested_amount': 24920.0,
                'exit_price': 282.0,
                'exit_reason': 'TARGET_MET_TRAILING_STOP (+₹2.00)',
                'exit_time': '13:10',
                'pnl_per_share': 2.0,
                'total_pnl': 178.0,
                'pnl_pct': 0.71
            }
        ]

        save_predictions(date_str, mock_predictions)
        save_outcomes(date_str, live_outcomes)

        predictor = TechStockPredictor()
        with patch.object(predictor, 'save_model'):
            with patch('ml_model.fetch_historical_training_dataset', return_value=(pd.DataFrame(), pd.Series())):
                summary = predictor.retrain_evening_feedback_loop(date_str, ['TATASTEEL.NS', 'BEL.NS'])

        # Both stocks should preserve their positive profit
        outcomes = summary['outcomes']
        self.assertEqual(len(outcomes), 2)
        for o in outcomes:
            self.assertEqual(o['exit_price'], o['starting_price'] + 2.0)
            self.assertGreater(o['total_pnl'], 0)
            self.assertIn("TARGET_MET_TRAILING_STOP", o['exit_reason'])

    def test_gemini_analysis_uses_same_picked_stocks(self):
        """
        Verify that run_gemini_deep_analysis uses the stocks already picked
        and stored for the day, without picking different stocks.
        """
        from gemini_analyzer import run_gemini_deep_analysis
        date_str = "2026-11-04"
        mock_predictions = [
            {
                'date': date_str,
                'ticker': 'TATASTEEL.NS',
                'rank': 1,
                'starting_price': 150.0,
                'expected_gain_pct': 2.5,
                'target_price': 152.0,
                'stop_loss': 149.0,
                'confidence_score': 95.0,
                'selection_basis': 'Bullish breakout above 20 EMA with strong delivery volume.',
                'news_impact': 'Metal sector surge driven by infrastructure demand.',
                'quantity': 166,
                'invested_amount': 24900.0
            },
            {
                'date': date_str,
                'ticker': 'BEL.NS',
                'rank': 2,
                'starting_price': 280.0,
                'expected_gain_pct': 2.2,
                'target_price': 282.0,
                'stop_loss': 279.0,
                'confidence_score': 92.0,
                'selection_basis': 'Defence PSU order backlog expansion and RSI momentum.',
                'news_impact': 'New defense contract announcement.',
                'quantity': 89,
                'invested_amount': 24920.0
            }
        ]
        save_predictions(date_str, mock_predictions)

        mock_context = {
            'overall_tone': 'BULLISH',
            'summary_text': 'US markets closed higher with Dow +0.5%',
            'news_items': [{'source': 'Moneycontrol', 'title': 'Nifty set to gap up'}]
        }
        with patch('market_news.get_market_context_summary', return_value=mock_context):
            report = run_gemini_deep_analysis(date_str)

        self.assertIn("TATASTEEL.NS", report)
        self.assertIn("BEL.NS", report)
        self.assertIn("TOP 2 PICKS", report)

if __name__ == '__main__':
    unittest.main()
