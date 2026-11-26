"""Test 1: Basso's sizing study. Same entries and exits, four sizing layers added one at a time.

Usage: python sizing_study.py <data_dir> <results_dir>
"""

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script dir
from engine import Config, Sizing, run, stats

CASES = {
    "1. Risk only": Sizing(use_init_vol=False, use_ongoing=False, use_caps=False),
    "2. + initial volatility": Sizing(use_ongoing=False, use_caps=False),
    "3. + ongoing trims": Sizing(use_caps=False),
    "4. + portfolio caps": Sizing(),
}


def benchmarks(prices: pd.DataFrame, start: pd.Timestamp) -> dict[str, pd.Series]:
    close = prices["Close"].loc[start:]
    spy = close["SPY"] / close["SPY"].iloc[0]
    # Equal weight in every ETF, rebalanced monthly.
    rets = close.pct_change().fillna(0.0)
    month = rets.index.to_period("M")
    weights = pd.DataFrame(1 / close.shape[1], index=rets.index, columns=close.columns)
    growth = []
    w = weights.iloc[0].to_numpy()
    for i, (d, r) in enumerate(rets.iterrows()):
        if i > 0 and month[i] != month[i - 1]:
            w = np.full(len(w), w.sum() / len(w))
        w = w * (1 + r.to_numpy())
        growth.append(w.sum())
    return {"SPY buy and hold": spy, "Equal-weight ETFs, buy and hold": pd.Series(growth, rets.index)}


def main(data_dir: Path, out_dir: Path) -> None:
    prices = pd.read_parquet(data_dir / "prices.parquet")
    tbill = pd.read_parquet(data_dir / "tbill.parquet")["irx"]
    rows, curves = [], {}
    for name, sizing in CASES.items():
        res = run(prices, replace(Config(), sizing=sizing), tbill)
        s = stats(res.equity, res.trades) | {"avg_gross": res.gross.mean(), "max_gross": res.gross.max()}
        rows.append({"case": name, **s})
        curves[name] = res.equity / Config().start_equity
        if name.startswith("4"):
            res.trades.to_csv(out_dir / "trades_case4.csv", index=False)
    start = next(iter(curves.values())).index[0]
    for name, curve in benchmarks(prices, start).items():
        rows.append({"case": name, **stats(curve)})
        curves[name] = curve
    table = pd.DataFrame(rows).set_index("case")
    table.to_csv(out_dir / "sizing_study.csv")
    pd.DataFrame(curves).to_parquet(out_dir / "sizing_curves.parquet")
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(table)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
