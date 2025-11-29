import json
from pathlib import Path
from datetime import datetime
from utils.timeframes import timeframe_to_minutes

# Resolve absolute path to the JSON file
REGISTRY_PATH = Path(__file__).resolve().parent.parent / "strategies" / "strategies_registry.json"


def should_run_strategy(cfg: dict, now: datetime) -> bool:
    """
    Returns True if this tick matches the closing moment of the strategy timeframe.
    """
    tf_minutes = timeframe_to_minutes(cfg["timeframe"])
    minutes_now = now.hour * 60 + now.minute

    return (minutes_now % tf_minutes) == 0


def load_strategy_definitions():
    """Load the JSON registry."""
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def get_strategies_to_run(now: datetime):
    """Return a list of strategies that are enabled AND should run at this tick."""
    registry = load_strategy_definitions()
    strategies_to_run = []

    for name, cfg in registry.items():
        if not cfg.get("enabled", False):
            continue

        if should_run_strategy(cfg, now):
            strategies_to_run.append((name, cfg))

    return strategies_to_run
