# Test Fixtures

This directory contains CSV fixtures for strategy unit tests.

## Files

- **btc_usdt_1h_100.csv**: 100 hours of BTC/USDT 1h candles (standard fixture)
  - Used by: Most strategy tests
  - Covers: VolatilitySystem (52 req), OTTStrategy (30 req), BbandRsi (30 req)

- **btc_usdt_1h_200.csv**: 200 hours of BTC/USDT 1h candles (extended fixture)
  - Used by: SupertrendStrategy tests (requires 100+ candles)
  - Covers: All strategies with extended lookback

- **btc_usdt_1h_minimal.csv**: 20 hours of BTC/USDT 1h candles (edge case testing)
  - Used by: Edge case and validation tests
  - Purpose: Testing MIN_CANDLES_REQUIRED validation

## Format

All CSV files follow this format:

```csv
date,open,high,low,close,volume
2024-01-01 00:00:00+00:00,42000.50,42500.75,41800.25,42300.00,125.45
2024-01-01 01:00:00+00:00,42300.00,42800.00,42100.00,42650.50,98.32
```

**Requirements:**
- Timezone-aware UTC timestamps (must include `+00:00`)
- Chronological order (no gaps)
- Realistic OHLCV values
- Volume > 0

## Regenerating Fixtures

To regenerate fixtures from live Binance data:

```bash
cd tests/fixtures
python generate_fixtures.py
```

**Note:** This requires internet connection and fetches real historical data from Binance.

## Usage in Tests

Load fixtures using the `load_fixture_df` pytest fixture:

```python
def test_strategy(load_fixture_df, fixed_timestamp):
    # Load 100 candles
    df = load_fixture_df('btc_usdt_1h_100.csv')

    # Run strategy
    strategy = MyStrategy()
    result = strategy.run(df, fixed_timestamp)

    assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]
```
