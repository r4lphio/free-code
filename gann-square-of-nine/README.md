# Free code: Gann's square of nine levels (basic version)

From r4lph's video "My AI tested Gann's square of nine". My AI coding agent built this from public sources,
tested it on 25 markets against random levels, and wrote this code. You can use it, change it, and share it.

This is a basic, educational version of the textbook method. It is research and education, not trading advice.
In our test, these levels did no better than random levels with the same spacing.

## What's in this folder

| File | For |
|---|---|
| `gann-square-of-nine.pine` | TradingView. Paste it in and see square-of-nine levels on any chart. No coding needed. |
| `spy-check.md` | The exact levels to expect on SPY, so you can check that it works, plus the test on SPY alone. |
| `python/` | The full test, for people who run Python. It has its own README. |

## What the indicator draws

The square of nine is a spiral of numbers with 1 in the middle. Traders turn it into price levels with one formula:

    level = (square root of the anchor price + degrees / 180) squared

One full turn of the spiral (360 degrees) adds 2 to the square root. 180 degrees adds 1, 90 adds 0.5, and 45 adds
0.25. The indicator takes an anchor price, then draws a line every 45 degrees (or 90, 180, 360) above and below it.

- **Solid lines** are full turns (every 360 degrees). **Dashed lines** are the steps in between.
- **Orange** lines are above the anchor, **teal** lines below, and the **gray** line is the anchor itself.
- Each line has a label: its angle and its price.

## Put it on a TradingView chart (about 2 minutes)

1. Go to tradingview.com and open a chart. A free account is fine.
2. Type `SPY` to load the symbol, and pick the daily timeframe (`1D`).
3. Leave dividend adjustment **off** (the `ADJ` button at the bottom right is not highlighted). The levels use the
   price as the chart shows it.
4. Open the **Pine Editor** tab at the bottom of the screen.
5. Delete the text in the editor. Open `gann-square-of-nine.pine` in any text editor, copy all of it, and paste it in.
6. Click **Save** (give it any name), then **Add to chart**.

You now see lines from the latest swing high or low (a small gray dot marks it).

## Change the settings

Click the gear next to the indicator's name on the chart.

- **Anchor**: "Latest swing" uses the most recent swing high or low. "Manual price" uses the price you type in.
- **Manual anchor price**: for example, a big low you picked yourself.
- **Swing length**: how many bars on each side make a swing. 10 is what the test used. A swing is only known that
  many bars later, so the anchor never uses future bars.
- **Degrees between levels**: 45, 90, 180 or 360.
- **Levels above and below**: how many lines to draw on each side.

To check it, set Anchor to "Manual price", type `348.11` (SPY's low on 13 October 2022), and compare the labels with
`spy-check.md`.

## What the test found

My AI tested these levels on 24 ETFs (2007 to 2026) and Bitcoin (2014 to 2026), against 200 sets of random levels
with the same spacing:

- A touched Gann level held 40.6% of the time. Random levels held 40.6% too.
- Trading the levels (fade the touch, or follow the break) lost money after costs, about the same as random levels.
- On SPY alone, the levels looked good (better than 97% of random sets), and on a bond fund and a commodity fund too.
  On utilities (XLU) they looked bad. Across all 25 markets, Gann beat the random middle in 13: a coin flip.

`python/` has the full test and its checks. Read `spy-check.md` for the SPY numbers.

## Sources

The formula and the usage come from public sources, not from Gann's own courses (he never wrote the formula out
clearly):

- LuxAlgo, "Gann Square-of-9 Levels": https://www.luxalgo.com/library/concept/gann-square-of-9-levels/
- Strike Money, "Gann Square of 9 Calculator": https://www.strike.money/free-tools/gann-square-of-9-calculator
- Optuma Knowledge Base, "Square of 9 Gann Fan" (credits the formula to Daniel Ferrera):
  https://www.optuma.com/kb/gann-and-astro/gann-tools/square-of-9-gann-fan
- Tradingsim, "Gann Square of Nine: How to Trade Using This Forecasting Tool":
  https://www.tradingsim.com/day-trading/day-trade-using-gann-square
- Patrick Mikula, "The Definitive Guide to Forecasting Using W.D. Gann's Square of Nine" (2003), the standard
  modern book on the method.
