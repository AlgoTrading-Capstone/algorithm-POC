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

# Step 1: Market data sync
from db.market_data import sync_market_data

# Step 2: Strategy scheduling (who should run this tick)
from engine.strategy_loader import get_strategies_to_run

# Step 3: Data preparation (load from DB + resample + trim)
from engine.data_prep import prepare_data_for_strategies

# Step 4: Parallel strategy execution
from engine.strategy_executor import execute_strategies_parallel


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

    print(f"[TICK] Tick scheduler started with CronTrigger: {cron_args}")

    return scheduler


def run_tick_cycle():
    """
    Execute one strategies tick cycle:
        1. Sync market data (exchange -> DB)
        2. Determine which strategies should run this tick
        3. Load & prepare OHLCV data for these strategies
        4. Run strategies in parallel
    """
    now = datetime.now(UTC)
    print(f"[TICK] Starting tick cycle at {now.strftime('%H:%M:%S.%f UTC')}")

    try:
        # -----------------------------------------------------
        # Step 1: Sync market data
        # -----------------------------------------------------
        print("[TICK] Step 1/4: Syncing market data from exchange...")
        new_candles = sync_market_data()
        print(f"[TICK] Synced {new_candles} new candles")

        # -----------------------------------------------------
        # Step 2: Determine which strategies should run now
        # -----------------------------------------------------
        print("[TICK] Step 2/4: Checking which strategies should run this tick...")
        strategies_to_run = get_strategies_to_run(now)

        if not strategies_to_run:
            print("[TICK] No strategies scheduled for this tick. Exiting tick.")
            return

        print(f"[TICK] {len(strategies_to_run)} strategies scheduled:")
        for name, cfg in strategies_to_run:
            print(f"       • {name} (TF={cfg['timeframe']}, LB={cfg['lookback_hours']}h)")

        # -----------------------------------------------------
        # Step 3: Prepare OHLCV data for strategies
        # -----------------------------------------------------
        print("[TICK] Step 3/4: Preparing data for strategies...")
        data_map = prepare_data_for_strategies(strategies_to_run)
        print("[TICK] Data preparation complete.")

        # -----------------------------------------------------
        # Step 4: Execute strategies in parallel
        # -----------------------------------------------------
        print("[TICK] Step 4/4: Executing strategies in parallel...")
        results = execute_strategies_parallel(
            strategies_to_run=strategies_to_run,
            data_map=data_map,
            now=now
        )

        print("[TICK] Strategy results:")
        for name, r in results.items():
            print(
                f"       • {r['name']}: "
                f"Decision: {r['signal']} | "
                f"Time: {r['decision_time'].strftime('%H:%M:%S.%f UTC')} | "
                f"Execution: {r['exec_time_ms']:.2f} ms"
            )

        print("[TICK] Tick cycle completed successfully")

    except Exception as e:
        print(f"[TICK] ERROR during tick cycle: {e}")
        # Continue - next tick will retry