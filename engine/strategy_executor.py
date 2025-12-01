from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from config import MAX_STRATEGY_RUNTIME
import importlib


def load_strategy_class(module_path: str, class_name: str):
    """
    Dynamically import a strategy class.
    """
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def execute_strategies_parallel(strategies_to_run, data_map, now):
    """
    Run strategies in parallel using ThreadPoolExecutor.
    """

    results = {}

    def run_single_strategy(name, cfg):
        cls = load_strategy_class(cfg["module"], cfg["class_name"])
        instance = cls()
        df = data_map[name]

        # run strategy
        rec = instance.run(df, now)

        # calculate execution time
        exec_ms = (rec.timestamp - now).total_seconds() * 1000

        return {
            "name": name,
            "signal": rec.signal.value,
            "decision_time": rec.timestamp,
            "exec_time_ms": exec_ms,
        }

    with ThreadPoolExecutor(max_workers=len(strategies_to_run)) as executor:
        futures = {
            executor.submit(run_single_strategy, name, cfg): name
            for name, cfg in strategies_to_run
        }

        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result(timeout=MAX_STRATEGY_RUNTIME)
                results[name] = result

            except TimeoutError:
                results[name] = {"error": f"timeout after {MAX_STRATEGY_RUNTIME} seconds"}

            except Exception as e:
                results[name] = {"error": str(e)}

    return results