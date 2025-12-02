"""
Shared pytest fixtures for trading strategy tests.

This module provides reusable fixtures for loading test data,
managing timestamps, and creating sample DataFrames.
"""
import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from freezegun import freeze_time

# Path to fixture files
FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_dir() -> Path:
    """Return path to fixtures directory."""
    return FIXTURE_DIR


@pytest.fixture
def load_fixture_df(fixture_dir):
    """
    Fixture factory to load OHLCV CSV files.

    Usage:
        df = load_fixture_df('btc_usdt_1h_100.csv')

    Returns:
        Callable that loads CSV and returns pandas DataFrame
    """
    def _load(filename: str) -> pd.DataFrame:
        filepath = fixture_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Fixture not found: {filepath}")

        df = pd.read_csv(filepath)

        # Ensure date column is timezone-aware UTC datetime
        df['date'] = pd.to_datetime(df['date'], utc=True)

        # Validate required columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in fixture: {missing}")

        return df

    return _load


@pytest.fixture
def fixed_timestamp():
    """
    Provide a fixed UTC timestamp for deterministic testing.
    Uses freezegun to freeze time at 2024-01-05 12:00:00 UTC.

    Returns:
        datetime: Fixed UTC datetime object
    """
    with freeze_time("2024-01-05 12:00:00", tz_offset=0):
        yield datetime.now(timezone.utc)


@pytest.fixture
def sample_ohlcv_df():
    """
    Minimal in-memory DataFrame for quick tests that don't need full fixtures.
    Generates 50 candles with simple uptrend pattern.

    Returns:
        pandas.DataFrame: 50 rows of OHLCV data
    """
    dates = pd.date_range(
        start='2024-01-01 00:00:00',
        periods=50,
        freq='1h',
        tz='UTC'
    )

    # Simple uptrend pattern
    base_price = 42000
    data = {
        'date': dates,
        'open': [base_price + i * 10 for i in range(50)],
        'high': [base_price + i * 10 + 100 for i in range(50)],
        'low': [base_price + i * 10 - 50 for i in range(50)],
        'close': [base_price + i * 10 + 50 for i in range(50)],
        'volume': [100.0] * 50
    }

    return pd.DataFrame(data)
