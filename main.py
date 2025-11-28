"""
Main entry point of the AlgoTrading POC.

Starts the tick scheduler and keeps the application running.
"""

from engine.tick_engine import start_tick_scheduler
import time


if __name__ == "__main__":
    # Perform initial database population from the exchange
    # initialize_market_data() - matan

    # Start the global tick engine
    scheduler = start_tick_scheduler()

    try:
        # Keep the main thread alive while the scheduler runs in the background
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Tick scheduler stopped. Exiting...")