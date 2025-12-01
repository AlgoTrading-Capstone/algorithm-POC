"""
Supertrend Strategy

Adapted from Freqtrade Supertrend strategy by @juankysoriano.

Logic:
    - Calculate 3 Supertrend indicators with different multiplier/period combinations
    - LONG when all 3 indicators are 'up'
    - Uses hyperopt-optimized parameters (buy_m1=4, buy_p1=8, etc.)

Note: Exit logic removed as exits are handled by meta-strategy layer.
      Only buy parameters are used (sell parameters removed).

Supertrend implementation from: https://github.com/freqtrade/freqtrade-strategies/issues/30
"""

from datetime import datetime

import pandas as pd
import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from strategies.base_strategy import (BaseStrategy, SignalType, StrategyRecommendation)


class SupertrendStrategy(BaseStrategy):
    """
    Supertrend Strategy for Bitcoin trading.
    Uses 3 Supertrend indicators with optimized parameters.
    """

    # Supertrend needs period candles to initialize, longest period is 9
    # Original startup_candle_count was 199, using conservative 100
    MIN_CANDLES_REQUIRED = 100

    # Hyperopt-optimized parameters (from original buy_params)
    BUY_M1 = 4
    BUY_M2 = 7
    BUY_M3 = 1
    BUY_P1 = 8
    BUY_P2 = 9
    BUY_P3 = 8

    def __init__(self):
        super().__init__(
            name="SupertrendStrategy",
            description="Triple Supertrend strategy with hyperopt-optimized parameters.",
            timeframe="1h",
            lookback_hours=124  # 100 candles + 24h buffer for 1h timeframe
        )

    def _supertrend(self, df: DataFrame, multiplier: int, period: int) -> DataFrame:
        """
        Calculate Supertrend indicator.
        EXACT copy of original supertrend() method logic.

        Adapted from: https://github.com/freqtrade/freqtrade-strategies/issues/30
        """
        df = df.copy()

        df['TR'] = ta.TRANGE(df)
        df['ATR'] = ta.SMA(df['TR'], period)

        st = 'ST_' + str(period) + '_' + str(multiplier)
        stx = 'STX_' + str(period) + '_' + str(multiplier)

        # Compute basic upper and lower bands
        df['basic_ub'] = (df['high'] + df['low']) / 2 + multiplier * df['ATR']
        df['basic_lb'] = (df['high'] + df['low']) / 2 - multiplier * df['ATR']

        # Compute final upper and lower bands
        df['final_ub'] = 0.00
        df['final_lb'] = 0.00
        for i in range(period, len(df)):
            df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or df['close'].iat[i - 1] > df['final_ub'].iat[i - 1] else df['final_ub'].iat[i - 1]
            df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or df['close'].iat[i - 1] < df['final_lb'].iat[i - 1] else df['final_lb'].iat[i - 1]

        # Set the Supertrend value
        df[st] = 0.00
        for i in range(period, len(df)):
            df[st].iat[i] = df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] <= df['final_ub'].iat[i] else \
                            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] >  df['final_ub'].iat[i] else \
                            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] >= df['final_lb'].iat[i] else \
                            df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] <  df['final_lb'].iat[i] else 0.00

        # Mark the trend direction up/down
        df[stx] = np.where((df[st] > 0.00), np.where((df['close'] < df[st]), 'down',  'up'), np.NaN)

        # Remove basic and final bands from the columns
        df.drop(['basic_ub', 'basic_lb', 'final_ub', 'final_lb'], inplace=True, axis=1)

        df.fillna(0, inplace=True)

        return DataFrame(index=df.index, data={
            'ST': df[st],
            'STX': df[stx]
        })

    def _calculate_indicators(self, df: DataFrame) -> DataFrame:
        """
        Reproduce populate_indicators() logic from Freqtrade version.

        Only calculates the 3 buy indicators with optimized parameters.
        Exit indicators removed as exits are handled by meta-strategy layer.
        """
        # Calculate 3 Supertrend indicators for buy signals
        result1 = self._supertrend(df, self.BUY_M1, self.BUY_P1)
        df[f'supertrend_1_buy_{self.BUY_M1}_{self.BUY_P1}'] = result1['STX']

        result2 = self._supertrend(df, self.BUY_M2, self.BUY_P2)
        df[f'supertrend_2_buy_{self.BUY_M2}_{self.BUY_P2}'] = result2['STX']

        result3 = self._supertrend(df, self.BUY_M3, self.BUY_P3)
        df[f'supertrend_3_buy_{self.BUY_M3}_{self.BUY_P3}'] = result3['STX']

        return df

    def _generate_signal(self, df: DataFrame) -> SignalType:
        """
        Reproduce populate_entry_trend() logic.

        LONG when all 3 buy supertrend indicators are 'up' AND volume > 0
        Otherwise HOLD.

        Note: Exit logic removed as handled by meta-strategy layer.
        """
        if len(df) < 1:
            return SignalType.HOLD

        last_row = df.iloc[-1]

        # Get the 3 supertrend indicator values
        st1_col = f'supertrend_1_buy_{self.BUY_M1}_{self.BUY_P1}'
        st2_col = f'supertrend_2_buy_{self.BUY_M2}_{self.BUY_P2}'
        st3_col = f'supertrend_3_buy_{self.BUY_M3}_{self.BUY_P3}'

        # Check if columns exist
        if st1_col not in df.columns or st2_col not in df.columns or st3_col not in df.columns:
            return SignalType.HOLD

        st1_value = last_row[st1_col]
        st2_value = last_row[st2_col]
        st3_value = last_row[st3_col]
        volume = last_row['volume']

        # Check for NaN or missing values
        if pd.isna(st1_value) or pd.isna(st2_value) or pd.isna(st3_value) or pd.isna(volume):
            return SignalType.HOLD

        # LONG signal: All 3 indicators are 'up' AND volume > 0
        if (st1_value == 'up' and
            st2_value == 'up' and
            st3_value == 'up' and
            volume > 0):
            return SignalType.LONG

        return SignalType.HOLD

    def run(self, df: pd.DataFrame, timestamp: datetime) -> StrategyRecommendation:
        """Execute the Supertrend Strategy logic."""

        if df is None or len(df) < self.MIN_CANDLES_REQUIRED:
            return StrategyRecommendation(signal=SignalType.HOLD, timestamp=timestamp)

        df = df.copy()
        df = self._calculate_indicators(df)

        signal = self._generate_signal(df)

        return StrategyRecommendation(signal=signal, timestamp=timestamp)