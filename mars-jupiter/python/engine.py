"""The Mars-Jupiter test engine: the aspect trade, the event study, volatility in orb, and turning points.

Every test takes an event calendar (aspect dates with their names) so the same code runs on the real calendar
and on shifted copies of it (the baseline). See ../TEST-PLAN.md for the rules this code follows.

Days are counted from SPAN_START (1 January 1990, UTC). A shifted calendar moves every event by the same
number of days and wraps around the span (1990 to 2036), which keeps the count, the spacing and the order.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SPAN_START = pd.Timestamp("1990-01-01")
SPAN_END = pd.Timestamp("2036-01-01")
SPAN_DAYS = (SPAN_END - SPAN_START).days
EASY = ("conjunction", "sextile", "trine")  # long
HARD = ("square", "opposition")  # short
ASPECT_NAMES = ("conjunction", "sextile", "square", "trine", "opposition")
ANGLES = {"conjunction": (0,), "sextile": (60, 300), "square": (90, 270), "trine": (120, 240), "opposition": (180,)}


def day_number(dates) -> np.ndarray:
    """Whole days since SPAN_START for dates (strings or timestamps, read as calendar dates)."""
    d = pd.to_datetime(pd.Index(dates)).tz_localize(None).normalize()
    return ((d - SPAN_START) // pd.Timedelta(days=1)).to_numpy(dtype=np.int64)


@dataclass
class Market:
    """One market's daily bars as arrays. bar_day is the day number of each bar's date."""
    symbol: str
    asset_class: str
    bar_day: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    pivot: np.ndarray  # True where the bar is a 10-day pivot high or low (uses future bars, by design)
    zabs: np.ndarray  # |close-to-close log return| / std of the previous 60 returns (NaN where unknown)


def make_market(symbol: str, asset_class: str, df: pd.DataFrame, pivot_n: int = 10) -> Market:
    df = df.dropna()
    o, h, l, c = (df[f].to_numpy(float) for f in ("Open", "High", "Low", "Close"))
    n = len(df)
    hi_win = pd.Series(h).rolling(2 * pivot_n + 1, center=True).max().to_numpy()
    lo_win = pd.Series(l).rolling(2 * pivot_n + 1, center=True).min().to_numpy()
    pivot = (h == hi_win) | (l == lo_win)  # NaN windows at both ends compare False
    r = np.diff(np.log(c), prepend=np.nan)
    sd = pd.Series(r).rolling(60).std().shift(1).to_numpy()
    zabs = np.abs(r) / sd
    assert len(pivot) == n
    return Market(symbol, asset_class, day_number(df.index), o, h, l, c, pivot, zabs)


def load_markets(data_dir: Path, since: str | None = None, until: str | None = None) -> list[Market]:
    """All 50 markets from prices.parquet, in universe order. since/until: keep bars in [since, until)."""
    uni = pd.read_csv(data_dir / "universe-50.csv")
    panel = pd.read_parquet(data_dir / "prices.parquet")
    out = []
    for sym, cls in zip(uni.symbol, uni.asset_class):
        df = panel.xs(sym, axis=1, level=1).dropna()
        if since:
            df = df[df.index >= since]
        if until:
            df = df[df.index < until]
        if len(df) > 80:
            out.append(make_market(sym, cls, df))
    return out


@dataclass
class Calendar:
    """Aspect events: day numbers (sorted), names, and trade direction (+1 easy, -1 hard)."""
    day: np.ndarray
    aspect: np.ndarray
    direction: np.ndarray

    def shifted(self, k: int) -> "Calendar":
        d = (self.day + k) % SPAN_DAYS
        order = np.argsort(d, kind="stable")
        return Calendar(d[order], self.aspect[order], self.direction[order])


def load_calendar(data_dir: Path) -> Calendar:
    ev = pd.read_csv(data_dir / "aspects.csv")
    day = day_number(ev.date)
    direction = np.where(ev.aspect.isin(EASY), 1, -1)
    return Calendar(day, ev.aspect.to_numpy(), direction)


def load_separation(data_dir: Path) -> np.ndarray:
    """Mars minus Jupiter longitude at 00:00 UTC for each day of the span (index = day number)."""
    sep = pd.read_csv(data_dir / "aspects-daily.csv")
    assert len(sep) == SPAN_DAYS and day_number(sep.date[:1])[0] == 0
    return sep.separation.to_numpy(float)


def event_bars(m: Market, cal: Calendar) -> np.ndarray:
    """For each event, the index of the market's first bar on or after the event day (len(bars) = none)."""
    return np.searchsorted(m.bar_day, cal.day, side="left")


# --- The aspect trade ---------------------------------------------------------------------------------------

def aspect_trades(m: Market, cal: Calendar, hold: int = 10) -> list[tuple[int, int, int, int]]:
    """(entry bar, exit bar, direction, event index) for each trade: enter at the open of the event bar, exit at
    the open `hold` bars later. One position at a time; an event during an open trade is skipped. Events
    whose exit bar is past the data are not traded. Events before the market's first bar are skipped too."""
    pos = event_bars(m, cal)
    n = len(m.open)
    trades = []
    free = 0
    for j, i0 in enumerate(pos):
        if i0 >= n or i0 + hold >= n or i0 < free:
            continue
        if cal.day[j] < m.bar_day[0]:  # the event came before this market existed
            continue
        trades.append((int(i0), int(i0 + hold), int(cal.direction[j]), j))
        free = i0 + hold
    return trades


def trade_returns(m: Market, trades, cost: float) -> np.ndarray:
    """Return of each trade on its entry price, after `cost` (a fraction) on entry and on exit.
    Long: exit / entry - 1. Short: 1 - exit / entry, floored at -100% (the position's money is gone)."""
    if not trades:
        return np.zeros(0)
    t = np.array(trades)
    ratio = m.open[t[:, 1]] / m.open[t[:, 0]]
    gross = np.where(t[:, 2] > 0, ratio - 1, 1 - ratio)
    return np.maximum(gross, -1.0) - 2 * cost


def slot_returns(m: Market, trades, cost: float) -> np.ndarray:
    """Daily return of one market's slot (flat days earn zero). Day i earns the move from open i to open i+1.
    Inside a trade the slot's value is 1 + direction * (open / entry open - 1), less the entry cost from the
    first day and the exit cost on the last day, floored at zero. So the daily returns compound to exactly the
    trade's return after costs (trade_returns)."""
    r = np.zeros(len(m.open))
    for i0, i1, d, _ in trades:
        v = 1 + d * (m.open[i0:i1 + 1] / m.open[i0] - 1) - cost
        v[0] = 1.0
        v[-1] -= cost
        v = np.maximum(v, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            r[i0:i1] = np.where(v[:-1] > 0, v[1:] / v[:-1] - 1, 0.0)
    return r


def portfolio(markets: list[Market], slots: list[np.ndarray]) -> pd.Series:
    """Equal-weight portfolio, rebalanced daily, over every calendar day on which any market trades.
    Each day's return is the average over markets that are live (between their first and last bar); a live
    market with no bar that day (an ETF on a weekend) counts as flat."""
    days = np.unique(np.concatenate([m.bar_day for m in markets]))
    total = np.zeros(len(days))
    live = np.zeros(len(days))
    for m, r in zip(markets, slots):
        idx = np.searchsorted(days, m.bar_day)
        total[idx] += r
        lo, hi = np.searchsorted(days, [m.bar_day[0], m.bar_day[-1]])
        live[lo:hi + 1] += 1
    ret = np.divide(total, live, out=np.zeros_like(total), where=live > 0)
    return pd.Series(ret, index=SPAN_START + pd.to_timedelta(days, unit="D"))


def cagr(daily: pd.Series) -> float:
    """Yearly growth of a daily return series, over the calendar time it covers."""
    years = (daily.index[-1] - daily.index[0]).days / 365.25
    growth = float(np.prod(1 + daily.to_numpy()))
    return growth ** (1 / years) - 1 if growth > 0 else -1.0


# --- Secondary tests ----------------------------------------------------------------------------------------

def forward_returns(m: Market, cal: Calendar, horizon: int) -> dict[str, np.ndarray]:
    """Long return from the event bar's open to the open `horizon` bars later, every event, by aspect."""
    pos = event_bars(m, cal)
    ok = (pos + horizon < len(m.open)) & (cal.day >= m.bar_day[0])
    out = {}
    for a in ASPECT_NAMES:
        sel = ok & (cal.aspect == a)
        p = pos[sel]
        out[a] = m.open[p + horizon] / m.open[p] - 1
    return out


def in_orb(sep: np.ndarray, orb: float, aspects=ASPECT_NAMES) -> np.ndarray:
    """True for each span day whose separation is within `orb` degrees of one of the aspects' angles."""
    hit = np.zeros(len(sep), bool)
    for a in aspects:
        for ang in ANGLES[a]:
            hit |= np.abs((sep - ang + 180) % 360 - 180) <= orb
    return hit


def orb_volatility(m: Market, orb_days: np.ndarray, k: int = 0) -> float:
    """Average normalized |return| on in-orb days minus out-of-orb days. k shifts the orb calendar forward."""
    flag = orb_days[(m.bar_day - k) % SPAN_DAYS]
    ok = np.isfinite(m.zabs)
    a, b = m.zabs[ok & flag], m.zabs[ok & ~flag]
    return float(a.mean() - b.mean()) if len(a) and len(b) else np.nan


def turn_rate(m: Market, cal: Calendar, window: int = 3) -> float:
    """Share of events with a 10-day pivot within `window` bars of the event bar."""
    pos = event_bars(m, cal)
    n = len(m.open)
    ok = (cal.day >= m.bar_day[0]) & (pos + window < n) & (pos - window >= 0)
    if not ok.any():
        return np.nan
    cum = np.concatenate([[0], np.cumsum(m.pivot)])
    p = pos[ok]
    return float(((cum[p + window + 1] - cum[p - window]) > 0).mean())
