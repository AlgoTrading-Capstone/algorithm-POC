"""
Data preparation module for strategy execution.

This module:
- Loads OHLCV data once (using global config settings)
- Resamples the data for each strategy's timeframe
- Trims to the strategy's lookback_hours
- Returns a dict: { strategy_name: prepared_df }
"""

from db.market_data import fetch_ohlcv_dataframe
from utils.resampling import resample_to_interval
from utils.timeframes import timeframe_to_minutes
import config


def prepare_data_for_strategies(strategies_to_run):
    """
    Prepare OHLCV data for each strategy.

    Args:
        strategies_to_run (list):
            A list of (name, cfg) entries returned from get_strategies_to_run().

    Returns:
        dict:
            {
                "StrategyName": pandas.DataFrame,
                ...
            }
    """

    # ----------------------------------------------------
    # 1. Load base data once using config.py
    # ----------------------------------------------------
    print(f"[PREP] Loading base data: timeframe={config.MIN_TIMEFRAME}, "
          f"lookback={config.MAX_LOOKBACK_HOURS}h")

    df_base = fetch_ohlcv_dataframe(
        timeframe=config.MIN_TIMEFRAME,
        lookback_hours=config.MAX_LOOKBACK_HOURS
    )

    # ----------------------------------------------------
    # 2. Prepare data per strategy
    # ----------------------------------------------------
    result_map = {}

    for name, cfg in strategies_to_run:
        strategy_tf = cfg["timeframe"]
        strategy_lb = cfg["lookback_hours"]

        print(f"[PREP] Preparing data for {name} | TF={strategy_tf}, LB={strategy_lb}h")

        # Step A: Resample to strategy timeframe
        df_resampled = resample_to_interval(df_base, strategy_tf)

        # Step B: Calculate how many bars the strategy needs
        tf_minutes = timeframe_to_minutes(strategy_tf)
        bars_needed = max(1, int(strategy_lb * 60 / tf_minutes))

        # Step C: Trim to lookback bars
        df_final = df_resampled.tail(bars_needed)

        # Store for execution
        result_map[name] = df_final

    # ----------------------------------------------------
    # 3. Return data map
    # ----------------------------------------------------
    return result_map