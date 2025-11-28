"""
Global configuration for the AlgoTrading system.
"""

# Smallest candle size required by any strategy
MIN_TIMEFRAME = "1h"

# Amount of historical data the system should have (in hours)
MAX_LOOKBACK_HOURS = 720

# How often the strategy engine runs (system-wide tick)
GLOBAL_TICK = "1h"

# Exchange used for market data and trading (CCXT identifier)
EXCHANGE_NAME = "binance"

# Trading pair used by the system (CCXT format)
TRADING_PAIR = "BTC/USDT"