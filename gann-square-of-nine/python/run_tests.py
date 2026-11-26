"""Run every square-of-nine test on the 50-instrument universe and write the CSVs in results/.

Settings: fade and break (follow) x 45/90/180 degrees x K-bar pivot anchors (K = 5, 10, 20) x 0 and 5 bps a side.
(The video also tested anchors from r4lph's own Gann swing indicator. That indicator is not part of this code.) Each setting runs the Gann levels and `--draws` random-phase
lattices (same spacing). A seventh mode, follow_nopivot, is the break with the anchor level left out (before costs).

Every result is given for each group: all markets, each asset class, and all ETFs (everything but crypto).
Hold rate, win rate and average trade are averages over the group's markets (each market counts the same);
CAGR and worst drop are for the group's equal-weight portfolio.

Usage: python -I scripts/run_tests.py <backtest_dir> [--draws 200] [--workers 20]
Writes results/summary.csv (one row per setting and group), results/markets.csv (one row per setting and
market), results/random_draws.csv.gz, results/benchmarks.csv, and the headline trades and portfolios.
"""

import argparse
import itertools
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402

STEPS = {"45": 0.25, "90": 0.5, "180": 1.0}  # degrees -> added to the square root
ANCHORS = [5, 10, 20]
HEADLINES = [("45", 10)]  # chosen before any run
COST = 0.0005  # 5 bps a side
GROUPS = ["all", "etfs", "equity", "bond", "commodity", "crypto"]

_DATA: dict = {}


def _init(bt: str) -> None:
    prices = pd.read_parquet(Path(bt) / "data/prices.parquet")
    uni = pd.read_csv(Path(bt) / "data/universe.csv")
    _DATA["syms"] = list(uni.symbol)
    _DATA["cls"] = dict(zip(uni.symbol, uni.asset_class))
    _DATA["frames"] = {s: engine.market_frame(prices, s) for s in _DATA["syms"]}


def members(group: str) -> list[str]:
    cls = _DATA["cls"]
    if group == "all":
        return _DATA["syms"]
    if group == "etfs":
        return [s for s in _DATA["syms"] if cls[s] != "crypto"]
    return [s for s in _DATA["syms"] if cls[s] == group]


def one_set(step, k, cost, follow, skip_pivot, draw):
    """All markets with Gann levels (draw None) or random draw d. Returns per-market runs."""
    return {s: engine.run_market(_DATA["frames"][s], step, k, cost, None if draw is None else (draw + 1) * 1000 + i,
                                 skip_pivot, follow) for i, s in enumerate(_DATA["syms"])}


def group_stats(runs, group):
    ms = [runs[s] for s in members(group)]
    port = engine.portfolio({s: runs[s].equity for s in members(group)})
    return {"touches": sum(r.touches for r in ms), "trades": sum(len(r.trades) for r in ms),
            "hold_rate": np.nanmean([r.holds / r.touches if r.touches else np.nan for r in ms]),
            "win_rate": np.nanmean([(r.trades.ret > 0).mean() if len(r.trades) else np.nan for r in ms]),
            "avg_trade": np.nanmean([r.trades.ret.mean() if len(r.trades) else np.nan for r in ms]),
            **engine.stats(port)}, port


def market_stats(r):
    t = r.trades
    return {"touches": r.touches, "hold_rate": r.holds / max(r.touches, 1), "trades": len(t),
            "avg_trade": t.ret.mean() if len(t) else np.nan, **engine.stats(r.equity)}


def run_setting(args):
    mode, deg, k, cost, draws = args
    step, follow, skip = STEPS[deg], mode != "fade", mode == "follow_nopivot"
    gann = one_set(step, k, cost, follow, skip, None)
    tag = dict(mode=mode, degrees=deg, anchor=str(k), cost_bps=cost * 1e4)
    g = {grp: group_stats(gann, grp) for grp in GROUPS}
    rand_rows, rand_mkt = [], []
    for d in range(draws):
        rr = one_set(step, k, cost, follow, skip, d)
        for grp in GROUPS:
            rand_rows.append({**tag, "draw": d, "group": grp, **group_stats(rr, grp)[0]})
        rand_mkt.append({s: market_stats(r) for s, r in rr.items()})
    rd = pd.DataFrame(rand_rows)
    rows = []
    for grp in GROUPS:
        gs, x = g[grp][0], rd[rd.group == grp]
        row = {**tag, "group": grp, "markets": len(members(grp)), **gs}
        for m in ("hold_rate", "avg_trade", "cagr", "win_rate"):
            row[f"rand_{m}_median"] = x[m].median()
            row[f"rand_{m}_p05"] = x[m].quantile(0.05)
            row[f"rand_{m}_p95"] = x[m].quantile(0.95)
            row[f"pct_rand_below_{m}"] = (x[m] < gs[m]).mean()  # share of random draws Gann beats
        rows.append(row)
    mrows = []
    for s, r in gann.items():
        ms = market_stats(r)
        rh = np.array([dm[s]["hold_rate"] for dm in rand_mkt])
        rt = np.array([dm[s]["avg_trade"] for dm in rand_mkt])
        mrows.append({**tag, "symbol": s, "asset_class": _DATA["cls"][s], **ms,
                      "rand_hold_median": np.median(rh), "hold_pct_rank": np.mean(rh < ms["hold_rate"]),
                      "rand_avg_trade_median": np.nanmedian(rt), "trade_pct_rank": np.mean(rt < ms["avg_trade"])})
    extra = None
    if (deg, k) in HEADLINES and mode != "follow_nopivot":
        trades = pd.concat([r.trades.assign(symbol=s) for s, r in gann.items()], ignore_index=True)
        ports = pd.DataFrame({grp: g[grp][1] for grp in GROUPS})
        extra = (trades, ports)
    return rows, mrows, rd, tag, extra


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bt", type=Path)
    ap.add_argument("--draws", type=int, default=200)
    ap.add_argument("--workers", type=int, default=20)
    a = ap.parse_args()
    out = a.bt / "results"
    out.mkdir(exist_ok=True)
    jobs = [(m, d, k, c, a.draws) for m, d, k, c in itertools.product(("fade", "follow"), STEPS, ANCHORS, (0.0, COST))]
    jobs += [("follow_nopivot", d, k, 0.0, a.draws) for d, k in itertools.product(STEPS, ANCHORS)]
    rows, mrows, rds = [], [], []
    with ProcessPoolExecutor(a.workers, initializer=_init, initargs=(str(a.bt),)) as ex:
        for r, m, rd, tag, extra in ex.map(run_setting, jobs):
            rows += r
            mrows += m
            rds.append(rd)
            al = next(x for x in r if x["group"] == "all")
            print(f"{tag['mode']} {tag['degrees']}deg {tag['anchor']} {tag['cost_bps']:.0f}bps: hold {al['hold_rate']:.3f} "
                  f"(rand {al['rand_hold_rate_median']:.3f}, beats {al['pct_rand_below_hold_rate']:.0%}) "
                  f"avg {al['avg_trade'] * 100:.3f}% (rand {al['rand_avg_trade_median'] * 100:.3f}%)", flush=True)
            if extra:
                name = f"{tag['mode']}_{tag['degrees']}deg_{tag['anchor']}_{int(tag['cost_bps'])}bps"
                extra[0].to_csv(out / f"trades_{name}.csv", index=False)
                extra[1].to_parquet(out / f"portfolios_{name}.parquet")
    pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)
    pd.DataFrame(mrows).to_csv(out / "markets.csv", index=False)
    pd.concat(rds).to_csv(out / "random_draws.csv.gz", index=False)

    # Benchmarks: buy and hold, price only (these prices are not dividend adjusted).
    _init(str(a.bt))
    bench = []
    c = _DATA["frames"]["SPY"].Close.loc[engine.PORTFOLIO_START:]
    bench.append({"group": "SPY", **engine.stats(c / c.iloc[0])})
    for grp in GROUPS:
        bench.append({"group": grp, **engine.stats(engine.portfolio({s: _DATA["frames"][s].Close for s in members(grp)}))})
    pd.DataFrame(bench).to_csv(out / "benchmarks.csv", index=False)
    print(pd.DataFrame(bench))


if __name__ == "__main__":
    main()
