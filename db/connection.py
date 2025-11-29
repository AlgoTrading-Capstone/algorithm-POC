"""
Database connection management.
Provides SQLAlchemy engine and connection utilities.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'bitcoin_rl',
    'user': 'postgres',
    'password': 'postgres123'
}

# Create connection string
DATABASE_URL = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

# Create SQLAlchemy engine
engine_db = create_engine(DATABASE_URL, poolclass=NullPool)


def get_connection():
    """
    Returns a new database connection.

    Returns:
        Connection: SQLAlchemy connection object
    """
    return engine_db.connect()


def test_connection():
    """
    Tests database connection and verifies TimescaleDB installation.
    Prints connection status and TimescaleDB version.
    """
    try:
        with engine_db.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT version();"))
            pg_version = result.fetchone()[0]
            print(f"Connected to PostgreSQL")
            print(f"Version: {pg_version[:50]}...")

            # Check TimescaleDB extension
            result = conn.execute(text(
                "SELECT default_version, installed_version "
                "FROM pg_available_extensions "
                "WHERE name='timescaledb';"
            ))
            version = result.fetchone()

            if version and version[1]:
                print(f"TimescaleDB installed")
                print(f"Version: {version[1]}")
            else:
                print("TimescaleDB extension not found")

    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    # Run connection test when executed directly
    test_connection()