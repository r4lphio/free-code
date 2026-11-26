# Square of nine test (Python)

The test from r4lph's video "My AI tested Gann's square of nine". It draws textbook square-of-nine levels from
the latest swing high or low, and checks whether price reacts to them more than to random levels with the same
spacing, before and after costs. Research and education, not trading advice.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python fetch_data.py data          # the 50 markets in data/universe.csv, from Yahoo Finance
python validate.py .               # the engine's checks (see below)
python spy_check.py data           # SPY alone: the levels to compare with TradingView, and the test
python run_tests.py .              # every setting, Gann against 200 sets of random levels (minutes on 20 cores)
```

Results go to `results/`. Yahoo's data changes a little over time, so a fresh download can give slightly different
numbers from the video.

## Files

| File | What it does |
|---|---|
| `engine.py` | The simulator. `run_market()` runs one market with Gann levels or a random set; the docstring states every rule. |
| `fetch_data.py` | Downloads daily prices, split adjusted but not dividend adjusted (the levels depend on the price as a chart shows it). |
| `data/universe.csv` | The 50 markets: the 30 largest stock ETFs, the 8 largest bond ETFs, 7 commodity funds, the 5 largest coins, picked by size on 19 November 2026. |
| `validate.py` | Checks the engine: a second implementation, look-ahead, and accounting. |
| `spy_check.py` | SPY alone, for comparing with the TradingView indicator. |
| `run_tests.py` | Every setting (45, 90 and 180 degrees; swings of 5, 10 and 20 days), fade and break, before and after costs. Results for all markets and for each asset class, and each market's rank. |

## The method

- **Levels.** level = (sqrt(anchor) + degrees / 180)^2. One full turn (360 degrees) adds 2 to the square root.
- **Anchor.** The latest swing high or low (the highest high or lowest low of 10 bars on each side). It is known only
  10 bars later, so the test waits. The video also used anchors from r4lph's own Gann swing indicator. That
  indicator is not in this code, so those results can't be rerun here.
- **Random levels.** The same spacing, shifted by a random amount for each anchor. Only the starting point differs.
- **Hold rate.** When a day touches the first level above (or below) yesterday's close, does it close back on its side?
- **Trades.** Fade: sell at the level above, buy at the level below, stop at the next level, target at the level
  before. Break: the mirror. 5 basis points per side.
- **Ruin.** A short can lose more than 100% when the levels are far apart (XRP under $1). An account at zero stops
  trading.

## The checks

1. A plain loop written separately makes the same SPY trades, touches and holds as the engine.
2. Cutting the data at 40 random dates changes no earlier trade, so nothing uses future prices.
3. Equity rebuilt from each trade's prices and the cost rule matches the engine.

The first version had a look-ahead bug inside the day (it skipped days that touched two levels, which used the rest
of the day). The engine now decides the order from the open only. Check 2 can't catch that kind of bug, so read the
"Bar order" rule in `engine.py` if you change the trade logic.
