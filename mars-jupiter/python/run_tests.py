"""Run every Mars-Jupiter test on the real aspect calendar and on 1,000 shifted copies (see ../TEST-PLAN.md).

Usage: python -I scripts/run_tests.py <backtest_dir> [--shifts 1000] [--workers 8]
Writes to <backtest_dir>/results/:
  summary.csv        one row per metric and group: real value, shifted mean, 5th and 95th percentile, share beaten
  draws.csv.gz       every metric for every shift (shift 0 is the real calendar)
  trades.csv         every real trade (hold 10, all markets), before and after costs
  per_market.csv     the aspect trade per market, with its own share of shifts beaten
  portfolio.csv      the real equal-weight portfolios (daily return), before and after costs, per group
  shifts.txt         the shift offsets in days
"""

from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E  # noqa: E402

COST = 0.0005  # 5 basis points each way
GROUPS = ("all", "equity", "bond", "commodity", "crypto")
SEED = 20261119
STATE: dict = {}


def group_mean(values: dict[str, float], markets: list[E.Market]) -> dict[str, float]:
    """Average of per-market values (each market counts once), for all markets and for each asset class."""
    out = {}
    for g in GROUPS:
        v = [values[m.symbol] for m in markets if (g == "all" or m.asset_class == g) and np.isfinite(values[m.symbol])]
        out[g] = float(np.mean(v)) if v else np.nan
    return out


def metrics(k: int, keep: bool = False) -> dict:
    """Every metric for the calendar shifted by k days (k = 0 is the real one)."""
    cal0, markets, recent, sep = STATE["cal"], STATE["markets"], STATE["recent"], STATE["sep"]
    cal = cal0.shifted(k) if k else cal0
    row: dict = {"shift": k}
    extra: dict = {}

    # Primary: the aspect trade, hold 10, average trade per market, and the portfolio.
    for cost, tag in ((COST, "net"), (0.0, "gross")):
        per, slots = {}, []
        for m in markets:
            tr = E.aspect_trades(m, cal, 10)
            r = E.trade_returns(m, tr, cost)
            per[m.symbol] = float(r.mean()) if len(r) else np.nan
            slots.append(E.slot_returns(m, tr, cost))
            if keep and tag == "net":
                extra.setdefault("trades", []).append((m, tr, r, E.trade_returns(m, tr, 0.0)))
        for g, v in group_mean(per, markets).items():
            row[f"trade10_{tag}|{g}"] = v
        for g in GROUPS:
            sel = [i for i, m in enumerate(markets) if g == "all" or m.asset_class == g]
            p = E.portfolio([markets[i] for i in sel], [slots[i] for i in sel])
            row[f"cagr10_{tag}|{g}"] = E.cagr(p)
            if keep:
                extra.setdefault("portfolio", {})[f"{tag}|{g}"] = p
        if tag == "net":
            for m in markets:
                row[f"market_trade10_net|{m.symbol}"] = per[m.symbol]

    # Robustness: hold 5 and 20, and data from March 2007 only (after costs).
    for hold in (5, 20):
        per = {}
        for m in markets:
            r = E.trade_returns(m, E.aspect_trades(m, cal, hold), COST)
            per[m.symbol] = float(r.mean()) if len(r) else np.nan
        for g, v in group_mean(per, markets).items():
            row[f"trade{hold}_net|{g}"] = v
    per = {}
    for m in recent:
        tr = E.aspect_trades(m, cal, 10)
        per[m.symbol] = float(E.trade_returns(m, tr, COST).mean()) if tr else np.nan
    for g, v in group_mean(per, recent).items():
        row[f"trade10_net_since2007|{g}"] = v

    # Direction by aspect: long forward returns, every event.
    for h in (5, 10, 20):
        fw = {m.symbol: E.forward_returns(m, cal, h) for m in markets}
        for a in E.ASPECT_NAMES:
            per = {s: float(f[a].mean()) if len(f[a]) else np.nan for s, f in fw.items()}
            for g, v in group_mean(per, markets).items():
                row[f"fwd{h}_{a}|{g}"] = v

    # Volatility in orb (3 degrees), all aspects and each aspect.
    for name, orb_days in STATE["orbs"].items():
        per = {m.symbol: E.orb_volatility(m, orb_days, k) for m in markets}
        for g, v in group_mean(per, markets).items():
            row[f"vol_{name}|{g}"] = v

    # Turning points within 3 bars.
    per = {m.symbol: E.turn_rate(m, cal, 3) for m in markets}
    for g, v in group_mean(per, markets).items():
        row[f"turns|{g}"] = v
    return (row, extra) if keep else row


def init(bt: Path) -> None:
    data = bt / "data"
    STATE["cal"] = E.load_calendar(data)
    STATE["markets"] = E.load_markets(data)
    STATE["recent"] = E.load_markets(data, since="2007-03-01")
    STATE["sep"] = sep = E.load_separation(data)
    STATE["orbs"] = {"all": E.in_orb(sep, 3.0)} | {a: E.in_orb(sep, 3.0, (a,)) for a in E.ASPECT_NAMES}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bt", type=Path)
    ap.add_argument("--shifts", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    out = a.bt / "results"
    out.mkdir(exist_ok=True)
    init(a.bt)
    rng = np.random.default_rng(SEED)
    ks = rng.integers(30, E.SPAN_DAYS - 30, size=a.shifts)
    (out / "shifts.txt").write_text("\n".join(map(str, ks)) + "\n")

    real, extra = metrics(0, keep=True)
    with Pool(a.workers, initializer=init, initargs=(a.bt,)) as pool:
        rows = pool.map(metrics, [int(k) for k in ks], chunksize=8)
    draws = pd.DataFrame([real] + rows)
    draws.to_csv(out / "draws.csv.gz", index=False)

    sh = draws.iloc[1:]
    summary = []
    for col in draws.columns:
        if col == "shift" or col.startswith("market_"):
            continue
        metric, group = col.split("|")
        x = sh[col].dropna()
        summary.append({"metric": metric, "group": group, "real": real[col], "shift_mean": x.mean(),
                        "shift_p05": x.quantile(0.05), "shift_p95": x.quantile(0.95),
                        "beat_share": float((x < real[col]).mean()), "n_shifts": len(x)})
    pd.DataFrame(summary).to_csv(out / "summary.csv", index=False)

    rows = []
    for m, tr, net, gross in extra["trades"]:
        for (i0, i1, d, j), rn, rg in zip(tr, net, gross):
            rows.append({"symbol": m.symbol, "asset_class": m.asset_class, "aspect": STATE["cal"].aspect[j],
                         "aspect_date": str((E.SPAN_START + pd.Timedelta(days=int(STATE["cal"].day[j]))).date()),
                         "entry_date": str((E.SPAN_START + pd.Timedelta(days=int(m.bar_day[i0]))).date()),
                         "exit_date": str((E.SPAN_START + pd.Timedelta(days=int(m.bar_day[i1]))).date()),
                         "direction": "long" if d > 0 else "short", "entry_open": m.open[i0],
                         "exit_open": m.open[i1], "return_gross": rg, "return_net": rn})
    pd.DataFrame(rows).to_csv(out / "trades.csv", index=False)

    per = []
    for m in STATE["markets"]:
        col = f"market_trade10_net|{m.symbol}"
        x = sh[col].dropna()
        n = sum(1 for r in rows if r["symbol"] == m.symbol)
        per.append({"symbol": m.symbol, "asset_class": m.asset_class, "trades": n, "first_bar":
                    str((E.SPAN_START + pd.Timedelta(days=int(m.bar_day[0]))).date()),
                    "avg_trade_net": real[col], "shift_mean": x.mean(), "beat_share": float((x < real[col]).mean())})
    pd.DataFrame(per).to_csv(out / "per_market.csv", index=False)
    pd.DataFrame(extra["portfolio"]).to_csv(out / "portfolio.csv")
    print(pd.DataFrame(summary).to_string())


if __name__ == "__main__":
    main()
