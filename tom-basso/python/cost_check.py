"""Check how much of each result is trading cost: rerun Keltner (21, 50) and 100 random seeds at zero cost.

Usage: python cost_check.py <data_dir> <results_dir>
"""

import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script dir
import more_tests
from engine import Config, run, stats


def _random_free(seed: int) -> float:
    res = run(more_tests.DATA["prices"], replace(Config(), entry="random", seed=seed, cost_bps=0.0), more_tests.DATA["tbill"])
    return stats(res.equity)["cagr"]


def main(data_dir: Path, out_dir: Path) -> None:
    more_tests._load(str(data_dir))
    rows = []
    for n in (21, 50):
        for bps in (5.0, 0.0):
            res = run(more_tests.DATA["prices"], replace(Config(), lookback=n, cost_bps=bps), more_tests.DATA["tbill"])
            rows.append({"system": f"Keltner {n}", "cost_bps": bps, "cagr": stats(res.equity)["cagr"]})
    with ProcessPoolExecutor(initializer=more_tests._load, initargs=(str(data_dir),)) as pool:
        free = pd.Series(list(pool.map(_random_free, range(100))))
    free.rename("cagr").to_csv(out_dir / "random_entry_zero_cost.csv", index=False)
    rand = pd.read_csv(out_dir / "random_entry.csv").cagr
    rows += [{"system": "Random entry (median of seeds)", "cost_bps": 5.0, "cagr": rand.median()},
             {"system": "Random entry (median of seeds)", "cost_bps": 0.0, "cagr": free.median()}]
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "cost_check.csv", index=False)
    print(out.round(4).to_string(index=False))
    print("zero-cost random seeds with CAGR > 0:", (free > 0).mean())
    k21 = rows[0]["cagr"]
    print("Keltner 21 beats this share of 500 random seeds:", round((rand < k21).mean(), 3))
    print("Keltner 50 beats this share:", round((rand < rows[2]["cagr"]).mean(), 3))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
