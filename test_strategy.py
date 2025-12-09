#!/usr/bin/env python
"""
Bitcoin Strategy Testing Tool

Manually test trading strategies without waiting for scheduled tick intervals.

Usage:
    python test_strategy.py                        # Show help menu
    python test_strategy.py <strategy_name>        # Test single strategy
    python test_strategy.py --all                  # Test all enabled strategies
    python test_strategy.py <name> --live          # Use live database data
    python test_strategy.py <name> --fixture <f>   # Use specific fixture file
    NOTE: The keys in this JSON file (e.g., 'SupertrendStrategy', 'BbandRsi')
    are the definitive source for valid strategy names accepted by the CLI.

"""


import argparse
import importlib
import json
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd


def load_registry():
    """Load strategies registry from JSON."""
    registry_path = Path("strategies/strategies_registry.json")
    if not registry_path.exists():
        print(f"ERROR: Registry file not found: {registry_path}")
        sys.exit(1)

    with open(registry_path, "r") as f:
        return json.load(f)


def load_fixture(filename="btc_usdt_1h_100.csv"):
    """
    Load OHLCV test fixture data from tests/fixtures/ directory.

    Args:
        filename: CSV filename in tests/fixtures/ directory

    Returns:
        pandas.DataFrame with OHLCV data (UTC timezone-aware dates)
    """
    fixture_path = Path(f"tests/fixtures/{filename}")

    if not fixture_path.exists():
        print(f"ERROR: Fixture file not found: {fixture_path}")
        print("\nAvailable fixtures:")
        fixtures_dir = Path("tests/fixtures")
        if fixtures_dir.exists():
            for csv_file in sorted(fixtures_dir.glob("*.csv")):
                print(f"  - {csv_file.name}")
        sys.exit(1)

    df = pd.read_csv(fixture_path)
    df['date'] = pd.to_datetime(df['date'], utc=True)

    return df


def load_strategy_class(module_path, class_name):
    """
    Dynamically import and return strategy class.

    Args:
        module_path: Python module path (e.g. "strategies.supertrend_strategy")
        class_name: Class name to load (e.g. "SupertrendStrategy")

    Returns:
        Strategy class (not instance)
    """
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except ImportError as e:
        print(f"ERROR: Failed to import module '{module_path}': {e}")
        sys.exit(1)
    except AttributeError as e:
        print(f"ERROR: Class '{class_name}' not found in module '{module_path}': {e}")
        sys.exit(1)


def test_strategy(strategy_name, use_db=False, fixture=None):
    """
    Test a single strategy and display results.

    Args:
        strategy_name: Name of strategy from registry
        use_db: If True, use live database data; if False, use fixture
        fixture: Optional custom fixture filename

    Returns:
        StrategyRecommendation result
    """
    registry = load_registry()

    # Validate strategy exists
    if strategy_name not in registry:
        print(f"ERROR: Strategy '{strategy_name}' not found in registry")
        print(f"\nAvailable strategies: {', '.join(registry.keys())}")
        sys.exit(1)

    config = registry[strategy_name]

    # Load data
    print(f"\n{'='*60}")
    print(f"Testing Strategy: {strategy_name}")
    print(f"{'='*60}")

    if use_db:
        print("Data source: Live database")
        from db.market_data import fetch_ohlcv_dataframe

        try:
            df = fetch_ohlcv_dataframe(
                timeframe=config["timeframe"],
                lookback_hours=config["lookback_hours"]
            )
            print(f"Loaded {len(df)} candles from database")
        except Exception as e:
            print(f"ERROR: Failed to fetch database data: {e}")
            print("Tip: Ensure PostgreSQL/TimescaleDB is running and configured correctly")
            sys.exit(1)
    else:
        fixture_file = fixture or "btc_usdt_1h_100.csv"
        print(f"Data source: Fixture ({fixture_file})")
        df = load_fixture(fixture_file)
        print(f"Loaded {len(df)} candles from fixture")

    # Prepare data using engine's data preparation logic
    from engine.data_prep import prepare_data_for_strategies

    strategies_to_run = [(strategy_name, config)]
    data_map = prepare_data_for_strategies(strategies_to_run)
    df_prepared = data_map[strategy_name]

    # Display data info
    print(f"\nStrategy Configuration:")
    print(f"  Timeframe: {config['timeframe']}")
    print(f"  Lookback: {config['lookback_hours']} hours")
    print(f"  Enabled: {config['enabled']}")

    print(f"\nData Prepared:")
    print(f"  Rows (candles): {len(df_prepared)}")
    if len(df_prepared) > 0:
        print(f"  Date range: {df_prepared['date'].min()} to {df_prepared['date'].max()}")
        print(f"  Latest close: ${df_prepared['close'].iloc[-1]:,.2f}")

    # Load and instantiate strategy
    StrategyClass = load_strategy_class(config["module"], config["class_name"])
    strategy = StrategyClass()

    # Run strategy and measure execution time
    timestamp = datetime.now(UTC)
    start_time = time.perf_counter()

    try:
        result = strategy.run(df_prepared, timestamp)
        exec_time_ms = (time.perf_counter() - start_time) * 1000

        # Display results
        print(f"\n{'='*60}")
        print(f"RESULT:")
        print(f"  Signal: {result.signal.value}")
        print(f"  Timestamp: {result.timestamp}")
        print(f"  Execution time: {exec_time_ms:.2f} ms")
        print(f"{'='*60}\n")

        return result

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR during strategy execution:")
        print(f"  {type(e).__name__}: {e}")
        print(f"{'='*60}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def show_help_menu():
    """Display interactive help menu with available strategies."""
    registry = load_registry()

    print("\nBitcoin Strategy Testing Tool")
    print("=" * 60)
    print("\nAvailable Strategies (from registry):\n")

    # Sort strategies by name for consistent display
    sorted_strategies = sorted(registry.items())

    for idx, (name, config) in enumerate(sorted_strategies, 1):
        status = "[+] Enabled" if config.get("enabled", False) else "[ ] Disabled"
        timeframe = config.get("timeframe", "?")
        print(f"  {idx}. {name:25s} [{timeframe:>4s}] {status}")

    print("\nUsage:")
    print("  python test_strategy.py <strategy_name>     Test single strategy")
    print("  python test_strategy.py --all               Test all enabled")
    print("  python test_strategy.py <name> --live       Use live DB data")

    print("\nExamples:")
    print("  python test_strategy.py SupertrendStrategy")
    print("  python test_strategy.py --all")
    print("  python test_strategy.py BbandRsi --live")
    print(f"\n{'=' * 60}\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manual testing tool for Bitcoin trading strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_strategy.py                        # Show this help
  python test_strategy.py SupertrendStrategy     # Test single strategy
  python test_strategy.py --all                  # Test all enabled
  python test_strategy.py BbandRsi --live        # Use live database
        """
    )

    parser.add_argument(
        "strategy",
        nargs="?",
        help="Strategy name to test (e.g. SupertrendStrategy)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all enabled strategies from registry"
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live database data instead of test fixtures"
    )

    parser.add_argument(
        "--fixture",
        help="Specific fixture file to use (e.g. btc_usdt_1h_200.csv)"
    )

    args = parser.parse_args()

    # No arguments = show help menu
    if not args.strategy and not args.all:
        show_help_menu()
        return

    # Test all enabled strategies
    if args.all:
        registry = load_registry()
        enabled_strategies = {
            name: cfg for name, cfg in registry.items()
            if cfg.get("enabled", False)
        }

        if not enabled_strategies:
            print("No enabled strategies found in registry")
            return

        print(f"\nTesting {len(enabled_strategies)} enabled strategies...")

        results = {}
        for name in sorted(enabled_strategies.keys()):
            try:
                result = test_strategy(name, use_db=args.live, fixture=args.fixture)
                results[name] = result
            except SystemExit:
                # Strategy test failed, continue with others
                results[name] = None

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}")
        for name, result in results.items():
            if result:
                print(f"  {name:30s} -> {result.signal.value}")
            else:
                print(f"  {name:30s} -> ERROR")
        print(f"{'='*60}\n")

        return

    # Test single strategy
    if args.strategy:
        test_strategy(args.strategy, use_db=args.live, fixture=args.fixture)
        return

    # Shouldn't reach here, but show help just in case
    parser.print_help()


if __name__ == "__main__":
    main()