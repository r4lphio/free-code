"""Run one symbol with the Pine script's default settings, so the numbers can be compared with TradingView.

Pine defaults: System 2 (55-day), 0.1% of the account per N, 5 bps commission per side, no slippage, a
$10,000,000 account, whole shares not enforced (TradingView rounds down; the effect is tiny at this size),
and no interest on cash (TradingView pays none).

Usage: python spy_check.py data [--symbol SPY] [--system 2] [--risk 0.001] [--interest] [--loose-filter]
"""

import argparse

import pandas as pd

from engine import Config, run, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--system", type=int, default=2)
    ap.add_argument("--risk", type=float, default=0.001)
    ap.add_argument("--cost-bps", type=float, default=5.0)
    ap.add_argument("--interest", action="store_true", help="pay T-bill interest on cash, as the portfolio test does")
    ap.add_argument("--loose-filter", action="store_true")
    a = ap.parse_args()

    prices = pd.read_parquet(f"{a.data_dir}/prices.parquet")
    one = prices.loc[:, (slice(None), [a.symbol])]
    tbill = pd.read_parquet(f"{a.data_dir}/tbill.parquet")["irx"] if a.interest else None
    cfg = Config(system=a.system, risk=a.risk, cost_bps=a.cost_bps, loose_filter=a.loose_filter)
    res = run(one, cfg, tbill)
    st = stats(res.equity, res.trades)
    tr = res.trades
    first_order_day = prices.index[55].date()  # entries on day 56 use orders placed at day 55's close
    units = int(tr.units.sum())
    print(f"{a.symbol} System {a.system}, {a.risk:.2%} per N, {a.cost_bps:g} bps per side, interest {'on' if a.interest else 'off'}")
    print(f"window: orders from {first_order_day} to {res.equity.index[-1].date()}")
    print(f"positions closed: {len(tr)}; unit fills in them: {units}; units still open at the end: {res.open_units}")
    print(f"win rate (positions): {st['win_rate']:.1%}; profit factor: {st['profit_factor']:.2f}")
    print(f"final equity: ${res.equity.iloc[-1]:,.0f} (net {res.equity.iloc[-1] / cfg.start_equity - 1:+.2%})")
    print(f"CAGR: {st['cagr']:+.2%}; max drawdown (daily closes): {st['max_dd']:.2%}; costs paid: ${res.costs:,.0f}")
    if res.open_units:
        print(f"open at the end: market value ${res.open_value:,.0f}")


if __name__ == "__main__":
    main()
