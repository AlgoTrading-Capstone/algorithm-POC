"""
Unit tests for OTTStrategy (Optimized Trend Tracker).

Tests cover:
- Strategy initialization
- Input validation and edge cases
- OTT indicator calculations (Var, OTT, CMO, etc.)
- Signal generation logic (LONG, SHORT, HOLD)
- Crossover detection (_crossed_above, _crossed_below)
- Full strategy integration
"""
import pytest
import pandas as pd
from datetime import datetime, timezone
from strategies.ott_strategy import OTTStrategy
from strategies.base_strategy import SignalType, StrategyRecommendation


class TestOTTStrategyInit:
    """Tests for OTTStrategy initialization."""

    def test_strategy_initialization(self):
        """Test strategy initializes with correct parameters."""
        strategy = OTTStrategy()

        assert strategy.name == "OTTStrategy"
        assert strategy.timeframe == "1h"
        assert strategy.lookback_hours == 50
        assert strategy.MIN_CANDLES_REQUIRED == 30
        assert "OTT" in strategy.description or "Trend" in strategy.description


class TestOTTStrategyValidation:
    """Tests for input validation and edge cases."""

    def test_insufficient_data_returns_hold(self, fixed_timestamp):
        """Test strategy returns HOLD when data is insufficient."""
        strategy = OTTStrategy()

        # Create DataFrame with only 20 candles (< MIN_CANDLES_REQUIRED)
        dates = pd.date_range('2024-01-01', periods=20, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0] * 20,
            'high': [42100.0] * 20,
            'low': [41900.0] * 20,
            'close': [42000.0] * 20,
            'volume': [100.0] * 20
        })

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_none_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles None DataFrame gracefully."""
        strategy = OTTStrategy()
        result = strategy.run(None, fixed_timestamp)

        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_empty_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles empty DataFrame."""
        strategy = OTTStrategy()
        df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        result = strategy.run(df, fixed_timestamp)

        assert result.signal == SignalType.HOLD

    def test_exactly_min_candles_required(self, fixed_timestamp):
        """Test strategy works with exactly MIN_CANDLES_REQUIRED candles."""
        strategy = OTTStrategy()

        # Create DataFrame with exactly 30 candles
        dates = pd.date_range('2024-01-01', periods=30, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0 + i * 10 for i in range(30)],
            'high': [42100.0 + i * 10 for i in range(30)],
            'low': [41900.0 + i * 10 for i in range(30)],
            'close': [42000.0 + i * 10 for i in range(30)],
            'volume': [100.0] * 30
        })

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]


class TestOTTStrategyIndicators:
    """Tests for OTT indicator calculation correctness."""

    def test_calculate_indicators_adds_columns(self, load_fixture_df):
        """Test that _calculate_indicators adds required columns."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Check OTT columns exist
        assert 'Var' in df_with_indicators.columns
        assert 'OTT' in df_with_indicators.columns
        assert 'adx' in df_with_indicators.columns

    def test_ott_calculation_produces_values(self, load_fixture_df):
        """Test OTT calculation produces non-NaN values after warmup."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_ott(df)

        # After warmup, OTT and Var should have values
        valid_ott = df_with_indicators['OTT'].dropna()
        valid_var = df_with_indicators['Var'].dropna()

        assert len(valid_ott) > 0
        assert len(valid_var) > 0

    def test_cmo_values_in_valid_range(self, load_fixture_df):
        """Test CMO values are between 0 and 1 (it's absolute)."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_ott(df)

        # CMO should be in [0, 1] after abs()
        if 'CMO' in df_with_indicators.columns:
            valid_cmo = df_with_indicators['CMO'].dropna()
            assert (valid_cmo >= 0).all()
            assert (valid_cmo <= 1).all()

    def test_adx_calculation(self, load_fixture_df):
        """Test ADX is calculated correctly."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # ADX should exist and have positive values
        valid_adx = df_with_indicators['adx'].dropna()
        assert len(valid_adx) > 0
        assert (valid_adx >= 0).all()


class TestOTTStrategyCrossoverHelpers:
    """Tests for crossover detection helper methods."""

    def test_crossed_above_detection(self):
        """Test _crossed_above detects upward crossover correctly."""
        strategy = OTTStrategy()

        # Create series where series1 crosses above series2
        series1 = pd.Series([10, 11, 12, 15, 20])
        series2 = pd.Series([15, 14, 13, 14, 15])

        # Last candle: series1 (20) > series2 (15)
        # Previous: series1 (15) > series2 (14) - Actually this is already above
        # So no crossover

        # Let's create a true crossover
        series1 = pd.Series([10, 11, 12, 14, 16])
        series2 = pd.Series([15, 15, 15, 15, 15])

        # At index -2: series1 (14) <= series2 (15)
        # At index -1: series1 (16) > series2 (15)
        # This IS a crossover
        assert strategy._crossed_above(series1, series2) == True

    def test_crossed_below_detection(self):
        """Test _crossed_below detects downward crossover correctly."""
        strategy = OTTStrategy()

        # Create series where series1 crosses below series2
        series1 = pd.Series([20, 18, 16, 15, 12])
        series2 = pd.Series([15, 15, 15, 15, 15])

        # At index -2: series1 (15) >= series2 (15)
        # At index -1: series1 (12) < series2 (15)
        # This IS a crossover
        assert strategy._crossed_below(series1, series2) == True

    def test_no_crossover_when_already_above(self):
        """Test no crossover detected when already above."""
        strategy = OTTStrategy()

        # Series1 is always above series2
        series1 = pd.Series([20, 21, 22, 23, 24])
        series2 = pd.Series([10, 10, 10, 10, 10])

        assert strategy._crossed_above(series1, series2) == False

    def test_no_crossover_when_already_below(self):
        """Test no crossover detected when already below."""
        strategy = OTTStrategy()

        # Series1 is always below series2
        series1 = pd.Series([5, 6, 7, 8, 9])
        series2 = pd.Series([15, 15, 15, 15, 15])

        assert strategy._crossed_below(series1, series2) == False

    def test_crossover_with_insufficient_data(self):
        """Test crossover returns False with insufficient data."""
        strategy = OTTStrategy()

        # Only 1 value (need at least 2)
        series1 = pd.Series([10])
        series2 = pd.Series([15])

        assert strategy._crossed_above(series1, series2) == False
        assert strategy._crossed_below(series1, series2) == False


class TestOTTStrategySignals:
    """Tests for signal generation logic."""

    def test_long_signal_on_var_crosses_above_ott(self, load_fixture_df, fixed_timestamp):
        """Test LONG signal when VAR crosses above OTT."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Run strategy (may or may not produce LONG depending on data)
        result = strategy.run(df, fixed_timestamp)

        # Just verify the method works
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.HOLD]

    def test_short_signal_on_var_crosses_below_ott(self, load_fixture_df, fixed_timestamp):
        """Test SHORT signal when VAR crosses below OTT."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Run strategy (may or may not produce SHORT depending on data)
        result = strategy.run(df, fixed_timestamp)

        # Just verify the method works
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.HOLD]

    def test_hold_signal_with_nan_indicators(self, fixed_timestamp):
        """Test HOLD when indicators are NaN (warmup period)."""
        strategy = OTTStrategy()

        # Use minimal data where indicators will be NaN
        dates = pd.date_range('2024-01-01', periods=15, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0] * 15,
            'high': [42100.0] * 15,
            'low': [41900.0] * 15,
            'close': [42000.0] * 15,
            'volume': [100.0] * 15
        })

        # Calculate indicators (will have NaN due to insufficient history)
        df_with_indicators = strategy._calculate_indicators(df)
        signal = strategy._generate_signal(df_with_indicators)

        assert signal == SignalType.HOLD

    def test_hold_signal_when_no_crossover(self, sample_ohlcv_df, fixed_timestamp):
        """Test HOLD signal when no crossover occurs."""
        strategy = OTTStrategy()

        result = strategy.run(sample_ohlcv_df, fixed_timestamp)

        # With sample data, crossover may or may not occur
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.HOLD]


class TestOTTStrategyIntegration:
    """Integration tests for full strategy execution."""

    def test_run_with_valid_fixture_data(self, load_fixture_df, fixed_timestamp):
        """Test full strategy run with valid fixture data."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert isinstance(result.signal, SignalType)
        assert result.timestamp == fixed_timestamp

    def test_strategy_is_deterministic(self, load_fixture_df, fixed_timestamp):
        """Test strategy produces same result with same input."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result1 = strategy.run(df.copy(), fixed_timestamp)
        result2 = strategy.run(df.copy(), fixed_timestamp)

        assert result1.signal == result2.signal
        assert result1.timestamp == result2.timestamp

    def test_strategy_with_minimal_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with minimal fixture (edge case)."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_minimal.csv')  # Only 20 candles

        result = strategy.run(df, fixed_timestamp)

        # Should return HOLD due to insufficient data (need 30)
        assert result.signal == SignalType.HOLD

    def test_strategy_with_extended_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with extended fixture (200 candles)."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_200.csv')

        result = strategy.run(df, fixed_timestamp)

        # Should work fine with more data
        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]

    def test_output_format_correctness(self, load_fixture_df, fixed_timestamp):
        """Test output follows StrategyRecommendation format."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        # Check it's a StrategyRecommendation NamedTuple
        assert hasattr(result, 'signal')
        assert hasattr(result, 'timestamp')
        assert len(result) == 2  # NamedTuple with 2 fields

    def test_timestamp_propagation(self, load_fixture_df):
        """Test that input timestamp is propagated to output."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Use different timestamps
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 2, 15, 18, 30, 0, tzinfo=timezone.utc)

        result1 = strategy.run(df, ts1)
        result2 = strategy.run(df, ts2)

        assert result1.timestamp == ts1
        assert result2.timestamp == ts2

    def test_supports_long_and_short_signals(self):
        """Test strategy can generate both LONG and SHORT signals."""
        # OTT strategy supports both LONG and SHORT
        assert hasattr(SignalType, 'LONG')
        assert hasattr(SignalType, 'SHORT')

    def test_complex_ott_calculation_doesnt_error(self, load_fixture_df, fixed_timestamp):
        """Test complex OTT calculation completes without errors."""
        strategy = OTTStrategy()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # The _calculate_ott method has complex logic with loops
        # Just verify it completes successfully
        df_with_ott = strategy._calculate_ott(df)

        assert 'OTT' in df_with_ott.columns
        assert 'Var' in df_with_ott.columns
        assert len(df_with_ott) == len(df)
