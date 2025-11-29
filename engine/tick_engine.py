"""
Tick engine using APScheduler (Cron-based).

This module registers a scheduler that executes the system tick
according to GLOBAL_TICK aligned to real candle boundaries.
"""

from datetime import datetime, UTC
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import GLOBAL_TICK
from utils.timeframes import timeframe_to_cron
from db.market_data import sync_market_data, fetch_ohlcv_dataframe


def start_tick_scheduler():
    """
    Start the APScheduler with a CronTrigger based on GLOBAL_TICK.
    The scheduler runs in the background and does not block the main thread.
    """
    cron_args = timeframe_to_cron(GLOBAL_TICK)
    trigger = CronTrigger(**cron_args)

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_tick_cycle, trigger)
    scheduler.start()

    print(f"Tick scheduler started with CronTrigger: {cron_args}")

    return scheduler


def run_tick_cycle():
    """
    Execute one trading tick:
        1. Sync market data (exchange -> DB)
        2. Load strategy data from DB
        3. Run strategies
    """
    print("\n" + "=" * 60)
    print(f"[TICK] Starting tick cycle at {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    try:
        # 1. Sync market data
        print("\n[TICK] Step 1/3: Syncing market data from exchange")
        new_candles = sync_market_data()
        print(f"[TICK] Synced {new_candles} new candles\n")

        # 2. Load strategy data
        print("[TICK] Step 2/3: Loading strategy data from database")
        df = fetch_ohlcv_dataframe()
        print(f"[TICK] Loaded {len(df)} candles for strategies\n")

        # 3. Execute strategies (to be implemented)
        print("[TICK] Step 3/3: Executing strategies")
        # execute_strategies(df) - omer
        print("[TICK] Strategies executed (placeholder)\n")

        print("[TICK] Tick cycle completed successfully")

    except Exception as e:
        print(f"[TICK] ERROR during tick cycle: {e}")
        # Continue - next tick will retry

    print("=" * 60 + "\n")