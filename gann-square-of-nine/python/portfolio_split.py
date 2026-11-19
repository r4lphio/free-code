"""The headline setting (45 degrees, K = 10) as two portfolios: the 24 ETFs together, and Bitcoin alone.

Bitcoin's levels are only about 0.2% apart at today's prices (the spacing in percent shrinks as the price
grows), so it trades far more often than any ETF and swamps an equal-weight portfolio. This splits it out.
Usage: python portfolio_split.py <folder> [--draws 200]
Writes results/portfolio_split.csv and results/portfolio_etfs_<mode>_<cost>.parquet.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine  # noqa: E402

STEP, K = 0.25, 10


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bt", type=Path)
    ap.add_argument("--draws", type=int, default=200)
    a = ap.parse_args()
    prices = pd.read_parquet(a.bt / "data/prices.parquet")
    (a.bt / "results").mkdir(exist_ok=True)
    syms = list(dict.fromkeys(prices.columns.get_level_values(1)))  # same order as run_tests.py (same seeds)
    frames = {s: engine.market_frame(prices, s) for s in syms}
    rows = []
    for follow in (False, True):
        for cost in (0.0, 0.0005):
            def runs(seed):
                return {s: engine.run_market(frames[s], STEP, K, cost, None if seed is None else seed * 1000 + i,
                                             follow=follow) for i, s in enumerate(syms)}
            g = runs(None)
            etf_port = engine.portfolio({s: r.equity for s, r in g.items() if s != "BTC-USD"})
            mode = "break" if follow else "fade"
            etf_port.rename("equity").to_frame().to_parquet(a.bt / f"results/portfolio_etfs_{mode}_{int(cost * 1e4)}bps.parquet")
            btc = g["BTC-USD"]
            r_etf, r_btc, r_btc_trade = [], [], []
            for d in range(a.draws):
                rr = runs(d + 1)
                r_etf.append(engine.stats(engine.portfolio({s: r.equity for s, r in rr.items() if s != "BTC-USD"}))["cagr"])
                r_btc.append(engine.stats(rr["BTC-USD"].equity)["cagr"])
                r_btc_trade.append(rr["BTC-USD"].trades.ret.mean())
            for name, eqty, rand in (("24 ETFs", etf_port, r_etf), ("Bitcoin", btc.equity, r_btc)):
                st = engine.stats(eqty.loc[engine.PORTFOLIO_START:] / eqty.loc[engine.PORTFOLIO_START:].iloc[0])
                rows.append({"portfolio": name, "mode": mode, "cost_bps": cost * 1e4, **st,
                             "rand_cagr_median": np.median(rand), "rand_cagr_p05": np.quantile(rand, 0.05),
                             "rand_cagr_p95": np.quantile(rand, 0.95), "pct_rand_below_cagr": np.mean(np.array(rand) < st["cagr"]),
                             "trades": sum(len(r.trades) for s, r in g.items() if (s == "BTC-USD") == (name == "Bitcoin"))})
                print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rows[-1].items()}, flush=True)
            print(f"Bitcoin avg trade {btc.trades.ret.mean():+.4%} (random median {np.median(r_btc_trade):+.4%})", flush=True)
    pd.DataFrame(rows).to_csv(a.bt / "results/portfolio_split.csv", index=False)


if __name__ == "__main__":
    main()
