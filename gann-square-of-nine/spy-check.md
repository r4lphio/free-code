# SPY cross-check: Python against TradingView

Use these numbers to check the Pine indicator in TradingView, and to see the test on one symbol. They come from
`python/spy_check.py`, run on Yahoo Finance data to 17 November 2026:

```
python spy_check.py data
```

## 1. The levels (check the indicator)

In TradingView: SPY, daily (`1D`), dividend adjustment off. In the indicator settings, set **Anchor** to "Manual
price", **Manual anchor price** to `348.11` (SPY's low on 13 October 2022), and **Degrees between levels** to 45.
The labels should match this table to the cent:

| Degrees | Level | | Degrees | Level |
|---|---|---|---|---|
| -180 | 311.79 | | 180 | 386.43 |
| -135 | 320.69 | | 225 | 396.32 |
| -90 | 329.70 | | 270 | 406.33 |
| -45 | 338.84 | | 315 | 416.47 |
| 0 (anchor) | 348.11 | | 360 | 426.74 |
| 45 | 357.50 | | 405 | 437.13 |
| 90 | 367.02 | | 450 | 447.65 |
| 135 | 376.66 | | 495 | 458.29 |

Check one by hand: the square root of 348.11 is 18.658. Add 0.25 for 45 degrees: 18.908. Squared: 357.50.

If TradingView shows a different low for 13 October 2022, check that dividend adjustment is off. The formula is
exact, so any difference comes from the anchor price.

## 2. The test on SPY alone

45 degrees, swing length 10, 1 March 2007 to 17 November 2026. Random levels: 200 sets with the same spacing.

| | Gann levels | Random levels (median) | Gann beats |
|---|---|---|---|
| Touches | 2,059 | | |
| Hold rate (the day closed back on its side) | 44.6% | 42.6% | 98% of random sets |
| Fade trades | 460 | | |
| Fade, average trade, before costs | +0.03% | -0.05% | 73% |
| Fade, average trade, after 5 bps a side | -0.07% | -0.15% | 73% |
| Fade, annual return after costs | -2.9% (worst drop 77%) | | |
| Break, average trade, after costs | -0.13% | -0.05% | 27% |

SPY is one of three markets (with LQD and DBC) where the Gann levels held more often than 95% of random sets. On XLU
they were in the bottom 5%. Across all 25 markets the Gann hold rate was 40.6%, the same as random levels, and Gann
beat the random middle in 13 of 25 markets. A few good markets are what luck gives, so don't judge the method on SPY
alone.

The trades in Python don't exist in the indicator. The indicator only draws the levels.
