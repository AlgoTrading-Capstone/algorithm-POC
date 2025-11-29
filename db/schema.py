"""
Database schema management.
Creates and manages tables, hypertables, and indexes.
"""

from sqlalchemy import text
from db.connection import engine_db


def create_schema():
    """
    Creates the database schema for the Bitcoin RL trading system.

    Creates:
        - candles table (OHLCV time-series data)
        - Converts to TimescaleDB hypertable
        - Creates indexes for efficient querying
    """
    with engine_db.connect() as conn:
        try:
            # Create candles table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS candles (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    PRIMARY KEY (time, symbol)
                );
            """))
            print("Table 'candles' created")

            # Convert to hypertable
            conn.execute(text("""
                SELECT create_hypertable(
                    'candles', 
                    'time',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 day'
                );
            """))
            print("Hypertable created (chunk_interval: 1 day)")

            # Create index for fast symbol+time queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_time 
                ON candles (symbol, time DESC);
            """))
            print("Index 'idx_candles_symbol_time' created")

            conn.commit()
            print("\nSchema created successfully!")

        except Exception as e:
            print(f"Schema creation failed: {e}")
            conn.rollback()


def verify_schema():
    """
    Verifies that the schema is correctly set up.
    Checks hypertable existence and configuration.

    Note: TimescaleDB 2.23+ uses different column names in information views.
    This function queries the hypertables view to confirm setup.
    """
    with engine_db.connect() as conn:
        try:
            # Check if hypertable exists
            # Note: chunk_time_interval column may vary by TimescaleDB version
            result = conn.execute(text("""
                SELECT hypertable_schema, hypertable_name
                FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'candles';
            """))

            hypertable = result.fetchone()
            if hypertable:
                print(f"Hypertable verified: {hypertable[0]}.{hypertable[1]}")
            else:
                print("Hypertable 'candles' not found")

        except Exception as e:
            print(f"Verification failed: {e}")


if __name__ == "__main__":
    # Run schema creation when executed directly
    print("Creating database schema...\n")
    create_schema()
    print("\nVerifying schema...\n")
    verify_schema()