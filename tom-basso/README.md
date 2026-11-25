# Free code: Tom Basso's trend rules

From r4lph's video "Coin Flips Beat Tom Basso's Entry Until Costs Hit". My AI coding agent read 9 long
interviews with Tom Basso, rebuilt his trend rules and his position sizing, tested four of his claims, and
wrote this code. You can use it, change it, and share it.

This is an experiment in what AI agents can build and verify, not trading advice. Past results do not predict
future results.

## What's in this folder

| File | For |
|---|---|
| `RESULTS.md` | The setup, the four tests, the results tables and the limits. |
| `python/` | The full backtest. It has its own README. |

This episode has no TradingView script. Basso's sizing works across the whole portfolio: it caps the total
risk of all open positions together. A TradingView strategy tests one symbol, so it cannot show the part of
the system that did the work.

## The result, in short

24 ETFs, daily prices from March 2007 to November 2026, a $10,000,000 account, 5 bps per side costs, and
T-bill interest on cash.

- **Coin flip, before costs.** Random entries with his sizing and a 3 x ATR trailing stop made a median of
  +3.1% a year. 94% of 100 runs made money. His 21-day Keltner system made +2.6%.
- **Coin flip, after costs.** Random entries trade about 1.8 times as often, so costs reverse the result.
  Only 14% of 500 runs made money, with a median of -1.8% a year. His system made +0.4% a year and beat 89%
  of the runs. SPY, bought and held, made +10.7% a year.
- **Big winners.** The best 30 of 2,992 trades made $11.6M. The other 2,962 lost $14.1M.
- **Win rate.** 34.7%. Basso says about a third.

`RESULTS.md` has every number.

## The rules, in short

- **Entry**: a stop order at the 21-day EMA plus or minus 2 x the 21-day ATR (a Keltner channel).
- **Exit**: exit and reverse at the opposite band, which trails each day.
- **Sizing** (his 2022 settings): 0.5% initial risk and 0.3% initial volatility per position. Trim a
  position back when it passes 1% risk or 0.4% volatility. Cap total risk at 16% and total volatility at 6%,
  as if every market moved together.
- **Coin flip**: the same sizing, a random long or short entry, and a 3 x ATR trailing stop.

The settings come from Basso's own talks. `RESULTS.md` links to the time in each video.
