# SPY cross-check: Python against TradingView

Use these numbers to check the Pine script in TradingView's Strategy Tester. They come from the Python
engine in `python/`, run on SPY alone with the Pine script's default settings. In TradingView, also turn on
**Stop at an end date** in the Inputs, so the test ends on 6 November 2026 like the Python run:

```
python spy_check.py data                 # the defaults below
python spy_check.py data --interest      # the same, with T-bill interest on cash
python spy_check.py data --system 1      # System 1 instead
```

## Settings (the Pine script's defaults)

| Setting | Value |
|---|---|
| Symbol, timeframe | SPY, daily (1D), dividend adjusted |
| System | System 2: 55-day entry, 20-day exit |
| Risk per unit | 0.1% of the account per N (the original rule is 1%) |
| N | 20-day Wilder average of the true range |
| Adds, stop | 1 more unit each 1/2 N, up to 4 units; stop 2 N behind the last fill |
| Costs | 0.05% commission per side (5 basis points), no slippage |
| Account | $10,000,000, no interest on cash |
| Dates | Orders from the close of 18 May 2007; last day 6 November 2026 (turn on "Stop at an end date") |

## Python results (System 2, 0.1%, no interest)

| Number | Value |
|---|---|
| Positions closed | 123 (a position is all the units of one trade) |
| Unit fills in those positions | 386 |
| Units still open on 6 Nov 2026 | 2 (a short position) |
| Win rate, by position | 24.4% |
| Final equity, open position at the 6 Nov close | $10,467,998 |
| Net profit | +$467,998 (+4.68%) |
| CAGR | +0.24% a year |
| Max drawdown, daily closes | 11.11% |
| Costs paid | $331,416 |

With T-bill interest on cash, as in the portfolio test: CAGR +1.56%, max drawdown 6.71%, net +35.02%.
System 1 (0.1%, no interest): 179 positions, CAGR -0.41%, max drawdown 10.55%, net -7.71%.
System 2 at the original 1%: CAGR -0.39%, max drawdown 65.02%, net -7.65%.

## What TradingView shows

We ran the script in TradingView on 19 November 2026: SPY, daily, dividend adjusted, default settings,
"Stop at an end date" on.

| Strategy report | TradingView | Python | Why they differ |
|---|---|---|---|
| Total trades | 377 | 388 units (386 closed, 2 open) | TradingView counts every unit as a trade. It adds at most one unit per bar; Python can add several on a gap |
| Total PnL | +5.80% ($580,364) | +4.68% ($467,998) | TradingView's prices, and the last 2 units close at the 9 Nov open, not the 6 Nov close |
| Max drawdown | 7.32% | 8.00% on closed trades, 11.11% on daily closes | TradingView measures it on closed trades. Python's 11.11% also counts open trades |
| Profitable trades | 33.4% (126 of 377) | 24.4% of positions | TradingView counts winning units, not winning positions |

Small differences are normal: TradingView's own prices and dividend adjustment, whole shares, one add per
bar, and the order of fills inside a bar. A large difference (for example a trade count far from 377) means
a setting is off. Check the timeframe, the dividend adjustment, the end date and the start date first.

## How this relates to the portfolio test

This is one ETF. The video's main test ran both systems on 24 ETFs at once, with the Turtle limits across
markets and interest on cash (`python run_portfolio.py data` reproduces it). SPY alone, at 0.1%, made about a quarter of a
percent a year before interest. Buying and holding SPY made 10.4% a year over the same period.
