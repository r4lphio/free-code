# Mars-Jupiter aspects: the full test in Python

The code behind the video "My AI tested Mars-Jupiter aspects on 50 markets". It computes every Mars-Jupiter aspect
from NASA's public ephemeris, tests the aspect trade on 50 markets against 1,000 shifted calendars, and checks its
own work. `TEST-PLAN.md` holds the rules, written down before the first run.

Research and education, not trading advice.

## Set up

Python 3.11 or newer.

```
pip install -r requirements.txt
```

## Run it

```
python aspects.py data/de440s.bsp data/aspects.csv     # aspect dates, 1990 to 2036 (downloads NASA's 32 MB file once)
python fetch_data.py data                                # daily prices for the 50 markets from Yahoo Finance
python run_tests.py .                                    # every test, 1,000 shifted calendars (about 2 minutes on 12 cores)
python posthoc.py .                                      # the checks added after the first run
python benchmarks.py .                                   # buy and hold, and time in a trade
python validate.py .                                     # the independent checks
python spy_check.py SPY                                  # one symbol's trades, to compare with TradingView
python make_pine.py data/aspects.csv ../mars-jupiter-aspects.pine   # rebuild the TradingView script
```

`data/aspects.csv` and `data/aspects-daily.csv` are already here, so you can skip the first line. Results go to `results/`: `summary.csv` has
every test against the shifted calendars ("beat_share" is the share of shifted calendars the real one beat).

## Files

| File | What it does |
|---|---|
| `aspects.py` | Finds every exact aspect (0, 60, 90, 120, 180 degrees) with Skyfield and NASA JPL DE440s. Geocentric, tropical. |
| `engine.py` | The trade, the portfolio, the 1,000-calendar baseline, and the secondary tests. |
| `run_tests.py` | Runs the plan in `TEST-PLAN.md` on the real calendar and 1,000 shifted ones. |
| `posthoc.py` | The sextile split and the two named claims (Williams, Matlock). |
| `benchmarks.py` | Buy and hold for each asset class, and the share of days in a trade. |
| `validate.py` | A second ephemeris (Swiss Ephemeris), published dates, a second implementation, no look-ahead, and more. |
| `spy_check.py` | Prints one symbol's trades and totals. |
| `fetch_data.py` | Downloads the prices (split adjusted, not dividend adjusted). |
| `make_pine.py` | Writes the TradingView indicator with the dates built in. |
| `data/aspects.csv`, `data/aspects-daily.csv` | Every exact aspect, 1990 to 2036, and the Mars-Jupiter angle each day. |
| `data/universe-50.csv` | The 50 markets: the largest by size on 19 November 2026, picked by a rule written down first. |

## The 50 markets

The 30 largest US-listed equity ETFs, the 8 largest bond ETFs, the largest fund in each of 7 commodity groups
(gold, silver, crude oil, natural gas, copper, agriculture, broad index) and the 5 largest coins, by size on
19 November 2026. One fund per index; no leveraged, inverse, option-income or cash-like funds; at least 5 years of
prices. Picking by today's size favors winners a little: funds and coins that shrank or closed are not in the list.

## Licences

Skyfield and NASA's ephemeris are free to use. Swiss Ephemeris (`pyswisseph`, used only in `validate.py`) is
dual-licensed (AGPL or a paid licence). Yahoo Finance data is for personal use.
