"""SPY alone: the levels to expect in TradingView, and the test on one symbol against random levels.

Usage: python spy_check.py <data_dir> [--anchor-date 2022-10-13] [--draws 200]
Prints the square-of-nine levels from the SPY low in the month of --anchor-date (compare with the Pine
script's "Manual price" anchor), then the SPY fade and break tests at 45 degrees, K = 10, before and after costs,
against random levels with the same spacing.
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
    ap.add_argument("data_dir", type=Path)
    ap.add_argument("--anchor-date", default="2022-10-13")
    ap.add_argument("--draws", type=int, default=200)
    a = ap.parse_args()
    prices = pd.read_parquet(a.data_dir / "prices.parquet")
    spy = engine.market_frame(prices, "SPY")

    month = spy.loc[a.anchor_date[:7]]
    day = month.Low.idxmin()
    low = month.Low.loc[day]
    print(f"Anchor: SPY low of {low:.2f} on {day.date()} (Yahoo, split adjusted, not dividend adjusted)")
    print("degrees  level")
    for j in range(-4, 13):
        print(f"{45 * j:7d}  {(np.sqrt(low) + 0.25 * j) ** 2:8.2f}")

    print("\nSPY, 45 degrees, swing length 10, from", spy.index[0].date(), "to", spy.index[-1].date())
    for follow in (False, True):
        for cost in (0.0, 0.0005):
            g = engine.run_market(spy, 0.25, 10, cost, follow=follow)
            rand = [engine.run_market(spy, 0.25, 10, cost, s + 1, follow=follow).trades.ret.mean() for s in range(a.draws)]
            rand_hold = [(lambda r: r.holds / r.touches)(engine.run_market(spy, 0.25, 10, cost, s + 1)) for s in range(a.draws)]
            st = engine.stats(g.equity)
            name = "break" if follow else "fade "
            print(f"{name} {cost * 1e4:.0f} bps: {len(g.trades)} trades, win {(g.trades.ret > 0).mean():.1%}, "
                  f"avg trade {g.trades.ret.mean():+.3%} (random median {np.median(rand):+.3%}, "
                  f"Gann beats {np.mean(np.array(rand) < g.trades.ret.mean()):.0%} of random sets), "
                  f"CAGR {st['cagr']:+.2%}, worst drop {st['max_dd']:.1%}")
    print(f"hold rate: Gann {g.holds / g.touches:.1%} of {g.touches} touches, random median {np.median(rand_hold):.1%}, "
          f"Gann beats {np.mean(np.array(rand_hold) < g.holds / g.touches):.0%} of random sets")


if __name__ == "__main__":
    main()
