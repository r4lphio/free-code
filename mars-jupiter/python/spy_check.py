"""The single-symbol cross-check: SPY's test trades, to compare with the TradingView indicator's table.

Prints every SPY trade of the planned rule (hold 10 bars, 5 basis points each way) and the totals the
indicator shows: closed trades, average trade after cost, and winning trades.
Usage: python spy_check.py [SYMBOL] [--until YYYY-MM-DD]   (needs data/prices.parquet from fetch_data.py)
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("symbol", nargs="?", default="SPY")
ap.add_argument("--until", default=None, help="drop bars on or after this date, to match a chart's last bar")
a = ap.parse_args()
data = Path(__file__).resolve().parent / "data"
df = pd.read_parquet(data / "prices.parquet").xs(a.symbol, axis=1, level=1).dropna()
if a.until:
    df = df[df.index < a.until]
cal = E.load_calendar(data)
m = E.make_market(a.symbol, "", df)
tr = E.aspect_trades(m, cal, 10)
r = E.trade_returns(m, tr, 0.0005)
for (i0, i1, d, j), x in zip(tr, r):
    print(f"{df.index[i0]:%Y-%m-%d}  {cal.aspect[j]:<11} {'long ' if d > 0 else 'short'}  "
          f"in {m.open[i0]:9.2f}  out {df.index[i1]:%Y-%m-%d} {m.open[i1]:9.2f}  {x:+.2%}")
print(f"\n{a.symbol}: {len(r)} closed trades, average {np.mean(r):+.2%} after cost, winning {np.mean(r > 0):.1%}, "
      f"bars {df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}")
