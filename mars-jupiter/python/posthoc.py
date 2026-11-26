"""Post-hoc checks, added after the first run (see TEST-PLAN.md, "Changes after the first run").

1. The planned run found one standout: stock ETFs rose more than usual in the 10 days after a sextile. These
   checks ask whether it holds in each half of the data and without the 2008 crash.
2. The source brief (RESEARCH.md) arrived after the first run and named two claims the plan did not test:
   David Williams (via Bates): a low at the conjunction and the opposition. Matlock (via Bates): an above-average
   rise in the 30 days before a conjunction or opposition. Both run on all 50 markets.
All against the same 1,000 shifted calendars.

Usage: python -I scripts/posthoc.py <backtest_dir>   (writes results/posthoc.csv and results/claims.csv)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E  # noqa: E402


def equity_fwd(markets, cal, aspect: str, horizon: int) -> float:
    """Average over equity markets (each counts once, even when split in two pieces) of the mean return."""
    per: dict[str, list] = {}
    for m in markets:
        if m.asset_class == "equity":
            per.setdefault(m.symbol, []).extend(E.forward_returns(m, cal, horizon)[aspect])
    vals = [np.mean(v) for v in per.values() if v]
    return float(np.mean(vals)) if vals else np.nan


def low_near(m: E.Market, cal: E.Calendar, aspects, window: int = 3) -> float:
    """Share of the given aspects with a 10-day pivot low within `window` bars of the event bar."""
    lo = pd.Series(m.low).rolling(21, center=True).min().to_numpy()
    cum = np.concatenate([[0], np.cumsum(m.low == lo)])
    pos = E.event_bars(m, cal)
    ok = np.isin(cal.aspect, aspects) & (cal.day >= m.bar_day[0]) & (pos - window >= 0) & (pos + window < len(m.open))
    p = pos[ok]
    return float(((cum[p + window + 1] - cum[p - window]) > 0).mean()) if len(p) else np.nan


def run_before(m: E.Market, cal: E.Calendar, aspects, bars: int = 21) -> float:
    """Average return from the open 21 bars (about 30 calendar days) before the event bar to its open."""
    pos = E.event_bars(m, cal)
    ok = np.isin(cal.aspect, aspects) & (cal.day >= m.bar_day[0]) & (pos - bars >= 0) & (pos < len(m.open))
    p = pos[ok]
    return float(np.mean(m.open[p] / m.open[p - bars] - 1)) if len(p) else np.nan


def claims(bt: Path, cal: E.Calendar, ks: list[int]) -> None:
    markets = E.load_markets(bt / "data")
    pair = ("conjunction", "opposition")
    tests = {"williams_low_at_conj_opp": lambda m, c: low_near(m, c, pair),
             "matlock_rise_30d_before_conj_opp": lambda m, c: run_before(m, c, pair)}
    rows = []
    for name, f in tests.items():
        def score(c):
            return float(np.nanmean([f(m, c) for m in markets]))
        real = score(cal)
        draws = np.array([score(cal.shifted(k)) for k in ks])
        rows.append({"claim": name, "real": real, "shift_mean": draws.mean(), "shift_p05": np.quantile(draws, 0.05),
                     "shift_p95": np.quantile(draws, 0.95), "beat_share": float((draws < real).mean())})
        print(rows[-1])
    pd.DataFrame(rows).to_csv(bt / "results" / "claims.csv", index=False)


def main() -> None:
    bt = Path(sys.argv[1])
    data = bt / "data"
    cal = E.load_calendar(data)
    ks = [int(x) for x in (bt / "results" / "shifts.txt").read_text().split()]
    windows = {
        "1993 to 2009": ("1993-01-01", "2010-01-01"),
        "2010 to 2026": ("2010-01-01", "2026-12-31"),
        "without 2008 and 2009": None,
    }
    rows = []
    for aspect in ("sextile", "conjunction"):
        for name, w in windows.items():
            if w:
                markets = E.load_markets(data, since=w[0], until=w[1])
            else:  # drop the bars of 2008 and 2009 by splitting each market and testing both pieces together
                markets = E.load_markets(data, until="2008-01-01") + E.load_markets(data, since="2010-01-01")
            real = equity_fwd(markets, cal, aspect, 10)
            draws = np.array([equity_fwd(markets, cal.shifted(k), aspect, 10) for k in ks])
            draws = draws[np.isfinite(draws)]
            rows.append({"aspect": aspect, "window": name, "equity_fwd10": real, "shift_mean": draws.mean(),
                         "beat_share": float((draws < real).mean())})
            print(rows[-1])
    pd.DataFrame(rows).to_csv(bt / "results" / "posthoc.csv", index=False)
    claims(bt, cal, ks)


if __name__ == "__main__":
    main()
