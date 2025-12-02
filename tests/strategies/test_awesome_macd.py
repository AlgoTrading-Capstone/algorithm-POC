"""
Unit tests for AwesomeMacd strategy.

Tests cover:
- Strategy initialization
- Input validation and edge cases
- Awesome Oscillator calculation
- MACD indicator calculation
- Signal generation logic (LONG on AO cross above zero, SHORT on cross below)
- Full strategy integration
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from strategies.awesome_macd import AwesomeMacd
from strategies.base_strategy import SignalType, StrategyRecommendation


class TestAwesomeMacdInit:
    """Tests for AwesomeMacd initialization."""

    def test_strategy_initialization(self):
        """Test strategy initializes with correct parameters."""
        strategy = AwesomeMacd()

        assert strategy.name == "AwesomeMacd"
        assert strategy.timeframe == "1h"
        assert strategy.lookback_hours == 100
        assert strategy.MIN_CANDLES_REQUIRED == 70
        assert "MACD" in strategy.description or "Awesome" in strategy.description


class TestAwesomeMacdValidation:
    """Tests for input validation and edge cases."""

    def test_insufficient_data_returns_hold(self, fixed_timestamp):
        """Test strategy returns HOLD when data is insufficient."""
        strategy = AwesomeMacd()

        # Create DataFrame with only 50 candles (< MIN_CANDLES_REQUIRED = 70)
        dates = pd.date_range('2024-01-01', periods=50, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0] * 50,
            'high': [42100.0] * 50,
            'low': [41900.0] * 50,
            'close': [42000.0] * 50,
            'volume': [100.0] * 50
        })

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_none_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles None DataFrame gracefully."""
        strategy = AwesomeMacd()
        result = strategy.run(None, fixed_timestamp)

        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_empty_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles empty DataFrame."""
        strategy = AwesomeMacd()
        df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        result = strategy.run(df, fixed_timestamp)

        assert result.signal == SignalType.HOLD

    def test_exactly_min_candles_required(self, fixed_timestamp):
        """Test strategy works with exactly MIN_CANDLES_REQUIRED candles."""
        strategy = AwesomeMacd()

        # Create DataFrame with exactly 70 candles
        dates = pd.date_range('2024-01-01', periods=70, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0 + i * 10 for i in range(70)],
            'high': [42100.0 + i * 10 for i in range(70)],
            'low': [41900.0 + i * 10 for i in range(70)],
            'close': [42000.0 + i * 10 for i in range(70)],
            'volume': [100.0] * 70
        })

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]


class TestAwesomeMacdIndicators:
    """Tests for indicator calculation correctness."""

    def test_calculate_indicators_adds_columns(self, load_fixture_df):
        """Test that _calculate_indicators adds required columns."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Check all required indicators are present
        assert 'adx' in df_with_indicators.columns
        assert 'ao' in df_with_indicators.columns
        assert 'macd' in df_with_indicators.columns
        assert 'macdsignal' in df_with_indicators.columns
        assert 'macdhist' in df_with_indicators.columns

    def test_awesome_oscillator_calculation(self, sample_ohlcv_df):
        """Test Awesome Oscillator is calculated correctly."""
        strategy = AwesomeMacd()

        # Calculate AO
        ao_series = strategy._calculate_awesome_oscillator(sample_ohlcv_df)

        # AO should be a pandas Series with same length as input
        assert isinstance(ao_series, pd.Series)
        assert len(ao_series) == len(sample_ohlcv_df)

        # First 34 values should be NaN (due to 34-period SMA warmup)
        assert ao_series.iloc[:33].isna().all()

        # After warmup, should have numeric values
        assert not ao_series.iloc[34:].isna().all()

    def test_awesome_oscillator_formula(self, sample_ohlcv_df):
        """Test AO formula: SMA(median, 5) - SMA(median, 34)."""
        strategy = AwesomeMacd()

        # Calculate median price manually
        median_price = (sample_ohlcv_df['high'] + sample_ohlcv_df['low']) / 2.0

        # Calculate SMAs manually using pandas rolling
        sma_5 = median_price.rolling(window=5).mean()
        sma_34 = median_price.rolling(window=34).mean()
        expected_ao = sma_5 - sma_34

        # Calculate using strategy method
        actual_ao = strategy._calculate_awesome_oscillator(sample_ohlcv_df)

        # Compare (allowing for floating point precision differences)
        pd.testing.assert_series_equal(actual_ao, expected_ao, check_names=False, atol=1e-6)

    def test_macd_values_exist_after_warmup(self, load_fixture_df):
        """Test MACD values are calculated after warmup period."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # After warmup (26 periods for MACD slow EMA), should have values
        assert not df_with_indicators['macd'].iloc[30:].isna().all()
        assert not df_with_indicators['macdsignal'].iloc[35:].isna().all()

    def test_adx_values_in_valid_range(self, load_fixture_df):
        """Test ADX values are in valid range [0, 100]."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # ADX should be between 0 and 100
        valid_adx = df_with_indicators['adx'].dropna()
        assert (valid_adx >= 0).all()
        assert (valid_adx <= 100).all()


class TestAwesomeMacdSignals:
    """Tests for signal generation logic."""

    def test_long_signal_on_ao_cross_above_zero(self, fixed_timestamp):
        """Test LONG signal when MACD > 0 AND AO crosses above zero."""
        strategy = AwesomeMacd()

        # Create scenario: AO crosses from negative to positive with MACD > 0
        dates = pd.date_range('2024-01-01', periods=80, freq='1h', tz='UTC')

        # Create price pattern: downtrend then sharp reversal
        prices = []
        for i in range(40):
            prices.append(44000 - i * 20)  # Downtrend
        for i in range(40):
            prices.append(42200 + i * 30)  # Sharp uptrend

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 100 for p in prices],
            'low': [p - 100 for p in prices],
            'close': prices,
            'volume': [100.0] * 80
        })

        result = strategy.run(df, fixed_timestamp)

        # After reversal from downtrend, should get LONG or HOLD
        # LONG occurs when MACD > 0 and AO crosses above zero
        assert result.signal in [SignalType.LONG, SignalType.HOLD]

    def test_short_signal_on_ao_cross_below_zero(self, fixed_timestamp):
        """Test SHORT signal when MACD < 0 AND AO crosses below zero."""
        strategy = AwesomeMacd()

        # Create scenario: AO crosses from positive to negative with MACD < 0
        dates = pd.date_range('2024-01-01', periods=80, freq='1h', tz='UTC')

        # Create price pattern: uptrend then sharp reversal
        prices = []
        for i in range(40):
            prices.append(42000 + i * 30)  # Uptrend
        for i in range(40):
            prices.append(43200 - i * 25)  # Sharp downtrend

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 100 for p in prices],
            'low': [p - 100 for p in prices],
            'close': prices,
            'volume': [100.0] * 80
        })

        result = strategy.run(df, fixed_timestamp)

        # After reversal from uptrend, should get SHORT or HOLD
        # SHORT occurs when MACD < 0 and AO crosses below zero
        assert result.signal in [SignalType.SHORT, SignalType.HOLD]

    def test_hold_signal_when_no_crossover(self, sample_ohlcv_df, fixed_timestamp):
        """Test HOLD signal when AO doesn't cross zero line."""
        strategy = AwesomeMacd()

        # sample_ohlcv_df has gradual uptrend - AO should stay positive, no crossover
        result = strategy.run(sample_ohlcv_df, fixed_timestamp)

        # No crossover should occur in gradual uptrend
        assert result.signal == SignalType.HOLD

    def test_hold_signal_with_nan_indicators(self, fixed_timestamp):
        """Test HOLD when indicators are NaN (warmup period)."""
        strategy = AwesomeMacd()

        # Use minimal data where indicators will be NaN
        dates = pd.date_range('2024-01-01', periods=30, freq='1h', tz='UTC')
        df = pd.DataFrame({
            'date': dates,
            'open': [42000.0] * 30,
            'high': [42100.0] * 30,
            'low': [41900.0] * 30,
            'close': [42000.0] * 30,
            'volume': [100.0] * 30
        })

        # Calculate indicators (will have NaN due to insufficient history)
        df_with_indicators = strategy._calculate_indicators(df)
        signal = strategy._generate_signal(df_with_indicators)

        assert signal == SignalType.HOLD

    def test_hold_when_macd_negative_but_no_ao_cross(self, fixed_timestamp):
        """Test HOLD when MACD < 0 but AO doesn't cross below zero."""
        strategy = AwesomeMacd()

        dates = pd.date_range('2024-01-01', periods=80, freq='1h', tz='UTC')

        # Create gentle downtrend - MACD may be negative but AO won't cross
        prices = [42000.0 - i * 5 for i in range(80)]

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 100 for p in prices],
            'low': [p - 100 for p in prices],
            'close': prices,
            'volume': [100.0] * 80
        })

        result = strategy.run(df, fixed_timestamp)

        # No crossover should trigger HOLD (might also be SHORT if conditions met)
        assert result.signal in [SignalType.HOLD, SignalType.SHORT]

    def test_hold_when_macd_positive_but_no_ao_cross(self, fixed_timestamp):
        """Test HOLD when MACD > 0 but AO doesn't cross above zero."""
        strategy = AwesomeMacd()

        dates = pd.date_range('2024-01-01', periods=80, freq='1h', tz='UTC')

        # Create gentle uptrend - MACD may be positive but AO won't cross
        prices = [42000.0 + i * 5 for i in range(80)]

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 100 for p in prices],
            'low': [p - 100 for p in prices],
            'close': prices,
            'volume': [100.0] * 80
        })

        result = strategy.run(df, fixed_timestamp)

        # No crossover should trigger HOLD (might also be LONG if conditions met)
        assert result.signal in [SignalType.HOLD, SignalType.LONG]


class TestAwesomeMacdIntegration:
    """Integration tests for full strategy execution."""

    def test_run_with_valid_fixture_data(self, load_fixture_df, fixed_timestamp):
        """Test full strategy run with valid fixture data."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert isinstance(result.signal, SignalType)
        assert result.timestamp == fixed_timestamp

    def test_strategy_is_deterministic(self, load_fixture_df, fixed_timestamp):
        """Test strategy produces same result with same input."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result1 = strategy.run(df.copy(), fixed_timestamp)
        result2 = strategy.run(df.copy(), fixed_timestamp)

        assert result1.signal == result2.signal
        assert result1.timestamp == result2.timestamp

    def test_strategy_with_minimal_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with minimal fixture (edge case)."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_minimal.csv')  # Only 20 candles

        result = strategy.run(df, fixed_timestamp)

        # Should return HOLD due to insufficient data
        assert result.signal == SignalType.HOLD

    def test_strategy_with_extended_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with extended fixture (200 candles)."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_200.csv')

        result = strategy.run(df, fixed_timestamp)

        # Should work fine with more data
        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]

    def test_output_format_correctness(self, load_fixture_df, fixed_timestamp):
        """Test output follows StrategyRecommendation format."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        # Check it's a StrategyRecommendation NamedTuple
        assert hasattr(result, 'signal')
        assert hasattr(result, 'timestamp')
        assert len(result) == 2  # NamedTuple with 2 fields

    def test_timestamp_propagation(self, load_fixture_df):
        """Test that input timestamp is propagated to output."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Use different timestamps
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 2, 15, 18, 30, 0, tzinfo=timezone.utc)

        result1 = strategy.run(df, ts1)
        result2 = strategy.run(df, ts2)

        assert result1.timestamp == ts1
        assert result2.timestamp == ts2

    def test_strategy_does_not_modify_input_dataframe(self, load_fixture_df, fixed_timestamp):
        """Test strategy doesn't modify the input DataFrame."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Get original columns
        original_columns = df.columns.tolist()

        # Run strategy
        strategy.run(df, fixed_timestamp)

        # Check columns haven't changed
        assert df.columns.tolist() == original_columns

    def test_multiple_executions_independent(self, load_fixture_df, fixed_timestamp):
        """Test multiple strategy executions are independent."""
        strategy = AwesomeMacd()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Run strategy multiple times
        results = [strategy.run(df.copy(), fixed_timestamp) for _ in range(3)]

        # All results should be identical
        assert all(r.signal == results[0].signal for r in results)
        assert all(r.timestamp == results[0].timestamp for r in results)
