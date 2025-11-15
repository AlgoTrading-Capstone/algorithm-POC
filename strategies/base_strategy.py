"""
Base Strategy Interface

This module defines the abstract base class that all trading strategies must inherit from.
It establishes a universal contract for strategy input/output and core methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import pandas as pd


class SignalType(Enum):
    """
    Enumeration of possible trading signals.
    """
    LONG = "LONG"  # Enter or maintain long position
    SHORT = "SHORT"  # Enter or maintain short position
    FLAT = "FLAT"  # Exit position / Stay flat
    HOLD = "HOLD"  # Maintain current position (no action)


@dataclass
class StrategyRecommendation:
    """
    Universal output format for strategy recommendations.

    Attributes:
        signal: The trading signal (LONG/SHORT/FLAT/HOLD)
        confidence: Confidence level in the signal (0.0 to 1.0)
        timestamp: When this recommendation was generated
        metadata: Additional strategy-specific information
    """
    signal: SignalType
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any]

    def __post_init__(self):
        """Validate confidence is within valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert recommendation to dictionary format."""
        return {
            'signal': self.signal.value,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement:
    - populate_indicators: Calculate technical indicators
    - generate_signal: Produce trading recommendations

    Attributes:
        name: Unique identifier for this strategy
        timeframe: Primary timeframe used by the strategy (e.g., '1h', '15m')
        description: Human-readable description of the strategy
    """

    def __init__(self, name: str, timeframe: str, description: str = ""):
        """
        Initialize the base strategy.

        Args:
            name: Strategy identifier
            timeframe: Primary timeframe (e.g., '1h', '5m')
            description: Optional strategy description
        """
        self.name = name
        self.timeframe = timeframe
        self.description = description
        self._last_signal: Optional[StrategyRecommendation] = None

    @abstractmethod
    def populate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate and add technical indicators to the dataframe.

        This method should add new columns to the dataframe containing
        calculated indicators (e.g., ATR, RSI, moving averages).

        Args:
            dataframe: OHLCV data with columns: ['open', 'high', 'low', 'close', 'volume']

        Returns:
            DataFrame with added indicator columns

        Note:
            - Do not modify the original OHLCV columns
            - Ensure all indicator columns have meaningful names
            - Handle NaN values appropriately
        """
        pass

    @abstractmethod
    def generate_signal(self, dataframe: pd.DataFrame) -> StrategyRecommendation:
        """
        Generate a trading signal based on the populated indicators.

        This is the core logic method that determines what action to take
        based on current market conditions and calculated indicators.

        Args:
            dataframe: DataFrame with OHLCV data and populated indicators

        Returns:
            StrategyRecommendation containing the signal and confidence

        Note:
            - Use the most recent (last) row for current market state
            - Consider previous rows for trend/pattern analysis
            - Set appropriate confidence levels based on signal strength
        """
        pass

    def run(self, dataframe: pd.DataFrame) -> StrategyRecommendation:
        """
        Execute the complete strategy workflow.

        This is the main entry point that:
        1. Populates indicators
        2. Generates signal
        3. Caches the last signal

        Args:
            dataframe: Raw OHLCV data

        Returns:
            StrategyRecommendation for current market conditions
        """
        # Populate indicators
        df_with_indicators = self.populate_indicators(dataframe)

        # Generate signal
        signal = self.generate_signal(df_with_indicators)

        # Cache last signal
        self._last_signal = signal

        return signal

    def get_last_signal(self) -> Optional[StrategyRecommendation]:
        """
        Get the most recently generated signal.

        Returns:
            Last StrategyRecommendation or None if no signal generated yet
        """
        return self._last_signal

    def __repr__(self) -> str:
        """String representation of the strategy."""
        return f"{self.__class__.__name__}(name='{self.name}', timeframe='{self.timeframe}')"