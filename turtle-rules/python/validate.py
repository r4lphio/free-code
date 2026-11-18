"""Check the engine against a separate, plain implementation, and check its accounting.

1. One market (SPY), System 2 without adds: every entry and exit date and price must match a second
   implementation written without the engine's code (pandas ewm for N, a plain loop for the rules).
2. Every breakout entry, in both systems, fills at or beyond a level made only from earlier days (no look-ahead).
3. Accounting: closed trade P&L + open positions + interest = the change in equity, for both systems at
   the original size and at 0.1% per N.
Usage: python validate.py data   (run_portfolio.py first is not needed)
"""

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import Config, run  # noqa: E402


def plain(df: pd.DataFrame) -> list[tuple]:
    h, l, c, o = df.High, df.Low, df.Close, df.Open
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    tr.iloc[0] = np.nan
    seed = tr.iloc[1:21].mean()
    n = pd.concat([pd.Series([seed], index=[tr.index[20]]), tr.iloc[21:]]).ewm(alpha=1 / 20, adjust=False).mean()
    n = n.reindex(tr.index)
    hi55, lo55 = h.rolling(55).max().shift(), l.rolling(55).min().shift()
    hi20, lo20 = h.rolling(20).max().shift(), l.rolling(20).min().shift()
    out, side, stop, ent = [], 0, None, None
    for t in range(56, len(df)):
        d = df.index[t]
        if side == 1:
            lvl = max(stop, lo20.iloc[t])
            if l.iloc[t] <= lvl:
                out.append((ent[0], ent[1], d, min(o.iloc[t], lvl)))
                side = 0
        elif side == -1:
            lvl = min(stop, hi20.iloc[t])
            if h.iloc[t] >= lvl:
                out.append((ent[0], ent[1], d, max(o.iloc[t], lvl)))
                side = 0
        if side == 0:
            up, dn = h.iloc[t] >= hi55.iloc[t], l.iloc[t] <= lo55.iloc[t]
            if up and not dn:
                px = max(o.iloc[t], hi55.iloc[t])
                side, stop, ent = 1, px - 2 * n.iloc[t - 1], (d, px)
            elif dn and not up:
                px = min(o.iloc[t], lo55.iloc[t])
                side, stop, ent = -1, px + 2 * n.iloc[t - 1], (d, px)
    return out


def main(data_dir: Path) -> None:
    prices = pd.read_parquet(data_dir / "prices.parquet")
    spy = prices.loc[:, (slice(None), ["SPY"])]
    eng = run(spy, Config(system=2, pyramid=False, use_dd_rule=False, cost_bps=0.0)).trades
    ref = plain(prices.xs("SPY", axis=1, level=1))
    a = [(r.entry_date, round(r.entry_px, 6), r.exit_date, round(r.exit_px, 6)) for r in eng.itertuples()]
    b = [(e, round(p, 6), x, round(q, 6)) for e, p, x, q in ref]
    lines = [f"1. SPY System 2, no adds: engine {len(a)} trades, plain loop {len(b)} trades, identical: {a == b}"]
    assert a == b, [x for x in zip(a, b) if x[0] != x[1]][:3]

    # System 1 enters at a 20-day breakout (or the 55-day fail-safe, which lies beyond it); System 2 at a 55-day one.
    for system, days in ((1, 20), (2, 55)):
        full = run(prices, Config(system=system), None).trades
        hi = prices["High"].rolling(days).max().shift()
        lo = prices["Low"].rolling(days).min().shift()
        bad = 0
        for r in full.itertuples():
            lvl = hi.loc[r.entry_date, r.symbol] if r.side == 1 else lo.loc[r.entry_date, r.symbol]
            bad += (r.side == 1 and r.entry_px < lvl - 1e-9) or (r.side == -1 and r.entry_px > lvl + 1e-9)
        lines.append(f"2. System {system} entries filled inside the prior {days}-day range (look-ahead): {bad} of {len(full)}")
        assert bad == 0

    tbill = pd.read_parquet(data_dir / "tbill.parquet")["irx"]
    worst = 0.0
    for system in (1, 2):
        for risk in (0.01, 0.001):
            r = run(prices, Config(system=system, risk=risk), tbill)
            gap = r.equity.iloc[-1] - 10_000_000 - r.trades.pnl.sum() - (r.open_value + r.open_cash) - r.interest
            worst = max(worst, abs(gap))
    lines.append(f"3. Accounting gap, largest over 4 cases: ${worst:.6f} (closed + open + interest = equity change)")
    assert worst < 1.0
    print("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
