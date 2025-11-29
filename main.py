"""
Main entry point of the AlgoTrading POC.

Starts the tick scheduler and keeps the application running.
"""

from engine.tick_engine import start_tick_scheduler
from db.market_data import initialize_market_data
import time


if __name__ == "__main__":
    print("=" * 60)
    print("Starting Bitcoin Meta-RL Trading System")
    print("=" * 60)

    # Initialize market data (one-time historical fetch)
    try:
        print("\n[MAIN] Initializing market data...")
        initialize_market_data()
        print("[MAIN] Market data initialization complete\n")
    except Exception as e:
        print(f"[MAIN] ERROR: Failed to initialize market data: {e}")
        raise

    # Start the global tick engine
    print("[MAIN] Starting tick scheduler\n")
    scheduler = start_tick_scheduler()

    try:
        # Keep the main thread alive while the scheduler runs in the background
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\n[MAIN] Shutting down...")
        scheduler.shutdown()
        print("[MAIN] Tick scheduler stopped. Exiting...")