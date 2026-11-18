# Free code: the Turtle Trading rules

From r4lph's video "My AI Backtested the Famous Turtle Trading Rules Overnight". My AI coding agent rebuilt
the original Turtle rules, tested them, and wrote this code. You can use it, change it, and share it.

This is research and education, not trading advice. Past results don't predict future results.

## What's in this folder

| File | For |
|---|---|
| `turtle-rules.pine` | TradingView. Paste it in and see the Turtle rules trade any chart. No coding needed. |
| `spy-check.md` | The numbers to expect on SPY, so you can check that it works. |
| `python/` | The full backtest, for people who run Python. It has its own README. |

## Put it on a TradingView chart (about 2 minutes)

1. Go to tradingview.com and open a chart. A free account is fine.
2. Type `SPY` to load the symbol, and pick the daily timeframe (`1D`).
3. Turn on dividend adjustment, so the prices match the backtest: click `ADJ` at the bottom right of the
   chart, or open the chart settings (the gear) and tick "Adjust data for dividends" on the Symbol tab.
4. Open the **Pine Editor** tab at the bottom of the screen.
5. Delete the text in the editor. Open `turtle-rules.pine` in any text editor, copy all of it, and paste it in.
6. Click **Save** (give it any name), then **Add to chart**.

You now see:

- Two thick lines on the price chart, teal on top and red below: the entry channel. A price **above the
  top line** buys, and a price **below the bottom line** sells short. These are the Donchian channels.
- Two thin lines: the exit channel. A position closes when price breaks the thin line on the other side.
- An orange line while a trade is open: where that trade will exit.
- Arrows for every buy and sell.
- A pane below the chart with **N**, the average daily range in dollars. N sets the size of every trade.

## Read the Strategy Tester

Open the **Strategy Tester** tab at the bottom. The **Overview** shows:

| Number | What it means |
|---|---|
| Net profit | What the strategy made or lost, in dollars and percent of the starting $10,000,000 |
| Total closed trades | Each Turtle unit counts as one trade, so a full position of 4 units is 4 trades |
| Percent profitable | The share of those trades that made money. Trend following often wins only 20 to 35% |
| Max equity drawdown | The largest fall from a high point of the account. This is the pain number |
| Profit factor | Money won divided by money lost. Above 1 made money overall |

The **List of trades** shows every entry and exit. On SPY with the default settings, compare your numbers
with `spy-check.md`: about 388 closed trades, about +4.7% net profit, and about 11% max drawdown.

## Change the settings

Click the gear next to the strategy's name on the chart.

- **Inputs**: pick System 1 (20-day breakouts) or System 2 (55-day breakouts), the risk per unit, the filter,
  the drawdown rule, and the dates. The default risk is 0.1% per N, the size that held up in the test.
  The original Turtle rule is 1%. Try it and look at the max drawdown.
- The default end date is 6 November 2026, to match the test. Set it to a future date to run up to today.
- **Properties**: the starting capital, the commission (0.05% per side, as in the test), slippage, and
  margin. Margin is 0 (no limit), as in the backtest. For a cash account, set it to 100.

## Why TradingView won't match the video exactly

The video's main test is a **portfolio**: both systems on 24 ETFs at the same time. TradingView tests **one
symbol**. So the numbers will differ, and that's expected:

- **One market, not 24.** In the portfolio, wins in one market pay for losses in another, and the Turtle
  limits (at most 6 units in markets that move together, 12 in one direction) matter. On one symbol they never apply.
- **No interest on cash.** The backtest pays the Treasury bill rate on unused cash, like a futures account.
  TradingView doesn't. On SPY at 0.1%, interest is the difference between +0.24% and +1.56% a year.
- **Different data.** TradingView's prices and dividend adjustment differ a little from Yahoo Finance's.
- **Small mechanics.** Whole shares, one add per bar, and the order of fills inside a single bar.
- **Counting.** TradingView counts each unit as a trade. The backtest counts a whole position as one trade.

If your SPY numbers are far from `spy-check.md`, check the timeframe (daily), the dividend adjustment,
and the dates first. TradingView's free plan loads a limited number of past bars; if the chart doesn't
reach back to 2007, the test starts later and the numbers change.

## A correction

The video's System 1 numbers came from a first version of the filter that skipped a breakout for one day
only. The original rule, used in this code, skips the whole breakout. System 2, the video's main result, has
no filter and is the same in both. `python/README.md` shows how to reproduce either version.

## The rules, in short

- **N**: the 20-day average daily range (average true range).
- **Unit**: (risk % of the account) divided by N, so a move of one N changes the account by that %.
- **Entry**: System 1 buys a 20-day high and sells short a 20-day low, but skips a breakout after a winning
  one (a 55-day breakout is always taken). System 2 does the same with 55 days and no filter.
- **Adds**: one more unit each half N in your favor, up to 4 units.
- **Stop**: 2 N behind the last unit.
- **Exit**: System 1 at a 10-day breakout the other way, System 2 at a 20-day breakout the other way.

Source: Curtis Faith and others, *The Original Turtle Trading Rules* (2003).
