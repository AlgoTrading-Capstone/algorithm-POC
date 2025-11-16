"""
Database module for Bitcoin RL Trading System.
Handles PostgreSQL + TimescaleDB connections and schema management.
"""

from .connection import engine, get_connection, test_connection
from .schema import create_schema

__all__ = ['engine', 'get_connection', 'test_connection', 'create_schema']