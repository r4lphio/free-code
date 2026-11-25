# Tom Basso backtest (Python)

The backtest from r4lph's video "Coin Flips Beat Tom Basso's Entry Until Costs Hit". It runs Tom Basso's
Keltner trend rules with his four sizing layers on a portfolio of daily prices, and compares them with random
entries. Research and education, not trading advice.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
mkdir -p data results
python fetch.py data                       # 24 ETFs, March 2007 to November 2026, from Yahoo Finance
python sizing_study.py data results        # test 1: the four sizing layers, one at a time
python more_tests.py data results 500      # tests 2 to 4: coin flip after costs, big winners, lookbacks
python cost_check.py data results          # the same runs before costs
python charts.py results                   # the charts from the video, as PNG files
```

Run the scripts in this order. Each one reads files that the one before it wrote. The coin-flip runs use
every CPU core and take about 1 minute on 24 cores. Yahoo's data changes a little over time, so a fresh
download can give slightly different numbers from the video.

## Files

| File | What it does |
|---|---|
| `engine.py` | The simulator. `Config` and `Sizing` hold every setting; `run()` returns the equity curve and the trades. |
| `fetch.py` | Downloads the prices and the 13-week T-bill rate. |
| `sizing_study.py` | Test 1. Writes `sizing_study.csv`, the equity curves and the trades. |
| `more_tests.py` | Tests 2 to 4. Writes `random_entry.csv`, `big_winners.csv` and `lookback_sweep.csv`. |
| `cost_check.py` | Reruns the systems at zero cost. Writes `cost_check.csv` and `random_entry_zero_cost.csv`. |
| `charts.py` | Draws the charts from the result files. |

## Assumptions

- Daily prices, dividend adjusted. Entries and exits are stop orders; a gap through a level fills at the open.
- Trims are decided at the close and filled at the next open.
- Costs: 5 basis points per side on traded value. Cash earns or pays the 13-week T-bill rate.
- Fractional units. Shorts pay no borrow fee. The account starts at $10,000,000.
- ETFs stand in for the futures that Basso traded.
