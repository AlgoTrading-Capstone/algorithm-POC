"""
Market data synchronization between exchange and database.

Provides functions to:
- Initialize historical market data (one-time fetch)
- Sync latest candles and prune old data (periodic)
- Load data for strategy execution (query DB)
"""

import time
from datetime import datetime, timedelta, UTC

import ccxt
import pandas as pd
from sqlalchemy import text

from db.connection import engine
import config


def initialize_market_data(
    symbol: str = None,
    timeframe: str = None,
    lookback_hours: int = None,
    exchange_name: str = None
) -> bool:
    """
    One-time historical data fetch from exchange to database.

    Args:
        symbol: Trading pair (default: config.TRADING_PAIR)
        timeframe: Candle interval (default: config.MIN_TIMEFRAME)
        lookback_hours: Historical data range (default: config.MAX_LOOKBACK_HOURS)
        exchange_name: Exchange to use (default: config.EXCHANGE_NAME)

    Returns:
        bool: True if data was fetched, False if data already exists (idempotent)

    Raises:
        ValueError: Invalid parameters
        ccxt.NetworkError: Exchange connection issues
        sqlalchemy.exc.SQLAlchemyError: Database errors
    """
    # Use config defaults
    symbol = symbol or config.TRADING_PAIR
    timeframe = timeframe or config.MIN_TIMEFRAME
    lookback_hours = lookback_hours or config.MAX_LOOKBACK_HOURS
    exchange_name = exchange_name or config.EXCHANGE_NAME

    # Check if data already exists (idempotency)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM candles WHERE symbol = :symbol"),
            {'symbol': symbol}
        )
        count = result.scalar()

        if count > 0:
            print(f"[INIT] Data already exists for {symbol} ({count} candles), skipping initialization")
            return False

    # Calculate time range
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=lookback_hours)

    print(f"[INIT] Initializing market data for {symbol} ({timeframe})")
    print(f"[INIT] Time range: {start_time} to {end_time}")
    print(f"[INIT] Fetching {lookback_hours} hours from {exchange_name}")

    # Initialize CCXT exchange
    exchange = getattr(ccxt, exchange_name)()

    # Fetch data with pagination
    all_candles = []
    since_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    print(f"[INIT] Fetching candles...")

    while since_ms < end_ms:
        candles = exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=since_ms,
            limit=1000
        )

        if not candles:
            break

        all_candles.extend(candles)

        # Update since to last candle timestamp + 1ms
        since_ms = candles[-1][0] + 1

        # Break if partial batch (less than 1000 = end of data)
        if len(candles) < 1000:
            break

        # Rate limit protection
        time.sleep(0.1)

        print(f"[INIT] Fetched {len(all_candles)} candles so far...")

    print(f"[INIT] Total fetched: {len(all_candles)} candles")

    # Convert to database format
    records = []
    for candle in all_candles:
        records.append({
            'time': datetime.fromtimestamp(candle[0] / 1000, tz=UTC),
            'symbol': symbol,
            'open': float(candle[1]),
            'high': float(candle[2]),
            'low': float(candle[3]),
            'close': float(candle[4]),
            'volume': float(candle[5])
        })

    # Bulk insert with conflict handling
    print(f"[INIT] Inserting {len(records)} candles into database...")

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO candles (time, symbol, open, high, low, close, volume)
            VALUES (:time, :symbol, :open, :high, :low, :close, :volume)
            ON CONFLICT (time, symbol) DO NOTHING
        """), records)

    print(f"[INIT] Successfully initialized {len(records)} candles for {symbol}")
    return True


def sync_market_data(
    symbol: str = None,
    timeframe: str = None,
    lookback_hours: int = None,
    exchange_name: str = None
) -> int:
    """
    Periodic sync: fetch latest candles and delete old data.
    Called every tick by run_tick_cycle().

    Args:
        symbol: Trading pair (default: config.TRADING_PAIR)
        timeframe: Candle interval (default: config.MIN_TIMEFRAME)
        lookback_hours: Data retention period (default: config.MAX_LOOKBACK_HOURS)
        exchange_name: Exchange to use (default: config.EXCHANGE_NAME)

    Returns:
        int: Number of new candles inserted

    Raises:
        ccxt.NetworkError: Exchange connection issues
        sqlalchemy.exc.SQLAlchemyError: Database errors
    """
    # Use config defaults
    symbol = symbol or config.TRADING_PAIR
    timeframe = timeframe or config.MIN_TIMEFRAME
    lookback_hours = lookback_hours or config.MAX_LOOKBACK_HOURS
    exchange_name = exchange_name or config.EXCHANGE_NAME

    print(f"[SYNC] Syncing market data for {symbol}")

    # Find most recent candle in database
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT MAX(time) FROM candles WHERE symbol = :symbol"),
            {'symbol': symbol}
        )
        last_time = result.scalar()

        if last_time is None:
            print(f"[SYNC] No data in database, calling initialize_market_data()")
            initialize_market_data(symbol, timeframe, lookback_hours, exchange_name)
            return 0

    print(f"[SYNC] Last candle in DB: {last_time}")

    # Fetch new candles since last_time
    since_ms = int(last_time.timestamp() * 1000) + 1

    exchange = getattr(ccxt, exchange_name)()
    candles = exchange.fetch_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        since=since_ms,
        limit=1000
    )

    if not candles:
        print(f"[SYNC] No new candles to fetch")
    else:
        print(f"[SYNC] Fetched {len(candles)} new candles from exchange")

        # Convert to database format
        records = []
        for candle in candles:
            records.append({
                'time': datetime.fromtimestamp(candle[0] / 1000, tz=UTC),
                'symbol': symbol,
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5])
            })

        # Insert new candles
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO candles (time, symbol, open, high, low, close, volume)
                VALUES (:time, :symbol, :open, :high, :low, :close, :volume)
                ON CONFLICT (time, symbol) DO NOTHING
            """), records)

        print(f"[SYNC] Inserted {len(records)} new candles")

    # Delete old data
    cutoff_time = datetime.now(UTC) - timedelta(hours=lookback_hours)

    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM candles WHERE symbol = :symbol AND time < :cutoff_time"),
            {'symbol': symbol, 'cutoff_time': cutoff_time}
        )
        deleted_count = result.rowcount

    print(f"[SYNC] Deleted {deleted_count} old candles (before {cutoff_time})")

    return len(candles) if candles else 0


def load_strategy_data(
    symbol: str = None,
    timeframe: str = None,
    lookback_hours: int = None
) -> pd.DataFrame:
    """
    Load OHLCV data from database for strategy execution.

    Args:
        symbol: Trading pair (default: config.TRADING_PAIR)
        timeframe: Candle interval (default: config.MIN_TIMEFRAME)
        lookback_hours: Data range to fetch (default: config.MAX_LOOKBACK_HOURS)

    Returns:
        pd.DataFrame: OHLCV data with columns:
            - date (datetime, UTC, timezone-aware)
            - open, high, low, close, volume (float, lowercase)
            Sorted by date ascending, ready for strategy consumption

    Raises:
        ValueError: No data available in database
        sqlalchemy.exc.SQLAlchemyError: Database errors
    """
    # Use config defaults
    symbol = symbol or config.TRADING_PAIR
    timeframe = timeframe or config.MIN_TIMEFRAME
    lookback_hours = lookback_hours or config.MAX_LOOKBACK_HOURS

    # Calculate time range
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=lookback_hours)

    print(f"[LOAD] Loading strategy data for {symbol} ({timeframe})")
    print(f"[LOAD] Time range: {start_time} to {end_time}")

    # Query database
    query = text("""
        SELECT time, open, high, low, close, volume
        FROM candles
        WHERE symbol = :symbol
          AND time >= :start_time
          AND time <= :end_time
        ORDER BY time ASC
    """)

    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={'symbol': symbol, 'start_time': start_time, 'end_time': end_time}
        )

    # Validate data exists
    if df.empty:
        error_msg = (
            f"No data available for {symbol} between {start_time} and {end_time}. "
            "Run initialize_market_data() first."
        )
        print(f"[LOAD] ERROR: {error_msg}")
        raise ValueError(error_msg)

    # Format for strategies
    df = df.rename(columns={'time': 'date'})  # Required by strategies
    df['date'] = pd.to_datetime(df['date'], utc=True)  # Ensure timezone-aware UTC

    # Ensure float types for OHLCV
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    # Final sort
    df = df.sort_values('date').reset_index(drop=True)

    print(f"[LOAD] Loaded {len(df)} candles ({df['date'].min()} to {df['date'].max()})")

    return df
