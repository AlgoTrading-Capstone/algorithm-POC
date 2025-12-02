"""
Unit tests for BbandRsi strategy.

Tests cover:
- Strategy initialization
- Input validation and edge cases
- Indicator calculations (RSI and Bollinger Bands)
- Signal generation logic (LONG, FLAT, HOLD)
- Full strategy integration
"""
import pytest
import pandas as pd
from datetime import datetime, timezone
from strategies.bband_rsi import BbandRsi
from strategies.base_strategy import SignalType, StrategyRecommendation


class TestBbandRsiInit:
    """Tests for BbandRsi initialization."""

    def test_strategy_initialization(self):
        """Test strategy initializes with correct parameters."""
        strategy = BbandRsi()

        assert strategy.name == "BbandRsi"
        assert strategy.timeframe == "1h"
        assert strategy.lookback_hours == 40
        assert strategy.MIN_CANDLES_REQUIRED == 30
        assert "RSI" in strategy.description or "Bollinger" in strategy.description


class TestBbandRsiValidation:
    """Tests for input validation and edge cases."""

    def test_insufficient_data_returns_hold(self, fixed_timestamp):
        """Test strategy returns HOLD when data is insufficient."""
        strategy = BbandRsi()

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
        strategy = BbandRsi()
        result = strategy.run(None, fixed_timestamp)

        assert result.signal == SignalType.HOLD
        assert result.timestamp == fixed_timestamp

    def test_empty_dataframe_returns_hold(self, fixed_timestamp):
        """Test strategy handles empty DataFrame."""
        strategy = BbandRsi()
        df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        result = strategy.run(df, fixed_timestamp)

        assert result.signal == SignalType.HOLD

    def test_exactly_min_candles_required(self, fixed_timestamp):
        """Test strategy works with exactly MIN_CANDLES_REQUIRED candles."""
        strategy = BbandRsi()

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


class TestBbandRsiIndicators:
    """Tests for indicator calculation correctness."""

    def test_calculate_indicators_adds_columns(self, load_fixture_df):
        """Test that _calculate_indicators adds required columns."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Check RSI column exists
        assert 'rsi' in df_with_indicators.columns

        # Check Bollinger Bands columns exist
        assert 'bb_upperband' in df_with_indicators.columns
        assert 'bb_middleband' in df_with_indicators.columns
        assert 'bb_lowerband' in df_with_indicators.columns

        # Check typical price column exists
        assert 'typical_price' in df_with_indicators.columns

    def test_rsi_values_in_valid_range(self, load_fixture_df):
        """Test RSI values are between 0 and 100."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # After warmup period, RSI should be in [0, 100]
        valid_rsi = df_with_indicators['rsi'].dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_bollinger_bands_ordering(self, load_fixture_df):
        """Test Bollinger Bands maintain upper >= middle >= lower ordering."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        df_with_indicators = strategy._calculate_indicators(df)

        # Drop NaN rows from warmup period
        df_valid = df_with_indicators.dropna(subset=['bb_upperband', 'bb_middleband', 'bb_lowerband'])

        # Check ordering: upper >= middle >= lower
        assert (df_valid['bb_upperband'] >= df_valid['bb_middleband']).all()
        assert (df_valid['bb_middleband'] >= df_valid['bb_lowerband']).all()

    def test_typical_price_calculation(self, sample_ohlcv_df):
        """Test typical price is calculated as (H+L+C)/3."""
        strategy = BbandRsi()
        df_with_indicators = strategy._calculate_indicators(sample_ohlcv_df)

        # Calculate expected typical price
        expected_typical = (sample_ohlcv_df['high'] + sample_ohlcv_df['low'] + sample_ohlcv_df['close']) / 3.0

        # Compare with actual
        pd.testing.assert_series_equal(
            df_with_indicators['typical_price'],
            expected_typical,
            check_names=False
        )


class TestBbandRsiSignals:
    """Tests for signal generation logic."""

    def test_long_signal_on_oversold_and_below_lower_band(self, fixed_timestamp):
        """Test LONG signal when RSI < 30 AND close < lower band."""
        strategy = BbandRsi()

        # Create data where last candle is oversold and below lower band
        dates = pd.date_range('2024-01-01', periods=50, freq='1h', tz='UTC')

        # Start with normal prices
        prices = [42000.0 + i * 10 for i in range(45)]
        # Then create a sharp drop (oversold condition)
        prices.extend([41000.0, 40500.0, 40000.0, 39500.0, 39000.0])

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 100 for p in prices],
            'low': [p - 100 for p in prices],
            'close': prices,
            'volume': [100.0] * 50
        })

        result = strategy.run(df, fixed_timestamp)

        # After sharp drop, RSI should be low and price should be below lower band
        # This should trigger LONG signal
        assert result.signal == SignalType.LONG

    def test_flat_signal_on_overbought(self, fixed_timestamp):
        """Test FLAT signal when RSI > 70."""
        strategy = BbandRsi()

        # Create data where last candles show overbought condition
        dates = pd.date_range('2024-01-01', periods=50, freq='1h', tz='UTC')

        # Start with normal prices
        prices = [42000.0 + i * 5 for i in range(45)]
        # Then create a sharp rise (overbought condition)
        prices.extend([43000.0, 43500.0, 44000.0, 44500.0, 45000.0])

        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 100 for p in prices],
            'low': [p - 100 for p in prices],
            'close': prices,
            'volume': [100.0] * 50
        })

        result = strategy.run(df, fixed_timestamp)

        # After sharp rise, RSI should be high
        # This should trigger FLAT signal
        assert result.signal == SignalType.FLAT

    def test_hold_signal_with_nan_indicators(self, fixed_timestamp):
        """Test HOLD when indicators are NaN (warmup period)."""
        strategy = BbandRsi()

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

    def test_hold_signal_in_neutral_market(self, sample_ohlcv_df, fixed_timestamp):
        """Test signal when market is neutral or trending."""
        strategy = BbandRsi()

        result = strategy.run(sample_ohlcv_df, fixed_timestamp)

        # Sample data has gradual uptrend, RSI will determine signal
        # Should be HOLD or FLAT (depending on RSI level)
        assert result.signal in [SignalType.HOLD, SignalType.FLAT]


class TestBbandRsiIntegration:
    """Integration tests for full strategy execution."""

    def test_run_with_valid_fixture_data(self, load_fixture_df, fixed_timestamp):
        """Test full strategy run with valid fixture data."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        assert isinstance(result, StrategyRecommendation)
        assert isinstance(result.signal, SignalType)
        assert result.timestamp == fixed_timestamp

    def test_strategy_is_deterministic(self, load_fixture_df, fixed_timestamp):
        """Test strategy produces same result with same input."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result1 = strategy.run(df.copy(), fixed_timestamp)
        result2 = strategy.run(df.copy(), fixed_timestamp)

        assert result1.signal == result2.signal
        assert result1.timestamp == result2.timestamp

    def test_strategy_with_minimal_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with minimal fixture (edge case)."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_minimal.csv')  # Only 20 candles

        result = strategy.run(df, fixed_timestamp)

        # Should return HOLD due to insufficient data
        assert result.signal == SignalType.HOLD

    def test_strategy_with_extended_fixture(self, load_fixture_df, fixed_timestamp):
        """Test strategy with extended fixture (200 candles)."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_200.csv')

        result = strategy.run(df, fixed_timestamp)

        # Should work fine with more data
        assert isinstance(result, StrategyRecommendation)
        assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]

    def test_output_format_correctness(self, load_fixture_df, fixed_timestamp):
        """Test output follows StrategyRecommendation format."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        result = strategy.run(df, fixed_timestamp)

        # Check it's a StrategyRecommendation NamedTuple
        assert hasattr(result, 'signal')
        assert hasattr(result, 'timestamp')
        assert len(result) == 2  # NamedTuple with 2 fields

    def test_timestamp_propagation(self, load_fixture_df):
        """Test that input timestamp is propagated to output."""
        strategy = BbandRsi()
        df = load_fixture_df('btc_usdt_1h_100.csv')

        # Use different timestamps
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 2, 15, 18, 30, 0, tzinfo=timezone.utc)

        result1 = strategy.run(df, ts1)
        result2 = strategy.run(df, ts2)

        assert result1.timestamp == ts1
        assert result2.timestamp == ts2
