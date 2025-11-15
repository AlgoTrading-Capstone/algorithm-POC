"""
Volatility System Strategy - IMPROVED VERSION

Adapted from Freqtrade strategy.
Based on: https://www.tradingview.com/script/3hhs0XbR/

Strategy Logic:
- Uses ATR (Average True Range) to measure volatility
- Enters LONG when price change exceeds ATR (strong upward move)
- Enters SHORT when price change exceeds -ATR (strong downward move)
- Exits positions when opposite signal appears

IMPROVEMENTS:
- Now supports string timeframes (e.g., "3h" instead of 180)
- Uses timeframes.py utilities
"""

from datetime import datetime
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
from typing import Union

# Import utilities
from strategies.utils.resampling import resample_to_interval, resampled_merge
from strategies.utils.timeframes import timeframe_to_minutes

# Import base strategy components
from strategies.base_strategy import BaseStrategy, SignalType, StrategyRecommendation


class VolatilitySystem(BaseStrategy):
    """
    Volatility-based breakout strategy.

    The strategy resamples data to a longer timeframe, calculates ATR,
    and generates signals when price movements exceed the ATR threshold.

    Attributes:
        resample_minutes: Resampling interval in minutes
        resample_timeframe: Original timeframe string (if provided)
        atr_period: Period for ATR calculation (default: 14)
        atr_multiplier: ATR multiplier for signal threshold (default: 2.0)
    """

    def __init__(
        self,
        name: str = "VolatilitySystem",
        timeframe: str = "1h",
        resample_timeframe: Union[str, int] = "3h",  # Can be "3h" or 180
        atr_period: int = 14,
        atr_multiplier: float = 2.0
    ):
        """
        Initialize the Volatility System strategy.

        Args:
            name: Strategy name
            timeframe: Primary timeframe (e.g., '1h')
            resample_timeframe: Resampling interval - can be:
                - String: "3h", "15m", "1d", etc.
                - Int: Number of minutes (e.g., 180)
                (default: "3h")
            atr_period: ATR calculation period (default: 14)
            atr_multiplier: Multiplier for ATR threshold (default: 2.0)

        Examples:
            # Using string timeframe (recommended):
            strategy = VolatilitySystem(resample_timeframe="3h")

            # Using minutes:
            strategy = VolatilitySystem(resample_timeframe=180)
        """
        super().__init__(
            name=name,
            timeframe=timeframe,
            description="Volatility breakout strategy using ATR"
        )

        # Convert resample_timeframe to minutes
        if isinstance(resample_timeframe, str):
            self.resample_minutes = timeframe_to_minutes(resample_timeframe)
            self.resample_timeframe = resample_timeframe
        else:
            self.resample_minutes = resample_timeframe
            self.resample_timeframe = f"{resample_timeframe}m"

        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def populate_indicators(self, dataframe: DataFrame) -> DataFrame:
        """
        Calculate volatility indicators.

        This method:
        1. Resamples data to a longer timeframe
        2. Calculates ATR on the resampled data
        3. Calculates close price changes
        4. Merges indicators back to original timeframe

        Args:
            dataframe: OHLCV data with columns: ['date', 'open', 'high', 'low', 'close', 'volume']
                       Note: 'date' column is required for resampling

        Returns:
            DataFrame with added indicators: 'atr', 'close_change', 'abs_close_change'
        """
        df = dataframe.copy()

        # Ensure 'date' column exists (required by resampling utilities)
        if 'date' not in df.columns and 'timestamp' in df.columns:
            df['date'] = df['timestamp']
        elif 'date' not in df.columns:
            raise ValueError("DataFrame must contain either 'date' or 'timestamp' column")

        # Resample to longer timeframe for smoother signals
        # Can pass either string ("3h") or int (180) - both work
        resampled = resample_to_interval(df, self.resample_timeframe)

        # Calculate Average True Range (ATR) on resampled data
        resampled['atr'] = ta.ATR(resampled, timeperiod=self.atr_period) * self.atr_multiplier

        # Calculate price changes
        resampled['close_change'] = resampled['close'].diff()
        resampled['abs_close_change'] = resampled['close_change'].abs()

        # Merge resampled indicators back to original timeframe
        df = resampled_merge(df, resampled, fill_na=True)

        # Extract the merged columns with proper naming
        # Note: prefix is now resample_{minutes}_ (not seconds)
        df['atr'] = df[f'resample_{self.resample_minutes}_atr']
        df['close_change'] = df[f'resample_{self.resample_minutes}_close_change']
        df['abs_close_change'] = df[f'resample_{self.resample_minutes}_abs_close_change']

        return df

    def generate_signal(self, dataframe: DataFrame) -> StrategyRecommendation:
        """
        Generate trading signal based on volatility breakout logic.

        Signal Logic:
        - LONG: When close_change > ATR (price breaks up through volatility)
        - SHORT: When close_change < -ATR (price breaks down through volatility)
        - FLAT: When opposite signal appears (reversal)
        - HOLD: No clear signal

        Args:
            dataframe: DataFrame with populated indicators

        Returns:
            StrategyRecommendation with signal and confidence
        """
        # Get current and previous candles
        if len(dataframe) < 2:
            return StrategyRecommendation(
                signal=SignalType.HOLD,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': 'Insufficient data'}
            )

        current = dataframe.iloc[-1]
        previous = dataframe.iloc[-2]

        # Check for valid indicators
        if pd.isna(current['atr']) or pd.isna(current['close_change']):
            return StrategyRecommendation(
                signal=SignalType.HOLD,
                confidence=0.0,
                timestamp=datetime.now(),
                metadata={'error': 'Invalid indicators (NaN values)'}
            )

        # Initialize signal and metadata
        signal = SignalType.HOLD
        confidence = 0.5
        metadata = {
            'atr': float(current['atr']),
            'close_change': float(current['close_change']),
            'abs_close_change': float(current['abs_close_change']),
            'price': float(current['close']),
            'resample_timeframe': self.resample_timeframe  # Added for debugging
        }

        # Entry Logic: Volatility breakout
        # LONG: Price change exceeds ATR threshold (strong upward move)
        if current['close_change'] > previous['atr']:
            signal = SignalType.LONG
            confidence = min(0.9, 0.6 + (current['abs_close_change'] / current['atr']) * 0.3)
            metadata['signal_reason'] = 'Volatility breakout - LONG'
            metadata['breakout_ratio'] = float(current['close_change'] / current['atr'])

        # SHORT: Price change exceeds -ATR threshold (strong downward move)
        elif current['close_change'] < -previous['atr']:
            signal = SignalType.SHORT
            confidence = min(0.9, 0.6 + (current['abs_close_change'] / current['atr']) * 0.3)
            metadata['signal_reason'] = 'Volatility breakout - SHORT'
            metadata['breakout_ratio'] = float(current['close_change'] / current['atr'])

        # Exit Logic: Opposite signal = reversal
        # Note: In Freqtrade, exit_long triggers when enter_short appears
        # We implement this by checking for strong opposite moves
        else:
            # Check if we're in a ranging market (low volatility)
            volatility_ratio = current['abs_close_change'] / current['atr']

            if volatility_ratio < 0.3:
                signal = SignalType.HOLD
                confidence = 0.3
                metadata['signal_reason'] = 'Low volatility - ranging market'
                metadata['volatility_ratio'] = float(volatility_ratio)
            else:
                signal = SignalType.HOLD
                confidence = 0.5
                metadata['signal_reason'] = 'No clear breakout'
                metadata['volatility_ratio'] = float(volatility_ratio)

        return StrategyRecommendation(
            signal=signal,
            confidence=confidence,
            timestamp=datetime.now(),
            metadata=metadata
        )


# Example usage and testing
if __name__ == "__main__":
    """
    Example of how to use the VolatilitySystem strategy.
    
    Note: This requires actual OHLCV data to run.
    """

    print("=" * 60)
    print("VOLATILITY SYSTEM - IMPROVED VERSION")
    print("=" * 60)

    # Example 1: Using string timeframe (recommended)
    print("\n1. Using string timeframe:")
    strategy1 = VolatilitySystem(
        name="VolatilitySystem",
        timeframe="1h",
        resample_timeframe="3h",  # ← String!
        atr_period=14,
        atr_multiplier=2.0
    )

    print(f"   Strategy: {strategy1}")
    print(f"   Timeframe: {strategy1.timeframe}")
    print(f"   Resample: {strategy1.resample_timeframe} ({strategy1.resample_minutes} minutes)")

    # Example 2: Using minutes (backward compatible)
    print("\n2. Using minutes (backward compatible):")
    strategy2 = VolatilitySystem(
        name="VolatilitySystem",
        timeframe="1h",
        resample_timeframe=180,  # ← Integer!
        atr_period=14,
        atr_multiplier=2.0
    )

    print(f"   Strategy: {strategy2}")
    print(f"   Timeframe: {strategy2.timeframe}")
    print(f"   Resample: {strategy2.resample_timeframe} ({strategy2.resample_minutes} minutes)")

    # Example 3: Different timeframes
    print("\n3. Testing different resample timeframes:")
    for tf in ["15m", "1h", "4h", "1d"]:
        strategy = VolatilitySystem(resample_timeframe=tf)
        print(f"   {tf:4s} → {strategy.resample_minutes:4d} minutes")

    print("\n" + "=" * 60)
    print("To use with real data:")
    print("=" * 60)
    print("""
    import ccxt
    import pandas as pd
    
    # Fetch data from exchange
    exchange = ccxt.kraken()
    ohlcv = exchange.fetch_ohlcv('BTC/USD', timeframe='1h', limit=100)
    
    # Convert to DataFrame with 'date' column (required!)
    df = pd.DataFrame(
        ohlcv, 
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Run strategy
    strategy = VolatilitySystem(resample_timeframe="3h")
    recommendation = strategy.run(df)
    
    print(f"Signal: {recommendation.signal.value}")
    print(f"Confidence: {recommendation.confidence:.2%}")
    print(f"Metadata: {recommendation.metadata}")
    """)