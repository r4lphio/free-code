"""Buy-and-hold benchmarks and time in the market, for comparison with the aspect trade.

Usage: python -I scripts/benchmarks.py <backtest_dir>   (writes results/benchmarks.csv)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E  # noqa: E402

bt = Path(sys.argv[1])
markets = E.load_markets(bt / "data")
cal = E.load_calendar(bt / "data")
rows = []
for g in ("all", "equity", "bond", "commodity", "crypto"):
    sel = [m for m in markets if g == "all" or m.asset_class == g]
    hold = [np.append(m.open[1:] / m.open[:-1] - 1, 0.0) for m in sel]  # always long, open to open
    p = E.portfolio(sel, hold)
    days_in = sum(sum(t[1] - t[0] for t in E.aspect_trades(m, cal, 10)) for m in sel)
    days_all = sum(len(m.open) for m in sel)
    rows.append({"group": g, "buy_hold_cagr": E.cagr(p), "start": str(p.index[0].date()),
                 "time_in_trade": days_in / days_all})
spy = [m for m in markets if m.symbol == "SPY"][0]
p = E.portfolio([spy], [np.append(spy.open[1:] / spy.open[:-1] - 1, 0.0)])
rows.append({"group": "SPY", "buy_hold_cagr": E.cagr(p), "start": str(p.index[0].date()), "time_in_trade": np.nan})
df = pd.DataFrame(rows)
df.to_csv(bt / "results" / "benchmarks.csv", index=False)
print(df.to_string())
