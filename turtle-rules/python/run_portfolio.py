"""Run both Turtle systems on the whole portfolio at several unit sizes, before and after costs.

Usage: python run_portfolio.py data
Prints a table and writes results/portfolio.csv.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import pandas as pd

from engine import Config, run, stats

DATA: dict = {}


def load(data_dir: str) -> None:
    DATA["prices"] = pd.read_parquet(Path(data_dir) / "prices.parquet")
    DATA["tbill"] = pd.read_parquet(Path(data_dir) / "tbill.parquet")["irx"]


def one(cfg: Config) -> dict:
    res = run(DATA["prices"], cfg, DATA["tbill"])
    st = stats(res.equity, res.trades)
    return {"system": cfg.system, "risk_per_n": cfg.risk, "cost_bps": cfg.cost_bps, "cagr": st["cagr"],
            "max_dd": st["max_dd"], "growth_of_1": st["growth"], "trades": st.get("trades", 0),
            "win_rate": st.get("win_rate"), "avg_gross_exposure": res.gross.mean()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    a = ap.parse_args()
    base = Config()
    cases = [replace(base, system=s, risk=r, cost_bps=c)
             for s in (1, 2) for r in (0.001, 0.0025, 0.005, 0.01) for c in (0.0, 5.0)]
    with ProcessPoolExecutor(initializer=load, initargs=(a.data_dir,)) as pool:
        rows = list(pool.map(one, cases))
    table = pd.DataFrame(rows)
    Path("results").mkdir(exist_ok=True)
    table.to_csv("results/portfolio.csv", index=False)
    show = table.copy()
    show["risk_per_n"] = show["risk_per_n"].map(lambda v: f"{v:.2%}")
    show["cagr"] = show["cagr"].map(lambda v: f"{v:+.1%}")
    for col in ("max_dd", "win_rate"):
        show[col] = show[col].map(lambda v: f"{v:.1%}")
    print(show.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
