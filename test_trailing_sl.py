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
    TRAILING_SL_PUSH_INR, TRAILING_SL_STEP_INR, MIN_AI_CONFIDENCE_THRESHOLD
)
from data_fetcher import evaluate_intraday_trade_1m, FEATURE_COLUMNS
from reporter import generate_morning_report_markdown, generate_evening_report_markdown
from database import save_predictions, get_predictions_by_date, save_outcomes, get_outcomes_by_date
from ml_model import TechStockPredictor
from main import run_morning_mode, run_evening_mode

class TestTrailingStopLossAndPipeline(unittest.TestCase):

    def test_top_n_is_2_and_threshold_95(self):
        """Verify Top 2 picks and >95% confidence threshold configuration."""
        self.assertEqual(TOP_N_PREDICTIONS, 2)
        self.assertEqual(MIN_AI_CONFIDENCE_THRESHOLD, 95.0)

    def test_trailing_stop_loss_profit_locked(self):
        """
        Verify that when a stock reaches target (+Rs 2), stop loss trails upward,
        and exiting on trailing stop loss locks in positive profit.
        """
        entry_price = 400.0
        target_date_str = "2026-11-04"
        ist = ZoneInfo("Asia/Kolkata")

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
                'confidence_score': 96.0,
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
                'confidence_score': 95.5,
                'quantity': 89,
                'invested_amount': 24920.0
            }
        ]
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
                'confidence_score': 96.5,
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
                'confidence_score': 95.8,
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

    def test_ai_not_confident_when_below_95_threshold(self):
        """
        Verify that if fewer than 2 stocks achieve >95% confidence,
        the system responds with 'AI is not confident for todays market'.
        """
        predictor = TechStockPredictor()
        dummy_features = {col: 1.0 for col in FEATURE_COLUMNS}
        sub_95_picks = [
            {'ticker': 'WIPRO.NS', 'starting_price': 420.0, 'expected_gain_pct': 2.0, 'confidence_score': 94.0},
            {'ticker': 'NTPC.NS', 'starting_price': 350.0, 'expected_gain_pct': 1.8, 'confidence_score': 92.5}
        ]
        with patch('ml_model.analyze_and_rank_predictions_with_gemini', return_value=sub_95_picks):
            with patch('ml_model.get_market_context_summary', return_value={'overall_tone': 'NEUTRAL'}):
                with patch('ml_model.fetch_stock_specific_news', return_value=[]):
                    with patch('ml_model.fetch_latest_ticker_features', return_value={'starting_price': 400.0, 'features': dummy_features}):
                        with patch.object(predictor, 'model_rf', MagicMock(predict=MagicMock(return_value=[2.0]))):
                            with patch.object(predictor, 'model_gb', MagicMock(predict=MagicMock(return_value=[2.0]))):
                                with patch.object(predictor, 'scaler', MagicMock(transform=MagicMock(return_value=[[1]*len(FEATURE_COLUMNS)]))):
                                    picks = predictor.predict_top_5_gainers(['WIPRO.NS', 'NTPC.NS'])

        self.assertEqual(picks, [])

        # Verify run_morning_mode outputs the exact alert
        with patch.object(TechStockPredictor, 'predict_top_5_gainers', return_value=[]):
            res = run_morning_mode(date_str="2026-11-06", send_telegram=False)
            self.assertIn("AI is not confident for todays market", res)

        # Verify run_gemini_deep_analysis outputs the exact alert
        from gemini_analyzer import run_gemini_deep_analysis
        save_predictions("2026-11-06", [])
        with patch('market_news.get_market_context_summary', return_value={'overall_tone': 'NEUTRAL'}):
            with patch.object(TechStockPredictor, 'predict_top_5_gainers', return_value=[]):
                res_analysis = run_gemini_deep_analysis("2026-11-06")
                self.assertIn("AI is not confident for todays market", res_analysis)

    def test_ai_confident_when_stocks_above_95_threshold(self):
        """
        Verify that stocks with >95% confidence are successfully accepted and ranked.
        """
        dummy_features = {col: 1.0 for col in FEATURE_COLUMNS}
        high_conf_picks = [
            {'ticker': 'TATASTEEL.NS', 'starting_price': 150.0, 'expected_gain_pct': 2.5, 'confidence_score': 96.5},
            {'ticker': 'BEL.NS', 'starting_price': 280.0, 'expected_gain_pct': 2.2, 'confidence_score': 95.8}
        ]
        predictor = TechStockPredictor()
        with patch('ml_model.analyze_and_rank_predictions_with_gemini', return_value=high_conf_picks):
            with patch('ml_model.get_market_context_summary', return_value={'overall_tone': 'BULLISH'}):
                with patch('ml_model.fetch_stock_specific_news', return_value=[]):
                    with patch('ml_model.fetch_latest_ticker_features', return_value={'starting_price': 150.0, 'features': dummy_features}):
                        with patch.object(predictor, 'model_rf', MagicMock(predict=MagicMock(return_value=[2.0]))):
                            with patch.object(predictor, 'model_gb', MagicMock(predict=MagicMock(return_value=[2.0]))):
                                with patch.object(predictor, 'scaler', MagicMock(transform=MagicMock(return_value=[[1]*len(FEATURE_COLUMNS)]))):
                                    picks = predictor.predict_top_5_gainers(['TATASTEEL.NS', 'BEL.NS'])

        self.assertEqual(len(picks), 2)
        self.assertEqual(picks[0]['ticker'], 'TATASTEEL.NS')
        self.assertGreater(picks[0]['confidence_score'], 95.0)
        self.assertGreater(picks[1]['confidence_score'], 95.0)

    def test_evening_mode_no_predictions_does_not_mutate_or_rerun_morning(self):
        """
        Verify that when evening mode runs for a date with no morning predictions,
        it cleanly reports that no morning predictions were found,
        and NEVER mutates date_str to an older date or executes morning prediction.
        """
        date_str = "2026-12-31"  # Future date with no predictions
        with patch('main.run_morning_mode') as mock_morning:
            msg = run_evening_mode(date_str, send_telegram=False)
            mock_morning.assert_not_called()
            self.assertIn("No morning predictions were recorded for 2026-12-31", msg)

    def test_evening_mode_ai_unconfident_preserves_capital(self):
        """
        Verify that if morning mode recorded AI_UNCONFIDENT for a date,
        evening mode reports 100% capital preserved without generating new trades.
        """
        from database import set_daily_session_status
        date_str = "2020-01-01"
        set_daily_session_status(date_str, "AI_UNCONFIDENT", "Confidence threshold not met")

        with patch('main.run_morning_mode') as mock_morning:
            msg = run_evening_mode(date_str, send_telegram=False)
            mock_morning.assert_not_called()
            self.assertIn("AI was not confident for today's market", msg)
            self.assertIn("Capital is 100% preserved", msg)

    def test_evening_mode_restores_from_outcomes_if_predictions_table_empty(self):
        """
        Verify that if predictions table is empty but outcomes table has today's stocks,
        the system restores the stocks from outcomes table and generates the evening report
        instead of reporting 'AI not confident'.
        """
        date_str = "2020-01-05"
        mock_outcomes = [
            {
                'date': date_str,
                'ticker': 'WIPRO.NS',
                'starting_price': 400.0,
                'close_price': 402.0,
                'high_price': 403.0,
                'low_price': 399.5,
                'actual_gain_pct': 0.5,
                'max_gain_pct': 0.75,
                'status': 'TARGET_MET',
                'quantity': 62,
                'invested_amount': 24800.0,
                'exit_price': 402.0,
                'exit_reason': 'TARGET_MET_TRAILING_STOP (+₹2.00)',
                'exit_time': '12:30',
                'pnl_per_share': 2.0,
                'total_pnl': 124.0,
                'pnl_pct': 0.5
            }
        ]
        save_predictions(date_str, [])  # Simulate cleared predictions table
        save_outcomes(date_str, mock_outcomes)

        predictor = TechStockPredictor()
        with patch.object(predictor, 'save_model'):
            with patch('ml_model.fetch_historical_training_dataset', return_value=(pd.DataFrame(), pd.Series())):
                summary = predictor.retrain_evening_feedback_loop(date_str, ['WIPRO.NS'])

        self.assertNotEqual(summary.get('status'), 'AI_UNCONFIDENT')
        self.assertNotEqual(summary.get('status'), 'NO_PREDICTIONS')
        self.assertEqual(len(summary.get('predictions', [])), 1)
        self.assertEqual(summary['predictions'][0]['ticker'], 'WIPRO.NS')

    def test_evening_mode_locks_trailed_profit_over_erroneous_market_close_loss(self):
        """
        Verify that if a tracker had recorded MARKET_CLOSE with a loss,
        but 1-minute replay demonstrates the stock achieved target (+Rs 2) and trailed stop loss,
        the evening report locks in the positive profit and does NOT report a loss.
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
                'confidence_score': 96.0,
                'quantity': 166,
                'invested_amount': 24900.0
            }
        ]
        save_predictions(date_str, mock_predictions)

        # Erroneous outcome from an interrupted tracker that only saw market close price
        bad_outcomes = [
            {
                'date': date_str,
                'ticker': 'TATASTEEL.NS',
                'starting_price': 150.0,
                'close_price': 148.0,
                'high_price': 150.0,
                'low_price': 148.0,
                'actual_gain_pct': -1.33,
                'max_gain_pct': 0.0,
                'status': 'MARKET_CLOSE',
                'quantity': 166,
                'invested_amount': 24900.0,
                'exit_price': 148.0,
                'exit_reason': 'MARKET_CLOSE',
                'exit_time': '15:30',
                'pnl_per_share': -2.0,
                'total_pnl': -332.0,
                'pnl_pct': -1.33
            }
        ]
        save_outcomes(date_str, bad_outcomes)

        # But 1m bar simulation proves the stock reached 153.50 (target +Rs 2 exceeded)
        # and trailed stop loss locked profit at 152.00 (+Rs 2.00)
        sim_trade_result = {
            'ticker': 'TATASTEEL.NS',
            'entry_price': 150.0,
            'exit_price': 152.0,
            'high_price': 153.5,
            'low_price': 149.8,
            'close_price': 148.0,
            'exit_reason': 'TARGET_MET_TRAILING_STOP (+₹2)',
            'exit_time': '11:15',
            'pnl_per_share': 2.0
        }

        predictor = TechStockPredictor()
        with patch.object(predictor, 'save_model'):
            with patch('ml_model.fetch_historical_training_dataset', return_value=(pd.DataFrame(), pd.Series())):
                with patch('ml_model.evaluate_intraday_trade_1m', return_value=sim_trade_result):
                    summary = predictor.retrain_evening_feedback_loop(date_str, ['TATASTEEL.NS'])

        outcomes = summary['outcomes']
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]['exit_price'], 152.0)
        self.assertGreater(outcomes[0]['pnl_per_share'], 0)
        self.assertIn("TARGET_MET_TRAILING_STOP", outcomes[0]['exit_reason'])

if __name__ == '__main__':
    unittest.main()
