"""Three checks on the square-of-nine engine. Writes results/validation.txt.

1. A second implementation, written separately in plain Python (no numba, no shared code), must give the same
   SPY trades (45 degrees, K = 10, 5 bps) as the engine, for the fade and the break: same dates, sides and prices.
2. No look-ahead: cut the data at 80 random dates and run again (fade and break, Gann and random levels, pivots
   with K = 5, 10 and 20). Every trade that ended before the cut must be the same as in the full run, and no
   earlier anchor may change.
3. Accounting: for every market and both modes, equity rebuilt from each trade's entry and exit prices and the
   cost rule equals the engine's equity.
The reference also counts touches and holds, which must match. It shares the written rules with the engine, so it
catches coding slips, not a wrong rule; and cuts at whole bars cannot catch a peek inside one bar.

Usage: python -I scripts/validate.py <backtest_dir>
"""

import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402

STEP, K, COST = 0.25, 10, 0.0005


def reference_spy(df: pd.DataFrame, follow: bool) -> list[tuple]:
    """Plain loop version: find swings, then walk the days one by one, tracking the price path in each bar."""
    hi, lo, op, cl = (list(df[c]) for c in ("High", "Low", "Open", "Close"))
    n = len(cl)
    confirmed = {}  # day it becomes known -> pivot prices in bar order
    for i in range(K, n - K):
        if hi[i] >= max(hi[i - K:i + K + 1]):
            confirmed.setdefault(i + K, []).append(hi[i])
        if lo[i] <= min(lo[i - K:i + K + 1]):
            confirmed.setdefault(i + K, []).append(lo[i])

    def path(t, start=None):
        """The bar's prices in order: open, nearer extreme, other extreme (from `start` if given)."""
        first, second = (hi[t], lo[t]) if hi[t] - op[t] <= op[t] - lo[t] else (lo[t], hi[t])
        return [op[t], first, second] if start is None else [start, first, second]

    def first_exit(points, stop, target, long):
        """Walk a list of prices; return the first price where the stop or target is crossed, at that level."""
        prev = points[0]
        if (long and (prev <= stop or prev >= target)) or (not long and (prev >= stop or prev <= target)):
            return prev
        for p in points[1:]:
            lo_, hi_ = min(prev, p), max(prev, p)
            hits = [x for x in (stop, target) if lo_ <= x <= hi_]
            if hits:
                return min(hits, key=lambda x: abs(x - prev))  # the one reached first on the way
            prev = p
        return None

    pivot, trades, pos = None, [], None
    touches = holds = 0
    for t in range(1, n):
        if (t - 1) in confirmed:
            pivot = confirmed[t - 1][-1]
        if pivot is not None:  # touches count on every day, trade or not
            r0 = math.sqrt(pivot)
            x0 = (math.sqrt(cl[t - 1]) - r0) / STEP
            u0, d0 = (r0 + (math.floor(x0) + 1) * STEP) ** 2, (r0 + (math.ceil(x0) - 1) * STEP) ** 2
            if r0 + (math.ceil(x0) - 2) * STEP > 0:
                if hi[t] >= u0:
                    touches += 1
                    holds += cl[t] < u0
                if lo[t] <= d0:
                    touches += 1
                    holds += cl[t] > d0
        if pos:
            long, entry, stop, target, ei = pos
            ex = first_exit(path(t), stop, target, long)
            if ex is None and t - ei >= engine.HOLD_DAYS:
                ex = cl[t]
            if ex is not None:
                trades.append((ei, t, 1 if long else -1, entry, ex))
                pos = None
            continue
        if pivot is None:
            continue
        root = math.sqrt(pivot)
        x = (math.sqrt(cl[t - 1]) - root) / STEP
        up, dn = math.floor(x) + 1, math.ceil(x) - 1
        lvl = lambda j: (root + j * STEP) ** 2
        if root + (dn - 1) * STEP <= 0:
            continue
        touch_up, touch_dn = hi[t] >= lvl(up), lo[t] <= lvl(dn)
        if not (touch_up or touch_dn):
            continue
        if touch_up and touch_dn:  # a gap past a level reached it first; else the nearer extreme first
            up_first = True if op[t] >= lvl(up) else False if op[t] <= lvl(dn) else hi[t] - op[t] <= op[t] - lo[t]
        else:
            up_first = touch_up
        j = up if up_first else dn
        if (up_first and op[t] >= lvl(j + 1)) or (not up_first and op[t] <= lvl(j - 1)):
            continue
        entry = max(op[t], lvl(j)) if up_first else min(op[t], lvl(j))
        long = (up_first == follow)
        stop, target = (lvl(j - 1), lvl(j + 1)) if long else (lvl(j + 1), lvl(j - 1))
        # rest of the entry bar: from the level on to the extreme on that side, then to the other extreme
        rest = [entry, hi[t], lo[t]] if up_first else [entry, lo[t], hi[t]]
        ex = first_exit(rest, stop, target, long)
        if ex is not None:
            trades.append((t, t, 1 if long else -1, entry, ex))
        else:
            pos = (long, entry, stop, target, t)
    return trades, touches, holds


def main() -> None:
    bt = Path(sys.argv[1])
    prices = pd.read_parquet(bt / "data/prices.parquet")
    syms = list(dict.fromkeys(prices.columns.get_level_values(1)))
    lines = []

    # 1. independent implementation, both modes
    spy = engine.market_frame(prices, "SPY")
    for follow, anchor in itertools.product((False, True), (K,)):
        ref, rt, rh = reference_spy(spy, follow)
        run = engine.run_market(spy, STEP, anchor, COST, follow=follow)
        eng = run.trades
        eng_t = [(int(r.entry_i), int(r.exit_i), int(r.side), r.entry, r.exit) for r in eng.itertuples()]
        same = len(ref) == len(eng_t) and all(
            a[:3] == b[:3] and abs(a[3] - b[3]) < 1e-9 and abs(a[4] - b[4]) < 1e-9 for a, b in zip(ref, eng_t))
        lines.append(f"1. Independent SPY implementation ({'break' if follow else 'fade'}, anchor {anchor}): "
                     f"{len(ref)} trades vs engine {len(eng_t)}; identical: {same}; touches {rt} vs {run.touches}, "
                     f"holds {rh} vs {run.holds}")

    # 2. look-ahead: truncate and rerun
    rng = np.random.default_rng(7)
    bad_trades = bad_pivots = checked = 0
    for i in range(80):  # fade or break, Gann or random levels, three pivot sizes
        sym = syms[rng.integers(len(syms))]
        df = engine.market_frame(prices, sym)
        cut = int(rng.integers(300, len(df) - 50))
        follow, seed = bool(i % 2), (None if i % 4 < 2 else 1000 + i)
        anchor = (5, 10, 20)[i // 4 % 3]
        full = engine.run_market(df, STEP, anchor, COST, seed, follow=follow).trades
        part = engine.run_market(df.iloc[:cut], STEP, anchor, COST, seed, follow=follow).trades
        f = full[full.exit_i < cut - 1].reset_index(drop=True)
        p = part[part.exit_i < cut - 1].reset_index(drop=True)
        cols = ["entry_i", "exit_i", "side", "entry", "exit"]
        if len(f) != len(p) or not np.allclose(f[cols].to_numpy(), p[cols].to_numpy()):
            bad_trades += 1
        pf = engine.anchors(df, anchor)[0][:cut]
        pp = engine.anchors(df.iloc[:cut], anchor)[0]
        if not np.allclose(np.nan_to_num(pf), np.nan_to_num(pp)):
            bad_pivots += 1
        checked += 1
    lines.append(f"2. Look-ahead: {checked} random cuts (fade and break, Gann and random, three pivot sizes); trades that changed when the future was removed: {bad_trades}; "
                 f"cuts where a past pivot changed: {bad_pivots}")

    # 3. accounting: rebuild equity from the trades' own prices and the cost rule, apart from the engine's ret column
    worst = 0.0
    for sym in syms:
        for follow, anchor in itertools.product((False, True), (K,)):
            r = engine.run_market(engine.market_frame(prices, sym), STEP, anchor, COST, follow=follow)
            if r.trades.empty:
                continue
            t = r.trades
            gross = t.side * (t.exit / t.entry - 1)
            rebuilt = max(0.0, float(np.prod((1 - COST) ** 2 * (1 + gross))))  # zero equity closes the account
            last = int(t.exit_i.iloc[-1])  # a trade still open at the end: compare at the last exit
            e = r.equity.iloc[last]
            worst = max(worst, abs(rebuilt - e) if e == 0 else abs(rebuilt / e - 1))
    lines.append(f"3. Accounting: equity rebuilt from trade prices and costs vs the engine's equity, {len(syms)} markets, "
                 f"both modes; largest relative gap {worst:.2e}")
    text = "\n".join(lines)
    (bt / "results").mkdir(exist_ok=True)
    (bt / "results/validation.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
