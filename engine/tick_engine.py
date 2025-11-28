"""
Tick engine using APScheduler (Cron-based).

This module registers a scheduler that executes the system tick
according to GLOBAL_TICK aligned to real candle boundaries.
"""

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import GLOBAL_TICK
from utils.timeframes import timeframe_to_cron


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
    print(f"[{datetime.utcnow()}] Starting tick...")

    # sync_market_data() - matan
    # load_strategy_data() - omer
    # execute_strategies() - omer

    print(f"[{datetime.utcnow()}] Tick finished.\n")