"""Independent checks of the Mars-Jupiter test. Every check must pass before a number from it is used.

1. Aspect dates: a second ephemeris (Swiss Ephemeris, Moshier mode, which uses no JPL file) and a second
   search method (daily samples, then Brent's method) find the same crossings as aspects.py.
2. Published dates: the Mars-Jupiter conjunctions listed by public astronomy sources.
3. SPY trades: a plain second implementation (row by row in pandas, no numpy indexing) matches the engine.
4. No look-ahead: every trade enters on the first bar on or after its aspect date, never before; cutting the data
   at 40 random dates changes no earlier trade and no earlier volatility score.
5. The baseline: every shifted event maps back to a real event with the same aspect and side, and shifting
   back reproduces the real calendar and the real SPY results.
6. Accounting: compounding a trade's daily slot returns gives back its trade return, before and after costs.
7. Secondary tests: plain pandas versions of the 10-day return by aspect, the turning-point rate and the
   volatility in orb match the engine on SPY.

A second agent reviewed the code cold on 19 November 2026 and found that the first versions of checks 4 and 5
could not fail; they were made stricter (check 4 entry dates, check 5 mapping), and check 7 was added.

Usage: python -I scripts/validate.py <backtest_dir>   (writes results/validation.txt)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import swisseph as swe
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E  # noqa: E402

PUBLISHED_CONJUNCTIONS = ["2018-01-07", "2020-03-20", "2022-05-29", "2024-08-14"]
LINES: list[str] = []


def report(name: str, ok: bool, detail: str) -> None:
    LINES.append(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    print(LINES[-1])


def swe_sep(jd_ut: float) -> float:
    flags = swe.FLG_MOSEPH  # geocentric, apparent, true equinox of date: the same frame as aspects.py
    m = swe.calc_ut(jd_ut, swe.MARS, flags)[0][0]
    j = swe.calc_ut(jd_ut, swe.JUPITER, flags)[0][0]
    return (m - j) % 360.0


def swe_crossings(start: str, end: str) -> pd.DataFrame:
    j0 = swe.julday(*map(int, start.split("-")), 0.0)
    j1 = swe.julday(*map(int, end.split("-")), 0.0)
    jd = np.arange(j0, j1, 1.0)
    sep = np.array([swe_sep(x) for x in jd])
    rows = []
    for ang in (0, 60, 90, 120, 180, 240, 270, 300):
        f = lambda x: (swe_sep(x) - ang + 180) % 360 - 180  # noqa: E731
        d = (sep - ang + 180) % 360 - 180
        for i in np.where((np.sign(d[:-1]) != np.sign(d[1:])) & (np.abs(d[:-1] - d[1:]) < 90))[0]:
            x = brentq(f, jd[i], jd[i + 1], xtol=1e-7)
            y, mo, dd, h = swe.revjul(x)
            t = pd.Timestamp(year=y, month=mo, day=dd, tz="UTC") + pd.Timedelta(hours=h)
            rows.append({"utc": t, "angle": ang})
    return pd.DataFrame(rows).sort_values("utc").reset_index(drop=True)


def check_ephemeris(data: Path) -> None:
    ours = pd.read_csv(data / "aspects.csv", parse_dates=["utc"])
    ours = ours[(ours.utc >= "1990-01-02") & (ours.utc < "2035-12-31")].reset_index(drop=True)
    theirs = swe_crossings("1990-01-01", "2036-01-01")
    theirs = theirs[(theirs.utc >= "1990-01-02") & (theirs.utc < "2035-12-31")].reset_index(drop=True)
    same_count = len(ours) == len(theirs)
    gaps = []
    for _, r in ours.iterrows():
        cand = theirs[theirs.angle == r.angle]
        gaps.append(float(np.min(np.abs((cand.utc - r.utc).dt.total_seconds()))) / 3600 if len(cand) else 1e9)
    gaps = np.array(gaps)
    same_day = (ours.utc.dt.date.values == theirs.utc.dt.date.values).mean() if same_count else 0.0
    report("ephemeris", same_count and gaps.max() < 1.0,
           f"Skyfield/JPL DE440s {len(ours)} crossings, Swiss Ephemeris/Moshier {len(theirs)}; largest time gap "
           f"{gaps.max() * 60:.1f} minutes, median {np.median(gaps) * 60:.2f}; same UTC date {same_day:.1%}")


def check_published(data: Path) -> None:
    ours = pd.read_csv(data / "aspects.csv")
    conj = set(ours[ours.aspect == "conjunction"].date)
    missing = [d for d in PUBLISHED_CONJUNCTIONS if d not in conj]
    report("published conjunctions", not missing,
           f"{len(PUBLISHED_CONJUNCTIONS) - len(missing)} of {len(PUBLISHED_CONJUNCTIONS)} published dates match"
           + (f"; missing {missing}" if missing else ""))


def plain_spy_trades(df: pd.DataFrame, events: pd.DataFrame, hold: int, cost: float) -> list[tuple]:
    """The aspect trade written out row by row, with dates as strings, independent of engine.py."""
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    opens = list(df.Open)
    out, busy_until = [], -1
    for _, ev in events.iterrows():
        if ev.date < dates[0]:
            continue
        i = next((k for k, d in enumerate(dates) if d >= ev.date), None)
        if i is None or i + hold >= len(dates) or i < busy_until:
            continue
        long = ev.aspect in ("conjunction", "sextile", "trine")
        ratio = opens[i + hold] / opens[i]
        ret = (ratio - 1 if long else 1 - ratio)
        out.append((dates[i], dates[i + hold], "long" if long else "short", max(ret, -1.0) - 2 * cost))
        busy_until = i + hold
    return out


def check_trades(data: Path) -> None:
    panel = pd.read_parquet(data / "prices.parquet")
    events = pd.read_csv(data / "aspects.csv")
    cal = E.load_calendar(data)
    for sym in ("SPY", "BTC", "TLT"):
        df = panel.xs(sym, axis=1, level=1).dropna()
        m = E.make_market(sym, "", df)
        tr = E.aspect_trades(m, cal, 10)
        r = E.trade_returns(m, tr, 0.0005)
        mine = [(df.index[a].strftime("%Y-%m-%d"), df.index[b].strftime("%Y-%m-%d"), "long" if d > 0 else "short", x)
                for (a, b, d, _), x in zip(tr, r)]
        plain = plain_spy_trades(df, events, 10, 0.0005)
        same = len(mine) == len(plain) and all(a[:3] == b[:3] and abs(a[3] - b[3]) < 1e-12 for a, b in zip(mine, plain))
        report(f"second implementation, {sym}", same, f"engine {len(mine)} trades, plain loop {len(plain)} trades, "
               f"{'identical dates, sides and returns' if same else 'DIFFERENT'}")


def check_lookahead(data: Path) -> None:
    panel = pd.read_parquet(data / "prices.parquet")
    events = pd.read_csv(data / "aspects.csv")
    cal = E.load_calendar(data)
    rng = np.random.default_rng(7)
    bad = early = tested = n_trades = 0
    for sym in ("SPY", "GLD", "BTC", "AGG"):
        df = panel.xs(sym, axis=1, level=1).dropna()
        dates = df.index.strftime("%Y-%m-%d")
        full = E.make_market(sym, "", df)
        ft = E.aspect_trades(full, cal, 10)
        fr = E.trade_returns(full, ft, 0.0005)
        for i0, _, _, j in ft:  # the entry bar is the first bar on or after the aspect's date
            ev_date = str((E.SPAN_START + pd.Timedelta(days=int(cal.day[j]))).date())
            early += not (dates[i0] >= ev_date and (i0 == 0 or dates[i0 - 1] < ev_date))
            n_trades += 1
        for cut in rng.integers(300, len(df) - 20, size=10):
            part = E.make_market(sym, "", df.iloc[:cut])
            pt = E.aspect_trades(part, cal, 10)
            pr = E.trade_returns(part, pt, 0.0005)
            before = [(t[:3], x) for t, x in zip(ft, fr) if t[1] < cut]
            got = [(t[:3], x) for t, x in zip(pt, pr)]
            z_same = np.allclose(full.zabs[:cut], part.zabs, equal_nan=True)
            bad += (before != got) or not z_same
            tested += 1
    report("no look-ahead", bad == 0 and early == 0,
           f"{n_trades} trades on SPY, GLD, BTC and AGG enter on the first bar on or after the aspect date "
           f"({early} early); {tested} data cut-offs changed {bad} earlier trades or volatility scores")


def check_shift(data: Path) -> None:
    cal = E.load_calendar(data)
    real = {(int(d), a, int(x)) for d, a, x in zip(cal.day, cal.aspect, cal.direction)}
    lost = 0
    ks = [1, 30, 812, 4000, 9999, 16770]
    for k in ks:
        s = cal.shifted(k)
        back = {(int((d - k) % E.SPAN_DAYS), a, int(x)) for d, a, x in zip(s.day, s.aspect, s.direction)}
        lost += len(real ^ back)
    panel = pd.read_parquet(data / "prices.parquet")
    m = E.make_market("SPY", "", panel.xs("SPY", axis=1, level=1).dropna())
    same = True
    for k in ks:
        c = cal.shifted(k).shifted(E.SPAN_DAYS - k)
        same &= E.aspect_trades(m, c, 10) == E.aspect_trades(m, cal, 10)
        same &= all(np.array_equal(E.forward_returns(m, c, 10)[a], E.forward_returns(m, cal, 10)[a])
                    for a in E.ASPECT_NAMES)
    report("baseline shift", lost == 0 and same,
           f"{len(ks)} shifts: every event maps back to a real one with the same aspect and side ({lost} mismatches); "
           f"shifting back gives the real SPY trades and returns")


def check_accounting(data: Path) -> None:
    panel = pd.read_parquet(data / "prices.parquet")
    cal = E.load_calendar(data)
    worst = {0.0: 0.0, 0.0005: 0.0}
    n = 0
    for sym in ("SPY", "SOL", "UNG"):
        m = E.make_market(sym, "", panel.xs(sym, axis=1, level=1).dropna())
        tr = E.aspect_trades(m, cal, 10)
        for cost in worst:
            ret = E.trade_returns(m, tr, cost)
            slots = E.slot_returns(m, tr, cost)
            for (i0, i1, _, _), g in zip(tr, ret):
                if g > -1:
                    worst[cost] = max(worst[cost], abs(np.prod(1 + slots[i0:i1]) - 1 - g))
                    n += cost == 0
    report("accounting", max(worst.values()) < 1e-9,
           f"{n} trades on SPY, SOL and UNG; largest gap between compounded daily returns and the trade return "
           f"{worst[0.0]:.1e} before costs, {worst[0.0005]:.1e} after")


def check_secondary(data: Path) -> None:
    """Plain pandas versions of the secondary measures on SPY, written without engine.py's helpers."""
    panel = pd.read_parquet(data / "prices.parquet")
    df = panel.xs("SPY", axis=1, level=1).dropna()
    events = pd.read_csv(data / "aspects.csv")
    events = events[events.date >= df.index[0].strftime("%Y-%m-%d")]
    cal = E.load_calendar(data)
    m = E.make_market("SPY", "", df)
    dates = list(df.index.strftime("%Y-%m-%d"))
    import bisect
    fwd: dict[str, list] = {a: [] for a in E.ASPECT_NAMES}
    turns = []
    hi = df.High.rolling(21, center=True).max()
    lo = df.Low.rolling(21, center=True).min()
    pivot = ((df.High == hi) | (df.Low == lo)).tolist()
    for _, ev in events.iterrows():
        i = bisect.bisect_left(dates, ev.date)
        if i + 10 < len(dates):
            fwd[ev.aspect].append(df.Open.iloc[i + 10] / df.Open.iloc[i] - 1)
        if 3 <= i and i + 3 < len(dates):
            turns.append(any(pivot[i - 3:i + 4]))
    eng = E.forward_returns(m, cal, 10)
    ok_fwd = all(np.allclose(np.mean(fwd[a]), eng[a].mean()) for a in E.ASPECT_NAMES)
    ok_turn = np.isclose(np.mean(turns), E.turn_rate(m, cal, 3))
    sep = pd.read_csv(data / "aspects-daily.csv").set_index("date").separation
    dist = pd.concat([((sep - a + 180) % 360 - 180).abs() for a in (0, 60, 90, 120, 180, 240, 270, 300)], axis=1).min(axis=1)
    flag = dist.reindex(dates).to_numpy() <= 3.0
    r = np.log(df.Close).diff()
    z = (r.abs() / r.rolling(60).std().shift(1)).to_numpy()
    ok = np.isfinite(z)
    plain_vol = z[ok & flag].mean() - z[ok & ~flag].mean()
    ok_vol = np.isclose(plain_vol, E.orb_volatility(m, E.in_orb(E.load_separation(data), 3.0)))
    report("secondary tests, SPY", ok_fwd and ok_turn and ok_vol,
           f"10-day return by aspect {'matches' if ok_fwd else 'DIFFERS'}, turning-point rate "
           f"{'matches' if ok_turn else 'DIFFERS'} ({np.mean(turns):.3f}), volatility in orb "
           f"{'matches' if ok_vol else 'DIFFERS'} ({plain_vol:+.4f})")


def main() -> None:
    bt = Path(sys.argv[1])
    data = bt / "data"
    check_ephemeris(data)
    check_published(data)
    check_trades(data)
    check_lookahead(data)
    check_shift(data)
    check_accounting(data)
    check_secondary(data)
    (bt / "results").mkdir(exist_ok=True)
    (bt / "results" / "validation.txt").write_text("\n".join(LINES) + "\n")
    if any(line.startswith("FAIL") for line in LINES):
        sys.exit(1)


if __name__ == "__main__":
    main()
