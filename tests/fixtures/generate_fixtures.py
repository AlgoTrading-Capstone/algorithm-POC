"""
Generate CSV fixtures from Binance historical data.
Run once to create test fixtures.

Usage:
    python tests/fixtures/generate_fixtures.py
"""
import ccxt
import pandas as pd
from datetime import datetime
from pathlib import Path


def generate_fixture(symbol: str, timeframe: str, num_candles: int, output_file: str):
    """Fetch real OHLCV data from Binance and save to CSV."""
    print(f"Fetching {num_candles} candles of {symbol} {timeframe}...")

    exchange = ccxt.binance()

    # Fetch data starting from a fixed date for reproducibility
    since = exchange.parse8601('2024-01-01T00:00:00Z')
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=num_candles)

    # Convert to DataFrame
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

    # Save to CSV
    output_path = Path(__file__).parent / output_file
    df.to_csv(output_path, index=False)
    print(f"[OK] Generated {output_path} with {len(df)} candles")
    print(f"  Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
    print()


if __name__ == "__main__":
    print("=" * 70)
    print("Generating test fixtures from Binance")
    print("=" * 70)
    print()

    try:
        # Standard fixture (100 candles)
        generate_fixture('BTC/USDT', '1h', 100, 'btc_usdt_1h_100.csv')

        # Extended fixture for SupertrendStrategy (200 candles)
        generate_fixture('BTC/USDT', '1h', 200, 'btc_usdt_1h_200.csv')

        # Minimal fixture for edge case testing (20 candles)
        generate_fixture('BTC/USDT', '1h', 20, 'btc_usdt_1h_minimal.csv')

        print("=" * 70)
        print("[OK] All fixtures generated successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"[ERROR] Error generating fixtures: {e}")
        print("Make sure you have internet connection and CCXT is installed.")
        raise
