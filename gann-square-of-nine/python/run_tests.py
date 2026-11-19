"""Run every square-of-nine test and write the CSVs in results/. Hold rate, win rate and average trade are
averages over markets (each market counts the same); CAGR and worst drop are for the equal-weight portfolio.

Usage: python run_tests.py <folder> [--draws 200]
"""

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402

STEPS = {"45": 0.25, "90": 0.5, "180": 1.0}  # degrees -> added to the square root
HEADLINE = ("45", 10)  # step and pivot window K
COST = 0.0005  # 5 bps a side


def run_all(prices, syms, step, k, cost, seed=None, skip_pivot=False, follow=False):
    runs = {s: engine.run_market(engine.market_frame(prices, s), step, k, cost,
                                 None if seed is None else seed * 1000 + i, skip_pivot, follow)
            for i, s in enumerate(syms)}
    port = engine.portfolio({s: r.equity for s, r in runs.items()})
    trades = pd.concat([r.trades.assign(symbol=s) for s, r in runs.items()], ignore_index=True)
    st = engine.stats(port)
    # Every market counts the same: Bitcoin's levels are so close together that it has about half of all
    # touches, so pooled numbers would mostly measure Bitcoin.
    rs = runs.values()
    return {
        "touches": sum(r.touches for r in rs),
        "hold_rate": np.mean([r.holds / r.touches for r in rs]),
        "trades": len(trades),
        "win_rate": np.mean([(r.trades.ret > 0).mean() for r in rs]),
        "avg_trade": np.mean([r.trades.ret.mean() for r in rs]),
        **st,
    }, runs, port, trades


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bt", type=Path)
    ap.add_argument("--draws", type=int, default=200)
    a = ap.parse_args()
    prices = pd.read_parquet(a.bt / "data/prices.parquet")
    syms = list(dict.fromkeys(prices.columns.get_level_values(1)))
    out = a.bt / "results"
    out.mkdir(exist_ok=True)

    rows = []
    for mode, deg, k, cost in itertools.product(("fade", "follow"), STEPS, (5, 10, 20), (0.0, COST)):
        step, fl = STEPS[deg], mode == "follow"
        g, runs, port, trades = run_all(prices, syms, step, k, cost, follow=fl)
        rand = [run_all(prices, syms, step, k, cost, seed=d + 1, follow=fl)[0] for d in range(a.draws)]
        rd = pd.DataFrame(rand)
        row = {"mode": mode, "degrees": deg, "k": k, "cost_bps": cost * 1e4, "levels": "gann", **g}
        for m in ("hold_rate", "avg_trade", "cagr", "win_rate"):
            row[f"rand_{m}_median"] = rd[m].median()
            row[f"rand_{m}_p05"] = rd[m].quantile(0.05)
            row[f"rand_{m}_p95"] = rd[m].quantile(0.95)
            row[f"pct_rand_below_{m}"] = (rd[m] < g[m]).mean()  # share of random draws Gann beats
        rows.append(row)
        rd.assign(mode=mode, degrees=deg, k=k, cost_bps=cost * 1e4).to_csv(
            out / f"random_{mode}_{deg}deg_k{k}_{int(cost * 1e4)}bps.csv", index=False)
        if (deg, k) == HEADLINE:
            tag = f"{mode}_" + ("costs" if cost else "free")
            trades.to_csv(out / f"trades_headline_{tag}.csv", index=False)
            port.rename("equity").to_frame().to_parquet(out / f"portfolio_headline_{tag}.parquet")
            per = []
            for s, r in runs.items():
                t = r.trades
                per.append({"symbol": s, "touches": r.touches, "hold_rate": r.holds / max(r.touches, 1),
                            "trades": len(t), "win_rate": (t.ret > 0).mean(), "avg_trade": t.ret.mean(),
                            **engine.stats(r.equity)})
            pd.DataFrame(per).to_csv(out / f"markets_headline_{tag}.csv", index=False)
        print(f"{mode} {deg}deg k{k} {cost*1e4:.0f}bps: hold {g['hold_rate']:.3f} (rand med {row['rand_hold_rate_median']:.3f}, "
              f"beats {row['pct_rand_below_hold_rate']:.0%}) avg {g['avg_trade']*100:.3f}% "
              f"(rand {row['rand_avg_trade_median']*100:.3f}%) cagr {g['cagr']*100:.2f}% "
              f"(rand {row['rand_cagr_median']*100:.2f}%) dd {g['max_dd']:.0%} trades {g['trades']}", flush=True)
    for cost in (0.0, COST):  # variant: without the pivot price itself as a level
        g = run_all(prices, syms, STEPS[HEADLINE[0]], HEADLINE[1], cost, skip_pivot=True)[0]
        rows.append({"mode": "fade", "degrees": HEADLINE[0], "k": HEADLINE[1], "cost_bps": cost * 1e4,
                     "levels": "gann_no_pivot", **g})
    pd.DataFrame(rows).to_csv(out / "summary.csv", index=False)

    # Benchmarks: buy and hold, price only (these prices are not dividend adjusted).
    bench = []
    for s in ("SPY", "BTC-USD"):
        c = engine.market_frame(prices, s).Close
        c = c.loc[engine.PORTFOLIO_START:]
        bench.append({"symbol": s, **engine.stats(c / c.iloc[0])})
    ew = engine.portfolio({s: engine.market_frame(prices, s).Close for s in syms})
    bench.append({"symbol": "equal-weight all markets", **engine.stats(ew)})
    pd.DataFrame(bench).to_csv(out / "benchmarks.csv", index=False)
    print(pd.DataFrame(bench))


if __name__ == "__main__":
    main()
