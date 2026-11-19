"""Per market: where do the Gann levels' hold rate and fade trade rank among random levels?

With 25 markets, a few will rank high or low by luck alone. This shows how many do, against that expectation.
Usage: python per_market.py <folder> [--draws 200]
Writes results/per_market.csv (45 degrees, K = 10, 5 bps).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bt", type=Path)
    ap.add_argument("--draws", type=int, default=200)
    a = ap.parse_args()
    prices = pd.read_parquet(a.bt / "data/prices.parquet")
    (a.bt / "results").mkdir(exist_ok=True)
    rows = []
    for i, sym in enumerate(dict.fromkeys(prices.columns.get_level_values(1))):
        df = engine.market_frame(prices, sym)
        g = engine.run_market(df, 0.25, 10, 0.0005)
        rh, rt = [], []
        for d in range(a.draws):
            r = engine.run_market(df, 0.25, 10, 0.0005, (d + 1) * 1000 + i)  # the same seeds as run_tests.py
            rh.append(r.holds / r.touches)
            rt.append(r.trades.ret.mean())
        gh = g.holds / g.touches
        rows.append({"symbol": sym, "touches": g.touches, "hold_rate": gh, "rand_hold_median": np.median(rh),
                     "hold_pct_rank": np.mean(np.array(rh) < gh), "avg_trade": g.trades.ret.mean(),
                     "rand_avg_trade_median": np.median(rt), "trade_pct_rank": np.mean(np.array(rt) < g.trades.ret.mean())})
    out = pd.DataFrame(rows).sort_values("hold_pct_rank", ascending=False)
    out.to_csv(a.bt / "results/per_market.csv", index=False)
    print(out.round(4).to_string(index=False))
    n = len(out)
    print(f"\nHold rate in the top 5% of random sets: {(out.hold_pct_rank >= 0.95).sum()} of {n} markets "
          f"(luck alone: about {0.05 * n:.1f}); bottom 5%: {(out.hold_pct_rank <= 0.05).sum()}")
    print(f"Gann beat the random median hold rate in {(out.hold_pct_rank > 0.5).sum()} of {n} markets")


if __name__ == "__main__":
    main()
