"""Daily portfolio simulator for the original Turtle Trading rules (Curtis Faith and others, "The Original Turtle
Trading Rules", 2003). Works on one symbol or a portfolio of daily OHLC prices.

Rules as implemented:
  N        20-day Wilder average of true range: N = (19 * N_prev + TR) / 20, seeded with a 20-day mean.
  Unit     1% of account equity / N shares (one N move costs 1% of the account).
  Entry    System 1: 20-day breakout, skipped when the last 20-day breakout (taken or not, either side)
           was a winner. The skip lasts for that whole breakout; only a 55-day breakout (the fail-safe) may
           enter while it lasts. System 2: 55-day breakout, no filter.
  Adds     One more unit each 1/2 N past the last fill, up to 4 units.
  Stop     2 N from the last fill, for every unit (so each add raises the stop by 1/2 N).
  Exit     System 1: 10-day breakout the other way. System 2: 20-day breakout the other way.
  Limits   4 units per market, 6 per closely correlated group, 10 per loosely correlated group, 12 per direction.
  Drawdown Each 10% the account falls below its value at the start of the year, size as if the account
           were 20% smaller again (the notional account), until the next year starts.
All levels use data up to yesterday's close. Orders are stops: a gap through a level fills at the open.
Cash earns (or, when borrowed, pays) the T-bill rate, like a futures account. Costs are per side on traded value.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Closely correlated groups (6-unit limit) and loosely correlated groups (10-unit limit) for the episode's 24 ETFs.
GROUPS = {
    "SPY": "stocks", "QQQ": "stocks", "IWM": "stocks", "XLK": "stocks", "XLV": "stocks", "XLU": "stocks",
    "EFA": "stocks", "EEM": "stocks", "EWJ": "stocks", "VNQ": "reit",
    "TLT": "bonds", "IEF": "bonds", "LQD": "bonds", "TIP": "bonds",
    "GLD": "metals", "SLV": "metals",
    "USO": "energy", "XLE": "energy", "DBC": "energy",
    "DBA": "grains",
    "UUP": "usd", "FXE": "usd", "FXA": "usd", "FXY": "usd",
}
LOOSE = {"stocks": "equity", "reit": "equity", "bonds": "rates", "metals": "commodities", "energy": "commodities",
         "grains": "commodities", "usd": "currencies"}


@dataclass(frozen=True)
class Config:
    system: int = 1  # 1: 20-day entry, 10-day exit, filter. 2: 55-day entry, 20-day exit.
    risk: float = 0.01  # account fraction per N per unit
    stop_n: float = 2.0
    add_n: float = 0.5
    max_units: int = 4
    group_units: int = 6
    loose_units: int = 10
    side_units: int = 12
    use_dd_rule: bool = True
    use_filter: bool = True  # System 1 only
    # The episode's first engine skipped only the day of a skipped breakout. True reproduces that version.
    loose_filter: bool = False
    pyramid: bool = True
    cost_bps: float = 5.0
    start_equity: float = 10_000_000.0
    sizing: str = "n"  # "n": Turtle units. "flat": same dollar size in every market (for the sizing test)


@dataclass
class Result:
    equity: pd.Series
    gross: pd.Series  # gross exposure / equity
    trades: pd.DataFrame
    interest: float  # total interest booked
    costs: float  # total trading costs paid
    open_value: float  # market value of positions still open at the end
    open_cash: float  # cash already booked against those positions (their entries, adds, costs)
    open_units: int  # Turtle units still open at the end


def wilder_n(prices: pd.DataFrame) -> pd.DataFrame:
    h, l, c = prices["High"], prices["Low"], prices["Close"]
    prev = c.shift(1)
    tr = np.maximum(h - l, np.maximum((h - prev).abs(), (l - prev).abs()))
    out = pd.DataFrame(np.nan, index=tr.index, columns=tr.columns)
    for col in tr.columns:
        s = tr[col].to_numpy(float)
        n = np.full(len(s), np.nan)
        first = np.flatnonzero(np.isfinite(s))
        if len(first) < 21:
            continue
        i0 = first[0] + 19
        n[i0] = np.nanmean(s[first[0]:i0 + 1])
        for i in range(i0 + 1, len(s)):
            n[i] = (19 * n[i - 1] + s[i]) / 20 if np.isfinite(s[i]) else n[i - 1]
        out[col] = n
    return out


def channels(prices: pd.DataFrame, days: int) -> tuple[np.ndarray, np.ndarray]:
    """Highest high and lowest low of the `days` days before each day (today excluded)."""
    return (prices["High"].rolling(days).max().shift(1).to_numpy(float),
            prices["Low"].rolling(days).min().shift(1).to_numpy(float))


def run(prices: pd.DataFrame, cfg: Config, tbill: pd.Series | None = None) -> Result:
    o, h, l, c = (prices[f].to_numpy(float) for f in ("Open", "High", "Low", "Close"))
    syms = list(prices["Close"].columns)
    n_days, n_sym = c.shape
    N = wilder_n(prices).to_numpy(float)
    entry_days, exit_days = (20, 10) if cfg.system == 1 else (55, 20)
    hi_in, lo_in = channels(prices, entry_days)
    hi_out, lo_out = channels(prices, exit_days)
    hi55, lo55 = channels(prices, 55)
    group = [GROUPS.get(s, s) for s in syms]  # a symbol not listed is its own group
    loose = [LOOSE.get(g, g) for g in group]
    cost = cfg.cost_bps / 1e4
    rf = np.zeros(n_days) if tbill is None else tbill.reindex(prices.index).ffill().fillna(0.0).to_numpy(float) / 100 / 252

    units = np.zeros(n_sym, int)  # unit count, signed by side
    qty = np.zeros(n_sym)  # shares, signed
    stop = np.full(n_sym, np.nan)
    last_fill = np.full(n_sym, np.nan)
    n_entry = np.full(n_sym, np.nan)  # N at the first unit
    pos: dict[int, dict] = {}
    trades: list[dict] = []
    # Hypothetical System 1 trade per market, for the "last breakout was a winner" filter.
    hyp_side = np.zeros(n_sym, int)
    hyp_px = np.full(n_sym, np.nan)
    hyp_stop = np.full(n_sym, np.nan)
    last_won = np.zeros(n_sym, bool)
    hyp_skipped = np.zeros(n_sym, bool)

    cash = cfg.start_equity
    interest = costs = 0.0
    eq_prev = cfg.start_equity
    equity = np.full(n_days, np.nan)
    gross = np.full(n_days, np.nan)
    year_start = cfg.start_equity
    size_eq = cfg.start_equity  # the notional account that units are sized on

    def book(j: int, dq: float, px: float) -> None:
        nonlocal cash, costs
        fee = abs(dq * px) * cost
        cash -= dq * px + fee
        costs += fee
        pos[j]["cash"] -= dq * px + fee
        qty[j] += dq

    def unit_shares(j: int, t: int) -> float:
        if cfg.sizing == "flat":
            return flat_dollars * size_eq / cfg.start_equity / c[t - 1, j]
        return cfg.risk * size_eq / N[t - 1, j]

    def room(j: int, side: int) -> bool:
        if abs(units[j]) >= cfg.max_units:
            return False
        same = units * side > 0
        if sum(abs(units[k]) for k in range(n_sym) if group[k] == group[j] and same[k]) >= cfg.group_units:
            return False
        if sum(abs(units[k]) for k in range(n_sym) if loose[k] == loose[j] and same[k]) >= cfg.loose_units:
            return False
        return int(np.abs(units[same]).sum()) < cfg.side_units

    def enter(j: int, side: int, px: float, t: int, system: int) -> None:
        pos[j] = {"side": side, "day": t, "cash": 0.0, "system": system, "units": 0, "risk1": 0.0, "px": px}
        n_entry[j] = N[t - 1, j]
        add(j, side, px, t)
        pos[j]["risk1"] = abs(qty[j]) * cfg.stop_n * n_entry[j]

    def add(j: int, side: int, px: float, t: int) -> None:
        book(j, side * unit_shares(j, t), px)
        units[j] += side
        pos[j]["units"] = abs(units[j])
        last_fill[j] = px
        stop[j] = px - side * cfg.stop_n * n_entry[j]

    def close(j: int, px: float, t: int, why: str) -> None:
        book(j, -qty[j], px)
        p = pos.pop(j)
        trades.append({"symbol": syms[j], "side": p["side"], "system": p["system"], "entry_day": p["day"], "exit_day": t,
                       "units": p["units"], "pnl": p["cash"], "r": p["cash"] / p["risk1"] if p["risk1"] else np.nan,
                       "exit": why, "entry_px": p["px"], "exit_px": px, "n": n_entry[j]})
        qty[j] = 0.0
        units[j] = 0
        stop[j] = last_fill[j] = n_entry[j] = np.nan

    idx = prices.index
    start = 56
    if cfg.sizing == "flat":  # match the typical N-sized unit's dollar size, so only the spread across markets changes
        typical = np.nanmedian(cfg.risk * cfg.start_equity / N[start:] * c[start:])
        flat_dollars = float(typical)
    for t in range(start, n_days):
        if idx[t].year != idx[t - 1].year:
            year_start = eq_prev
        size_eq = eq_prev
        if cfg.use_dd_rule and eq_prev < year_start * 0.9:
            steps = int(np.floor(np.log(eq_prev / year_start) / np.log(0.9) + 1e-9))
            size_eq = min(eq_prev, year_start * 0.8 ** steps)
        day_int = cash * rf[t - 1]
        cash += day_int
        interest += day_int
        for j in range(n_sym):
            if not (np.isfinite(c[t, j]) and np.isfinite(N[t - 1, j]) and np.isfinite(hi55[t, j])):
                continue
            side = int(np.sign(units[j]))
            # 1. exits: the 2N stop or the exit breakout, whichever is nearer
            if side == 1:
                level = max(stop[j], lo_out[t, j])
                if l[t, j] <= level:
                    close(j, min(o[t, j], level), t, "stop" if stop[j] >= lo_out[t, j] else "breakout")
                    side = 0
            elif side == -1:
                level = min(stop[j], hi_out[t, j])
                if h[t, j] >= level:
                    close(j, max(o[t, j], level), t, "stop" if stop[j] <= hi_out[t, j] else "breakout")
                    side = 0
            # 2. adds every 1/2 N
            if side != 0 and cfg.pyramid:
                while abs(units[j]) < cfg.max_units and room(j, side):
                    nxt = last_fill[j] + side * cfg.add_n * n_entry[j]
                    if (side == 1 and h[t, j] >= nxt) or (side == -1 and l[t, j] <= nxt):
                        add(j, side, max(o[t, j], nxt) if side == 1 else min(o[t, j], nxt), t)
                    else:
                        break
            # 3. the System 1 filter's hypothetical trade (uses 20/10-day levels whatever the system)
            if cfg.system == 1:
                hs = hyp_side[j]
                if hs == 1 and (l[t, j] <= hyp_stop[j] or l[t, j] <= lo_out[t, j]):
                    lost = hyp_stop[j] >= lo_out[t, j] and l[t, j] <= hyp_stop[j]
                    last_won[j], hyp_side[j] = not lost, 0
                elif hs == -1 and (h[t, j] >= hyp_stop[j] or h[t, j] >= hi_out[t, j]):
                    lost = hyp_stop[j] <= hi_out[t, j] and h[t, j] >= hyp_stop[j]
                    last_won[j], hyp_side[j] = not lost, 0
            up, dn = h[t, j] >= hi_in[t, j], l[t, j] <= lo_in[t, j]
            brk = 1 if up and not dn else -1 if dn and not up else 0
            skip = False
            if cfg.system == 1 and not cfg.loose_filter and hyp_side[j] != 0 and hyp_skipped[j]:
                skip = True  # still inside a skipped breakout: only the 55-day fail-safe may enter
            if cfg.system == 1 and brk and hyp_side[j] == 0:
                skip = cfg.use_filter and last_won[j]
                hyp_skipped[j] = skip
                hyp_side[j], hyp_px[j] = brk, hi_in[t, j] if brk == 1 else lo_in[t, j]
                hyp_stop[j] = hyp_px[j] - brk * cfg.stop_n * N[t - 1, j]
            # 4. new entries when flat
            if side == 0:
                if brk and not skip and room(j, brk):
                    lvl = hi_in[t, j] if brk == 1 else lo_in[t, j]
                    enter(j, brk, max(o[t, j], lvl) if brk == 1 else min(o[t, j], lvl), t, cfg.system)
                elif cfg.system == 1 and skip:  # fail-safe: take the 55-day breakout anyway
                    f = 1 if h[t, j] >= hi55[t, j] else -1 if l[t, j] <= lo55[t, j] else 0
                    if f and room(j, f):
                        lvl = hi55[t, j] if f == 1 else lo55[t, j]
                        enter(j, f, max(o[t, j], lvl) if f == 1 else min(o[t, j], lvl), t, 1)
        px = np.where(np.isfinite(c[t]), c[t], 0.0)
        eq = cash + float(np.dot(qty, px))
        equity[t] = eq
        gross[t] = float(np.abs(qty * px).sum()) / eq
        eq_prev = eq

    tr = pd.DataFrame(trades)
    if not tr.empty:
        tr["entry_date"] = idx[tr["entry_day"]]
        tr["exit_date"] = idx[tr["exit_day"]]
        tr["days"] = tr["exit_day"] - tr["entry_day"]
    open_value = float(np.dot(qty, np.where(np.isfinite(c[-1]), c[-1], 0.0)))
    open_cash = sum(p["cash"] for p in pos.values())
    return Result(pd.Series(equity, idx).dropna(), pd.Series(gross, idx).dropna(), tr, interest, costs, open_value, open_cash,
                  int(np.abs(units).sum()))


def stats(eq: pd.Series, trades: pd.DataFrame | None = None) -> dict[str, float]:
    rets = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    dd = eq / eq.cummax() - 1
    downside = np.sqrt((np.minimum(rets, 0) ** 2).mean()) * np.sqrt(252)
    out = {"cagr": cagr, "max_dd": -dd.min(), "vol": rets.std() * np.sqrt(252),
           "sortino": rets.mean() * 252 / downside if downside > 0 else np.nan,
           "mar": cagr / -dd.min() if dd.min() < 0 else np.nan, "growth": eq.iloc[-1] / eq.iloc[0]}
    if trades is not None and not trades.empty:
        wins, losses = trades.pnl[trades.pnl > 0].sum(), -trades.pnl[trades.pnl < 0].sum()
        out |= {"trades": len(trades), "win_rate": (trades.pnl > 0).mean(), "profit_factor": wins / losses}
    return out
