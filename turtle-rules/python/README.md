# Turtle rules backtest (Python)

The backtest from r4lph's video "My AI Backtested the Famous Turtle Trading Rules Overnight". It runs the
original Turtle rules (both systems, N sizing, adds, stops, exits, the unit limits and the drawdown rule) on
daily prices for one symbol or a portfolio. Research and education, not trading advice.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python fetch_data.py data          # 24 ETFs, March 2007 to November 2026, from Yahoo Finance
python validate.py data            # the engine's checks (see below)
python spy_check.py data           # SPY alone, with the TradingView script's default settings
python run_portfolio.py data       # both systems, 4 unit sizes, before and after costs
```

`run_portfolio.py` writes `results/portfolio.csv`. Yahoo's data changes a little over time, so a fresh
download can give slightly different numbers from the video.

## Files

| File | What it does |
|---|---|
| `engine.py` | The simulator. `Config` holds every setting; `run()` returns the equity curve and the trades. |
| `fetch_data.py` | Downloads prices and the T-bill rate. `--symbols` and `--end` change what it gets. |
| `spy_check.py` | One symbol with the Pine script's defaults, to compare with TradingView. |
| `run_portfolio.py` | The portfolio test across unit sizes and costs. |
| `validate.py` | Checks the engine: a second implementation, look-ahead, and accounting. |

## The checks

1. A plain loop written separately makes the same 103 SPY trades (System 2, no adds) at the same prices.
2. No entry fills inside the breakout range of earlier days, so no entry uses future prices.
3. Closed trade profit + open positions + interest equals the change in the account, to the cent.

## One correction to know about

The first version of this engine, used for the video's System 1 numbers, skipped a breakout after a
winner for one day only. The original rule skips the whole breakout. This code uses the original rule.
`--loose-filter` (in `spy_check.py` and `run_portfolio.py`) or `Config(loose_filter=True)` reproduces the
first version. System 2 has no filter, so its numbers are the same in both.

## Assumptions

- Daily prices, dividend adjusted. Orders are stop orders; a gap through a level fills at the open.
- Costs: 5 basis points per side on traded value. Cash earns or pays the 13-week T-bill rate.
- Fractional shares. Shorts pay no borrow fee. The account starts at $10,000,000.
- ETFs stand in for the futures the Turtles traded.
