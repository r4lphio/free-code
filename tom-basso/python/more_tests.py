"""Tests 2 to 4: random entry, big-winner share, and a lookback sweep.

Usage: python more_tests.py <data_dir> <results_dir> [seeds]
"""

import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script dir
from engine import Config, run, stats

DATA: dict[str, object] = {}


def _load(data_dir: str) -> None:
    DATA["prices"] = pd.read_parquet(Path(data_dir) / "prices.parquet")
    DATA["tbill"] = pd.read_parquet(Path(data_dir) / "tbill.parquet")["irx"]


def _random_run(seed: int) -> dict[str, float]:
    res = run(DATA["prices"], replace(Config(), entry="random", seed=seed), DATA["tbill"])
    return {"seed": seed, **stats(res.equity, res.trades)}


def big_winners(trades: pd.DataFrame) -> pd.DataFrame:
    """Share of net trade profit that comes from the best trades, and what is left without them."""
    pnl = trades.pnl.sort_values(ascending=False).reset_index(drop=True)
    total = pnl.sum()
    rows = []
    for pct in (0.01, 0.02, 0.03, 0.05):
        k = max(1, round(len(pnl) * pct))
        rows.append({"top_pct": pct, "n_trades": k, "pnl_top": pnl[:k].sum(), "pnl_rest": pnl[k:].sum(), "pnl_total": total})
    return pd.DataFrame(rows)


def main(data_dir: Path, out_dir: Path, seeds: int) -> None:
    _load(str(data_dir))
    prices, tbill = DATA["prices"], DATA["tbill"]

    # Test 3: big winners, using the full-sizing Keltner system from test 1.
    trades = pd.read_csv(out_dir / "trades_case4.csv")
    bw = big_winners(trades)
    bw.to_csv(out_dir / "big_winners.csv", index=False)
    print(bw.round(0).to_string(index=False))
    top = trades.sort_values("pnl", ascending=False).head(10)
    print(top[["symbol", "side", "entry_date", "exit_date", "pnl_pct_equity"]].round(4).to_string(index=False))

    # Test 4: lookback sweep. He says he never optimizes and picked 21 because a month has 21 trading days.
    sweep = []
    for n in (9, 15, 21, 30, 40, 50):
        res = run(prices, replace(Config(), lookback=n), tbill)
        sweep.append({"lookback": n, **stats(res.equity, res.trades)})
    sweep = pd.DataFrame(sweep)
    sweep.to_csv(out_dir / "lookback_sweep.csv", index=False)
    print(sweep.round(3).to_string(index=False))

    # Test 2: random entry with his sizing and a 3 x ATR trailing stop.
    with ProcessPoolExecutor(initializer=_load, initargs=(str(data_dir),)) as pool:
        rand = pd.DataFrame(pool.map(_random_run, range(seeds)))
    rand.to_csv(out_dir / "random_entry.csv", index=False)
    print(rand.drop(columns="seed").describe(percentiles=[0.05, 0.5, 0.95]).round(3).to_string())
    print("share of seeds with CAGR > 0:", round((rand.cagr > 0).mean(), 3))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 200)
