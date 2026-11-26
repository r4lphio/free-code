"""Square-of-nine price levels as support and resistance: a daily backtest with a random-level baseline.

The textbook formula (see ../RESEARCH.md): from a pivot price P, the level that is `deg` degrees around the
square of nine is (sqrt(P) + deg / 180) ** 2. One full turn (360 degrees) adds 2 to the square root, 180 adds 1,
90 adds 0.5 and 45 adds 0.25. So the levels are evenly spaced in square-root space, anchored on the pivot.

Pivots     A swing high (low) is a bar whose high (low) is the highest (lowest) of the K bars on each side.
           It is known only K bars later. On day t the active pivot is the latest one confirmed by day t - 1.
Levels     Gann: sqrt(P) + j * step for every whole j. j = 0 is the pivot itself (the 0 / 360 degree point);
           a variant (skip_pivot) drops it, and drops the nearest level from the random lattice too.
           Random baseline: the same lattice with the same step, moved by a random phase in [0, step) that
           is drawn once per pivot. So it has the same spacing and density, only the anchor differs.
Touch      Resistance: yesterday's close is below a level and today's high reaches it. Support: the mirror.
           A touch "holds" when today's close stays on yesterday's side of the level. Touches count on every
           day, with or without an open trade.
Trade      Fade the touch: sell at resistance, buy at support (follow=True trades the break instead: the mirror
           rule, with the stop and target swapped). A limit order at the level; a gap through it fills at the open,
           and a gap past the next level skips the trade. The stop is the next level beyond, the target the next
           level back. After HOLD_DAYS days, exit at the close. One trade per market at a time, 1x notional,
           flat (no interest) between trades.
Bar order  Daily bars don't say whether the high or the low came first. When it matters, a gap past a level
           reached it first; otherwise the path is open -> the nearer extreme -> the other extreme. Only the open decides, so neither the fade nor the
           break is favoured, and no decision uses the rest of the day.
Costs      `cost` per side, as a fraction of traded value.
Ruin       A short can lose more than 100% (the levels are very far apart on prices under about $1). When equity
           reaches zero the market's account is closed: no more trades, equity stays at zero.
All decisions on day t use only data up to day t (levels use data up to day t - 1).
"""

from dataclasses import dataclass

import numba
import numpy as np
import pandas as pd

HOLD_DAYS = 20


def pivot_events(high: np.ndarray, low: np.ndarray, k: int) -> list[tuple[int, float]]:
    """(bar where it became known, price) for each K-bar swing high and low. A swing at bar i is known at i + k."""
    events: list[tuple[int, float]] = []
    for i in range(k, len(high) - k):
        if high[i] == high[i - k : i + k + 1].max():
            events.append((i + k, high[i]))
        if low[i] == low[i - k : i + k + 1].min():
            events.append((i + k, low[i]))
    return sorted(events, key=lambda e: e[0])


def active_anchor(events: list[tuple[int, float]], n: int) -> tuple[np.ndarray, np.ndarray]:
    """The active anchor price for each day (NaN before the first) and its number (-1 before the first):
    the latest event known by the day before."""
    out = np.full(n, np.nan)
    pid = np.full(n, -1)
    cur, cid, e = np.nan, -1, 0
    for t in range(n):
        while e < len(events) and events[e][0] <= t - 1:  # known by yesterday
            cur, cid = events[e][1], e
            e += 1
        out[t], pid[t] = cur, cid
    return out, pid


def pivots(high: np.ndarray, low: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """The active K-bar pivot for each day (see active_anchor)."""
    return active_anchor(pivot_events(high, low, k), len(high))


def anchors(df: pd.DataFrame, k: int) -> tuple[np.ndarray, np.ndarray]:
    """The active anchor for each day: the latest K-bar pivot (K = 5, 10, 20...)."""
    return pivots(df.High.to_numpy(float), df.Low.to_numpy(float), k)


@numba.njit(cache=True)
def _exit_in_bar(side, stop, target, o, h, l):
    """Where an open trade exits inside one bar, or -1.0 if it does not.
    A gap through the stop or target exits at the open. Otherwise the bar's path is taken as
    open -> the nearer extreme -> the other extreme (so neither side is favoured)."""
    if side == 1:
        if o <= stop or o >= target:
            return o
    else:
        if o >= stop or o <= target:
            return o
    high_first = (h - o) <= (o - l)
    up = target if side == 1 else stop  # the level above
    dn = stop if side == 1 else target  # the level below
    if high_first:
        if h >= up:
            return up
        if l <= dn:
            return dn
    else:
        if l <= dn:
            return dn
        if h >= up:
            return up
    return -1.0


@numba.njit(cache=True)
def _next(j, d, sk):
    """The lattice index d steps (+1 or -1) from j, jumping over the skipped index sk (NaN: none)."""
    j2 = j + d
    if j2 == sk:
        j2 += d
    return j2


@numba.njit(cache=True)
def _simulate(o, h, l, c, anchor, skip, step, follow, cost, hold_days):
    """Core loop. anchor[t] is the lattice origin in sqrt space (sqrt(P) for Gann, sqrt(P) + phase for random);
    level j is (anchor + j * step) ** 2. skip[t] is a lattice index left out (NaN: none).
    Touches and holds are counted on every day, whether or not a trade is open, so they depend on the levels only.
    Returns per-day equity (1.0 start), touches, holds, and trade rows (entry_i, exit_i, side, entry, exit, ret).
    ret is the trade's net return after both sides' costs, so the product of (1 + ret) is the final equity."""
    n = len(c)
    eq = np.ones(n)
    touches = 0
    holds = 0
    rows = np.zeros((n, 6))
    nt = 0
    pos = 0  # +1 long, -1 short
    entry = stop = target = 0.0
    entry_i = 0
    equity = 1.0  # cash equity when flat
    ruined = False  # a short can lose more than 100%; at zero equity the account is closed for good
    base = 1.0  # equity after the entry cost, for the open trade
    for t in range(1, n):
        # The levels next to yesterday's close, from the anchor known yesterday.
        a = anchor[t]
        valid = not np.isnan(a)
        hit_up = hit_dn = False
        j_up = j_dn = 0.0
        lu = ld = 0.0
        sk = skip[t]
        if valid:
            u = np.sqrt(c[t - 1])
            j_up = np.floor((u - a) / step) + 1
            j_dn = np.ceil((u - a) / step) - 1
            if j_up == sk:
                j_up += 1
            if j_dn == sk:
                j_dn -= 1
            if a + _next(j_dn, -1, sk) * step <= 0:  # the lattice reaches zero below: no level to use
                valid = False
        if valid:
            lu = (a + j_up * step) ** 2
            ld = (a + j_dn * step) ** 2
            hit_up = h[t] >= lu
            hit_dn = l[t] <= ld
            if hit_up:
                touches += 1
                if c[t] < lu:
                    holds += 1
            if hit_dn:
                touches += 1
                if c[t] > ld:
                    holds += 1

        if ruined:  # touches still count (they belong to the levels), but there is no more trading
            eq[t] = 0.0
            continue
        if pos != 0:
            ex = _exit_in_bar(pos, stop, target, o[t], h[t], l[t])
            if ex < 0 and t - entry_i >= hold_days:
                ex = c[t]
            if ex > 0:
                gross = pos * (ex / entry - 1.0)
                equity = base * (1.0 + gross) * (1.0 - cost)
                rows[nt, 0] = entry_i
                rows[nt, 1] = t
                rows[nt, 2] = pos
                rows[nt, 3] = entry
                rows[nt, 4] = ex
                rows[nt, 5] = (1.0 - cost) ** 2 * (1.0 + gross) - 1.0
                nt += 1
                pos = 0
                if equity <= 0.0:
                    equity, ruined = 0.0, True
                eq[t] = equity
                continue  # no new entry on an exit day
            eq[t] = base * (1.0 + pos * (c[t] / entry - 1.0))
            if eq[t] <= 0.0:  # wiped out while open: closed at this close, no more trading
                rows[nt, 0] = entry_i
                rows[nt, 1] = t
                rows[nt, 2] = pos
                rows[nt, 3] = entry
                rows[nt, 4] = c[t]
                rows[nt, 5] = (1.0 - cost) ** 2 * (1.0 + pos * (c[t] / entry - 1.0)) - 1.0
                nt += 1
                pos, equity, ruined = 0, 0.0, True
                eq[t] = 0.0
            continue
        eq[t] = equity
        if not (hit_up or hit_dn):
            continue
        # Which level did price reach first? Only the open decides, never the rest of the day:
        # a gap past one level reached it first; otherwise the path is open -> nearer extreme first.
        if hit_up and hit_dn:
            if o[t] >= lu:
                up_first = True
            elif o[t] <= ld:
                up_first = False
            else:
                up_first = (h[t] - o[t]) <= (o[t] - l[t])
        else:
            up_first = hit_up
        if up_first:
            hi_lvl = (a + _next(j_up, 1, sk) * step) ** 2
            lo_lvl = (a + _next(j_up, -1, sk) * step) ** 2
            if o[t] >= hi_lvl:  # gapped past the next level: skip
                continue
            fill = max(o[t], lu)
            side = 1 if follow else -1  # follow buys the break; fade sells the touch
        else:
            hi_lvl = (a + _next(j_dn, 1, sk) * step) ** 2
            lo_lvl = (a + _next(j_dn, -1, sk) * step) ** 2
            if o[t] <= lo_lvl:
                continue
            fill = min(o[t], ld)
            side = -1 if follow else 1
        if side == 1:
            s_, g_ = lo_lvl, hi_lvl
        else:
            s_, g_ = hi_lvl, lo_lvl
        base = equity * (1.0 - cost)
        # The rest of the entry bar. Up first: price went on to the high, then to the low (and the mirror).
        ex = -1.0
        if up_first:
            if h[t] >= hi_lvl:
                ex = hi_lvl
            elif l[t] <= lo_lvl:
                ex = lo_lvl
        else:
            if l[t] <= lo_lvl:
                ex = lo_lvl
            elif h[t] >= hi_lvl:
                ex = hi_lvl
        if ex > 0:
            gross = side * (ex / fill - 1.0)
            equity = base * (1.0 + gross) * (1.0 - cost)
            rows[nt, 0] = t
            rows[nt, 1] = t
            rows[nt, 2] = side
            rows[nt, 3] = fill
            rows[nt, 4] = ex
            rows[nt, 5] = (1.0 - cost) ** 2 * (1.0 + gross) - 1.0
            nt += 1
            if equity <= 0.0:
                equity, ruined = 0.0, True
            eq[t] = equity
            continue
        pos, entry, stop, target, entry_i = side, fill, s_, g_, t
        eq[t] = max(0.0, base * (1.0 + side * (c[t] / fill - 1.0)))
    return eq, touches, holds, rows[:nt]


@dataclass
class Run:
    equity: pd.Series
    touches: int
    holds: int
    trades: pd.DataFrame


_PIVOTS: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def run_market(df: pd.DataFrame, step: float, k: int, cost: float, phase_seed: int | None = None,
               skip_pivot: bool = False, follow: bool = False) -> Run:
    """Run one market. k is the anchor rule (see anchors()). phase_seed=None gives Gann levels; an int gives a random-phase lattice.
    skip_pivot=True leaves out the level nearest the pivot: the pivot itself for Gann, and the nearest
    random level for a random lattice, so both keep the same density.
    follow=True trades the break instead of the bounce (the mirror rule, same stops and targets swapped)."""
    o, h, l, c = (df[f].to_numpy(float) for f in ("Open", "High", "Low", "Close"))
    key = (len(df), hash(h.tobytes()), hash(l.tobytes()), k)
    if key not in _PIVOTS:
        _PIVOTS[key] = anchors(df, k)
    piv, pid = _PIVOTS[key]
    root = np.sqrt(piv)
    phase = np.zeros(len(df))
    if phase_seed is not None:
        rng = np.random.default_rng(phase_seed)
        phase = rng.uniform(0, step, size=pid.max() + 2)[pid + 1]
    anchor = root + phase
    # the lattice index nearest the pivot: (root - anchor) / step = -phase / step, rounded
    skip = np.round(-phase / step) if skip_pivot else np.full(len(df), np.nan)
    eq, touches, holds, rows = _simulate(o, h, l, c, anchor, skip, step, follow, cost, HOLD_DAYS)
    trades = pd.DataFrame(rows, columns=["entry_i", "exit_i", "side", "entry", "exit", "ret"])
    trades["entry_date"] = df.index[trades.entry_i.astype(int)]
    trades["exit_date"] = df.index[trades.exit_i.astype(int)]
    return Run(pd.Series(eq, index=df.index), touches, holds, trades)


def market_frame(prices: pd.DataFrame, sym: str) -> pd.DataFrame:
    return prices.xs(sym, axis=1, level=1).dropna()


PORTFOLIO_START = "2007-03-01"  # when all 24 ETFs have data; Bitcoin joins in 2014


def portfolio(equities: dict[str, pd.Series]) -> pd.Series:
    """Equal-weight daily rebalanced portfolio of the markets' equity curves, from PORTFOLIO_START.
    Each market joins when its data starts. The calendar is the days when at least two markets trade, so
    Bitcoin's weekend and holiday moves fold into its next trading day instead of making those days all Bitcoin."""
    eqs = pd.DataFrame(equities).loc[PORTFOLIO_START:]
    days = eqs.index[eqs.notna().sum(axis=1) >= min(2, eqs.shape[1])]
    rets = eqs.ffill().loc[days].pct_change()
    return (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()


def stats(eq: pd.Series) -> dict[str, float]:
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / years) - 1
    dd = (eq / eq.cummax() - 1).min()
    return {"cagr": cagr, "max_dd": -dd, "end": eq.iloc[-1]}
