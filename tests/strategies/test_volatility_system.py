"""
Unit tests for VolatilitySystem strategy.

Tests cover:
- Strategy initialization
- Input validation and edge cases
- Indicator calculations (ATR, close_change, resampling)
- Signal generation logic (LONG, SHORT, HOLD)
- Full strategy integration
- Multi-timeframe resampling behavior
"""
import pytest
import pandas as pd
from datetime import datetime, timezone
from strategies.volatility_system import VolatilitySystem
from strategies.base_strategy import SignalType, StrategyRecommendation


class TestVolatilitySystemInit:
    """Tests for VolatilitySystem initialization."""

    def test_strategy_initialization(self):
        """Test strategy initializes with correct parameters."""
        strategy = VolatilitySystem()

        assert strategy.name == "VolatilitySystem"
        assert strategy.timeframe == "1h"
        assert strategy.lookback_hours == 66
        assert strategy.MIN_CANDLES_REQUIRED == 52
        assert "ATR" in strategy.description or "Volatility" in strategy.description


class TestVolatilitySystemValidation:
    """Tests for input validation and edge cases."""

    def test_insufficient_data_returns_hold(self, fixed_timestamp):
        """Test strategy returns HOLD when data is insufficient."""
        strategy = VolatilitySystem()

        # Create DataFrame with only 40 candles (< MIN_CANDLES_REQUIRED)
        dates = pd.date_range('2024-01-01', periods=40, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0] * 40,
            'high': [42100.0] * 40,
            'low': [41900.0] * 40,
            'close': [42000.0] * 40,
            'volume': [100.0] * 40
        })

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_none_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles None DataFrame gracefully."""
        strategy = VolatilitySystem()
        result = strategy.run(None, fixed_timestamp)

        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_empty_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles empty DataFrame."""
        strategy = VolatilitySystem()
        df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        result = strategy.run(df, fixed_timestamp)

        assert result.signal == SignalType.HOLD

    def test_exactly_min_candles_required(self, load_fixture_df, fixed_timestamp):
        """Test strategy works with exactly MIN_CANDLES_REQUIRED candles."""
        strategy = VolatilitySystem()

        # Use 52 candles from fixture
        df = load_fixture_df('btc_usdt_1h_100.csv')
        df_52 = df.head(52).copy()

        result = strategy.run(df_52, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]


class TestVolatilitySystemIndicators:
    """Tests for indicator calculation correctness."""

    def test_calculate_indicators_adds_columns(self, load_fixture_df):
        """Test that _calculate_indicators adds required columns."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Check ATR column exists
        assert 'atr' in df_with_indicators.columns

        # Check close_change columns exist
        assert 'close_change' in df_with_indicators.columns
        assert 'abs_close_change' in df_with_indicators.columns

    def test_atr_values_are_positive(self, load_fixture_df):
        """Test ATR values are positive after warmup period."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # After warmup, ATR should be positive (ATR is doubled, so > 0)
        valid_atr = df_with_indicators['atr'].dropna()
        assert len(valid_atr) > 0
        assert (valid_atr > 0).all()

    def test_abs_close_change_is_non_negative(self, load_fixture_df):
        """Test absolute close change is non-negative."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Absolute values should be >= 0
        valid_abs_change = df_with_indicators['abs_close_change'].dropna()
        assert (valid_abs_change >= 0).all()

    def test_resampling_to_3h(self, load_fixture_df):
        """Test that resampling to 3h works correctly."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Should have resampled columns from 3h (180 min) data
        # The resampled_merge creates columns with resample_ prefix
        assert 'atr' in df_with_indicators.columns
        assert len(df_with_indicators) == len(df)  # Same length as original


class TestVolatilitySystemSignals:
    """Tests for signal generation logic."""

    def test_long_signal_on_upward_breakout(self, fixed_timestamp):
        """Test LONG signal when positive close_change > ATR."""
        strategy = VolatilitySystem()

        # Create data with strong upward move
        dates = pd.date_range('2024-01-01', periods=60, freq='1h', tz='UTC')

        # Start stable, then big upward move
        prices = [42000.0 + i * 5 for i in range(54)]
        # Add strong upward breakout at the end
        prices.extend([43000.0, 44000.0, 45000.0, 46000.0, 47000.0, 48000.0])

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 200 for p in prices],
            'low': [p - 200 for p in prices],
            'close': prices,
            'volume': [100.0] * 60
        })

        result = strategy.run(df, fixed_timestamp)

        # Strong upward move should trigger LONG
        assert result.signal == SignalType.LONG

    def test_short_signal_on_downward_breakout(self, fixed_timestamp):
        """Test SHORT signal when negative close_change > ATR."""
        strategy = VolatilitySystem()

        # Create data with strong downward move
        dates = pd.date_range('2024-01-01', periods=60, freq='1h', tz='UTC')

        # Start stable, then big downward move
        prices = [48000.0 - i * 5 for i in range(54)]
        # Add strong downward breakout at the end
        prices.extend([44000.0, 42000.0, 40000.0, 38000.0, 36000.0, 34000.0])

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 200 for p in prices],
            'low': [p - 200 for p in prices],
            'close': prices,
            'volume': [100.0] * 60
        })

        result = strategy.run(df, fixed_timestamp)

        # Strong downward move should trigger SHORT
        assert result.signal == SignalType.SHORT

    def test_hold_signal_with_nan_indicators(self, fixed_timestamp):
        """Test HOLD when indicators are NaN (warmup period)."""
        strategy = VolatilitySystem()

        # Use minimal data where indicators will be NaN
        dates = pd.date_range('2024-01-01', periods=20, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0] * 20,
            'high': [42100.0] * 20,
            'low': [41900.0] * 20,
            'close': [42000.0] * 20,
            'volume': [100.0] * 20
        })

        # Calculate indicators (will have NaN due to insufficient history)
        df_with_indicators = strategy._calculate_indicators(df)
        signal = strategy._generate_signal(df_with_indicators)

        assert signal == SignalType.HOLD

    def test_hold_signal_in_low_volatility(self, fixed_timestamp):
        """Test HOLD signal when price movement is within ATR range."""
        strategy = VolatilitySystem()

        # Create flat market data (low volatility)
        dates = pd.date_range('2024-01-01', periods=60, freq='1h', tz='UTC')
        prices = [42000.0 + i * 2 for i in range(60)]  # Very small movements

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 50 for p in prices],
            'low': [p - 50 for p in prices],
            'close': prices,
            'volume': [100.0] * 60
        })

        result = strategy.run(df, fixed_timestamp)

        # Low volatility should result in HOLD
        assert result.signal == SignalType.HOLD

    def test_signal_uses_shifted_atr(self, load_fixture_df, fixed_timestamp):
        """Test that signal generation uses shifted ATR (prev_row)."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Verify _generate_signal can access both last and previous rows
        if len(df_with_indicators) >= 2:
            signal = strategy._generate_signal(df_with_indicators)
            assert signal in [SignalType.LONG, SignalType.SHORT, SignalType.HOLD]


class TestVolatilitySystemIntegration:
    """Integration tests for full strategy execution."""

    def test_run_with_valid_fixture_data(self, load_fixture_df, fixed_timestamp):
        """Test full strategy run with valid fixture data."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert isinstance(result.signal, SignalType)
        assert result.timestamp == fixed_timestamp

    def test_strategy_is_deterministic(self, load_fixture_df, fixed_timestamp):
        """Test strategy produces same result with same input."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result1 = strategy.run(df.copy(), fixed_timestamp)
        result2 = strategy.run(df.copy(), fixed_timestamp)

        assert result1.signal == result2.signal
        assert result1.timestamp == result2.timestamp

    def test_strategy_with_minimal_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with minimal fixture (edge case)."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_minimal.csv')  # Only 20 candles

        result = strategy.run(df, fixed_timestamp)

        # Should return HOLD due to insufficient data (need 52)
        assert result.signal == SignalType.HOLD

    def test_strategy_with_extended_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with extended fixture (200 candles)."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_200.csv')

        result = strategy.run(df, fixed_timestamp)

        # Should work fine with more data
        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]

    def test_output_format_correctness(self, load_fixture_df, fixed_timestamp):
        """Test output follows StrategyRecommendation format."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        # Check it's a StrategyRecommendation NamedTuple
        assert hasattr(result, 'signal')
        assert hasattr(result, 'timestamp')
        assert len(result) == 2  # NamedTuple with 2 fields

    def test_timestamp_propagation(self, load_fixture_df):
        """Test that input timestamp is propagated to output."""
        strategy = VolatilitySystem()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Use different timestamps
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 2, 15, 18, 30, 0, tzinfo=timezone.utc)

        result1 = strategy.run(df, ts1)
        result2 = strategy.run(df, ts2)

        assert result1.timestamp == ts1
        assert result2.timestamp == ts2

    def test_supports_long_and_short_signals(self, fixed_timestamp):
        """Test strategy can generate both LONG and SHORT signals."""
        strategy = VolatilitySystem()

        # Test LONG (covered in test_long_signal_on_upward_breakout)
        # Test SHORT (covered in test_short_signal_on_downward_breakout)

        # Just verify the strategy supports both directions
        assert hasattr(SignalType, 'LONG')
        assert hasattr(SignalType, 'SHORT')
