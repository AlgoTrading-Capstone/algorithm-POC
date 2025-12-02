# Trading Strategy Unit Tests

This directory contains unit tests for the Bitcoin trading system strategies.

## Quick Start

```bash
# Run all tests
pytest

# Run specific strategy tests
pytest tests/strategies/test_bband_rsi.py -v

# Run with coverage
pytest --cov=strategies --cov-report=html

# Run tests matching a pattern
pytest -k "signal"
```

## Project Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared pytest fixtures
├── README.md                   # This file
├── fixtures/                   # Test data
│   ├── __init__.py
│   ├── README.md
│   ├── generate_fixtures.py    # Script to fetch data from Binance
│   ├── btc_usdt_1h_100.csv    # 100 candles (standard)
│   ├── btc_usdt_1h_200.csv    # 200 candles (extended)
│   └── btc_usdt_1h_minimal.csv # 20 candles (edge cases)
└── strategies/                 # Strategy test files
    ├── __init__.py
    └── test_bband_rsi.py       # BbandRsi strategy tests
```

## Test Coverage

### Current Status

| Strategy | Tests | Coverage | Status |
|----------|-------|----------|--------|
| BbandRsi | 19 tests | 97% | ✅ Complete |
| VolatilitySystem | - | - | ⏳ TODO |
| OTTStrategy | - | - | ⏳ TODO |
| SupertrendStrategy | - | - | ⏳ TODO |

## Testing Philosophy

### Key Principles

1. **No GLOBAL_TICK waiting** - Tests call `strategy.run()` directly
2. **Deterministic** - pytest-freezegun for time control, static CSV fixtures
3. **Fast execution** - All tests complete in < 1 second
4. **Isolated** - No database, exchange API, or scheduler dependencies
5. **Comprehensive** - Cover initialization, validation, indicators, signals, integration

### What We Test

Each strategy test file includes 5 test classes:

1. **TestInit** - Strategy initialization
   - Verify name, timeframe, lookback_hours
   - Check MIN_CANDLES_REQUIRED

2. **TestValidation** - Input validation
   - Insufficient data → HOLD
   - None/empty DataFrame → HOLD
   - Edge cases

3. **TestIndicators** - Indicator calculations
   - Required columns added
   - Values in valid ranges
   - No unexpected NaN

4. **TestSignals** - Signal generation
   - LONG conditions
   - SHORT conditions (if applicable)
   - FLAT conditions
   - HOLD when no clear signal

5. **TestIntegration** - Full execution
   - Complete run() with valid data
   - Deterministic behavior
   - Correct output format

## Shared Fixtures

Defined in `conftest.py`:

### `load_fixture_df(filename)`

Factory to load CSV fixtures.

```python
def test_strategy(load_fixture_df):
    df = load_fixture_df('btc_usdt_1h_100.csv')
    # DataFrame with timezone-aware UTC timestamps
```

### `fixed_timestamp()`

Frozen UTC timestamp (2024-01-05 12:00:00 UTC).

```python
def test_strategy(fixed_timestamp):
    # timestamp is always 2024-01-05 12:00:00+00:00
    result = strategy.run(df, fixed_timestamp)
    assert result.timestamp == fixed_timestamp
```

### `sample_ohlcv_df()`

Quick in-memory DataFrame (50 candles, simple uptrend).

```python
def test_quick(sample_ohlcv_df):
    # 50 candles, no fixture loading needed
    result = strategy.run(sample_ohlcv_df, timestamp)
```

## Running Tests

### Basic Commands

```bash
# All tests
pytest

# Specific file
pytest tests/strategies/test_bband_rsi.py

# Specific class
pytest tests/strategies/test_bband_rsi.py::TestBbandRsiSignals

# Specific test
pytest tests/strategies/test_bband_rsi.py::TestBbandRsiSignals::test_long_signal_on_oversold_and_below_lower_band

# Verbose output
pytest -v

# Stop at first failure
pytest -x

# Show print statements
pytest -s
```

### Coverage Reporting

```bash
# Terminal report
pytest --cov=strategies

# HTML report
pytest --cov=strategies --cov-report=html
start htmlcov/index.html  # Windows

# Missing lines
pytest --cov=strategies --cov-report=term-missing
```

### Markers

Tests are categorized with markers:

```bash
# Run only unit tests
pytest -m unit

# Run only strategy tests
pytest -m strategy

# Run only edge case tests
pytest -m edge_case

# Skip slow tests
pytest -m "not slow"
```

## Writing New Strategy Tests

### Template

Use `test_bband_rsi.py` as a template. For a new strategy:

1. Create `tests/strategies/test_your_strategy.py`
2. Import the strategy class
3. Create 5 test classes: Init, Validation, Indicators, Signals, Integration
4. Use shared fixtures from conftest.py
5. Run: `pytest tests/strategies/test_your_strategy.py -v`

### Example Test

```python
def test_strategy_with_fixture(load_fixture_df, fixed_timestamp):
    \"\"\"Test strategy with real market data.\"\"\"
    strategy = YourStrategy()
    df = load_fixture_df('btc_usdt_1h_100.csv')

    result = strategy.run(df, fixed_timestamp)

    assert isinstance(result, StrategyRecommendation)
    assert result.signal in [SignalType.LONG, SignalType.SHORT, SignalType.FLAT, SignalType.HOLD]
    assert result.timestamp == fixed_timestamp
```

## Regenerating Fixtures

If you need fresh data:

```bash
cd tests/fixtures
python generate_fixtures.py
```

This fetches real historical data from Binance and saves to CSV.

## Benefits of This Approach

### ✅ No Waiting for GLOBAL_TICK

Instead of waiting hours for APScheduler:

```python
# OLD (slow): Wait for tick cycle
python main.py  # Wait 1 hour for GLOBAL_TICK...

# NEW (fast): Direct strategy testing
pytest  # Tests complete in 0.23 seconds!
```

### ✅ Deterministic Testing

- Frozen time with pytest-freezegun
- Static CSV fixtures (reproducible results)
- No network calls or database queries

### ✅ Fast Feedback Loop

```bash
# Edit strategy → Run tests → See results
pytest tests/strategies/test_bband_rsi.py
# 19 tests in 0.23 seconds!
```

### ✅ Isolated Testing

No need to mock:
- ❌ Database (strategies receive DataFrames directly)
- ❌ Exchange API (using CSV fixtures)
- ❌ APScheduler (calling strategy.run() directly)

Only need:
- ✅ pytest-freezegun (for time control)
- ✅ CSV fixtures (static test data)

## Next Steps

1. **Create tests for remaining strategies:**
   - `test_volatility_system.py`
   - `test_ott_strategy.py`
   - `test_supertrend_strategy.py`

2. **Add utility tests (optional):**
   - `test_resampling.py`
   - `test_timeframes.py`

3. **Integration tests (future):**
   - Test strategy loader
   - Test data preparation
   - Test parallel execution

## Troubleshooting

### Tests fail with import errors

Ensure you're in the project root and virtual environment is activated:

```bash
cd C:\Projects\algorithm-POC
.venv\Scripts\activate  # Windows
pytest
```

### Fixture not found

Check that CSV files exist:

```bash
ls tests/fixtures/*.csv
# Should see: btc_usdt_1h_100.csv, btc_usdt_1h_200.csv, btc_usdt_1h_minimal.csv
```

If missing, regenerate:

```bash
python tests/fixtures/generate_fixtures.py
```

### TA-Lib errors

TA-Lib requires the C library. See main README for installation instructions.

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-freezegun](https://github.com/ktosiek/pytest-freezegun)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- Project plan: `.claude/plans/giggly-knitting-scott.md`
