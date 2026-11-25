"""Daily portfolio simulator for Tom Basso's trend-following and sizing rules.

Entries and exits are stop orders. Sizing follows his four layers, which you can switch on one at a time:
  1. initial risk     units = equity * risk% / distance to stop
  2. initial vol      units = min(risk units, equity * vol% / ATR)
  3. ongoing limits   trim a position when its open risk or its volatility grows past a limit
  4. portfolio caps   assume correlation 1.0 and trim every position in proportion when total risk or vol is too high
Trims are decided at the close and filled at the next open, the way he describes it.
Cash earns (or, when borrowed, pays) the T-bill rate, like a futures or margin account.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Sizing:
    """Basso's 2022 settings (TraderLion talk, 38:16). Set a layer flag to False to switch it off."""

    init_risk: float = 0.005
    init_vol: float = 0.003
    ongoing_risk: float = 0.01
    ongoing_vol: float = 0.004
    total_risk: float = 0.16
    total_vol: float = 0.06
    use_init_vol: bool = True
    use_ongoing: bool = True
    use_caps: bool = True


@dataclass(frozen=True)
class Config:
    lookback: int = 21
    band_mult: float = 2.0  # Keltner: EMA +/- band_mult * ATR
    entry: str = "keltner"  # "keltner" (stop and reverse at the bands) or "random"
    trail_mult: float = 3.0  # random entry only: chandelier stop at trail_mult * ATR
    cost_bps: float = 5.0  # per side, on traded value
    start_equity: float = 10_000_000.0
    seed: int = 0
    sizing: Sizing = field(default_factory=Sizing)


@dataclass
class Result:
    equity: pd.Series
    gross: pd.Series  # gross exposure / equity
    trades: pd.DataFrame  # one row per round trip, P&L includes trims


def indicators(prices: pd.DataFrame, n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """EMA of close and simple n-day average true range, per symbol."""
    h, l, c = prices["High"], prices["Low"], prices["Close"]
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()]).groupby(level=0).max()
    tr = tr.reindex(c.index)
    return c.ewm(span=n, adjust=False).mean(), tr.rolling(n).mean()


def run(prices: pd.DataFrame, cfg: Config, tbill: pd.Series | None = None) -> Result:
    """tbill: annual percent yield by date. None means cash earns nothing."""
    sz = cfg.sizing
    o, h, l, c = (prices[f].to_numpy(float) for f in ("Open", "High", "Low", "Close"))
    ema_df, atr_df = indicators(prices, cfg.lookback)
    ema, atr = ema_df.to_numpy(float), atr_df.to_numpy(float)
    upper, lower = ema + cfg.band_mult * atr, ema - cfg.band_mult * atr
    n_days, n_sym = c.shape
    rng = np.random.default_rng(cfg.seed)
    cost = cfg.cost_bps / 1e4
    if tbill is None:
        rf = np.zeros(n_days)
    else:
        rf = tbill.reindex(prices.index).ffill().fillna(0.0).to_numpy(float) / 100 / 252

    units = np.zeros(n_sym)  # signed
    stop = np.full(n_sym, np.nan)
    target = np.full(n_sym, np.nan)  # pending trim, filled at next open
    cash = cfg.start_equity
    equity = np.full(n_days, np.nan)
    gross = np.full(n_days, np.nan)
    open_trade: dict[int, dict] = {}
    trades: list[dict] = []
    eq_prev = cfg.start_equity

    def trade(j: int, qty: float, px: float) -> None:
        """Change position j by qty at price px, booking cash and cost against the open trade."""
        nonlocal cash
        cash -= qty * px + abs(qty * px) * cost
        if j in open_trade:
            open_trade[j]["cash"] -= qty * px + abs(qty * px) * cost

    def close_trade(j: int, px: float, day: int) -> None:
        trade(j, -units[j], px)
        t = open_trade.pop(j)
        # Round-trip P&L is the net cash flow of entry, trims and exit.
        trades.append({"symbol": j, "side": t["side"], "entry_day": t["day"], "exit_day": day,
                       "pnl": t["cash"], "pnl_pct_equity": t["cash"] / t["equity"]})
        units[j] = 0.0
        stop[j] = np.nan

    def open_new(j: int, side: int, px: float, stop_px: float, day: int, eq: float) -> None:
        dist = abs(px - stop_px)
        if not np.isfinite(dist) or dist <= 0 or not np.isfinite(atr[day - 1, j]):
            return
        qty = eq * sz.init_risk / dist
        if sz.use_init_vol:
            qty = min(qty, eq * sz.init_vol / atr[day - 1, j])
        open_trade[j] = {"side": side, "day": day, "equity": eq, "cash": 0.0}
        units[j] = side * qty
        trade(j, side * qty, px)
        stop[j] = stop_px

    start = cfg.lookback + 1
    for t in range(start, n_days):
        cash += cash * rf[t - 1]  # overnight interest on yesterday's balance
        # 1. pending trims at the open
        for j in np.flatnonzero(np.isfinite(target)):
            if units[j] != 0:
                trade(j, target[j] - units[j], o[t, j])
                units[j] = target[j]
            target[j] = np.nan

        for j in range(n_sym):
            if not np.isfinite(c[t, j]) or not np.isfinite(upper[t - 1, j]):
                continue
            side = int(np.sign(units[j]))
            # 2. stops on open positions (gap fills at the open)
            if side == 1 and l[t, j] <= stop[j]:
                close_trade(j, min(o[t, j], stop[j]), t)
                if cfg.entry == "keltner":
                    open_new(j, -1, min(o[t, j], lower[t - 1, j]), upper[t - 1, j], t, eq_prev)
                continue
            if side == -1 and h[t, j] >= stop[j]:
                close_trade(j, max(o[t, j], stop[j]), t)
                if cfg.entry == "keltner":
                    open_new(j, 1, max(o[t, j], upper[t - 1, j]), lower[t - 1, j], t, eq_prev)
                continue
            # 3. new entries when flat
            if side == 0:
                if cfg.entry == "keltner":
                    up_hit, dn_hit = h[t, j] >= upper[t - 1, j], l[t, j] <= lower[t - 1, j]
                    if up_hit and not dn_hit:
                        open_new(j, 1, max(o[t, j], upper[t - 1, j]), lower[t - 1, j], t, eq_prev)
                    elif dn_hit and not up_hit:
                        open_new(j, -1, min(o[t, j], lower[t - 1, j]), upper[t - 1, j], t, eq_prev)
                else:
                    d = 1 if rng.random() < 0.5 else -1
                    open_new(j, d, o[t, j], o[t, j] - d * cfg.trail_mult * atr[t - 1, j], t, eq_prev)

        # 4. mark to market and move stops for tomorrow
        px = np.where(np.isfinite(c[t]), c[t], 0.0)
        eq = cash + float(np.dot(units, px))
        equity[t] = eq
        gross[t] = float(np.abs(units * px).sum()) / eq
        eq_prev = eq
        live = units != 0
        if cfg.entry == "keltner":
            stop[live & (units > 0)] = lower[t][live & (units > 0)]
            stop[live & (units < 0)] = upper[t][live & (units < 0)]
        else:
            long_, short_ = live & (units > 0), live & (units < 0)
            stop[long_] = np.maximum(stop[long_], (c[t] - cfg.trail_mult * atr[t])[long_])
            stop[short_] = np.minimum(stop[short_], (c[t] + cfg.trail_mult * atr[t])[short_])

        # 5. decide trims for tomorrow's open
        if not live.any() or not (sz.use_ongoing or sz.use_caps):
            continue
        new = units.copy()
        risk_unit = np.where(live, np.maximum(np.sign(units) * (c[t] - stop), 0.0), 0.0)
        if sz.use_ongoing:
            with np.errstate(divide="ignore", invalid="ignore"):
                cap_r = np.where(risk_unit > 0, eq * sz.ongoing_risk / risk_unit, np.inf)
                cap_v = eq * sz.ongoing_vol / atr[t]
            cap = np.nan_to_num(np.minimum(cap_r, cap_v), nan=np.inf)
            new = np.sign(new) * np.minimum(np.abs(new), cap)
        if sz.use_caps:
            tot_r = float((np.abs(new) * risk_unit).sum()) / eq
            tot_v = float(np.nansum(np.abs(new) * atr[t])) / eq
            scale = min(1.0, sz.total_risk / tot_r if tot_r > 0 else 1.0, sz.total_vol / tot_v if tot_v > 0 else 1.0)
            new = new * scale
        changed = live & (np.abs(new) < np.abs(units) * 0.999)
        target[changed] = new[changed]

    idx = prices.index
    eq_s = pd.Series(equity, idx).dropna()
    tr = pd.DataFrame(trades)
    if not tr.empty:
        tr["symbol"] = [prices["Close"].columns[j] for j in tr["symbol"]]
        tr["entry_date"] = idx[tr["entry_day"]]
        tr["exit_date"] = idx[tr["exit_day"]]
    return Result(eq_s, pd.Series(gross, idx).dropna(), tr)


def stats(eq: pd.Series, trades: pd.DataFrame | None = None) -> dict[str, float]:
    """Return-to-risk numbers he quotes: CAGR, max drawdown, Sortino, MAR, plus trade stats."""
    rets = eq.pct_change().dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    dd = eq / eq.cummax() - 1
    downside = np.sqrt((np.minimum(rets, 0) ** 2).mean()) * np.sqrt(252)
    out = {
        "cagr": cagr,
        "max_dd": -dd.min(),
        "sortino": rets.mean() * 252 / downside if downside > 0 else np.nan,
        "mar": cagr / -dd.min() if dd.min() < 0 else np.nan,
    }
    if trades is not None and not trades.empty:
        wins, losses = trades.pnl[trades.pnl > 0].sum(), -trades.pnl[trades.pnl < 0].sum()
        out |= {"trades": len(trades), "win_rate": (trades.pnl > 0).mean(), "profit_factor": wins / losses}
    return out
