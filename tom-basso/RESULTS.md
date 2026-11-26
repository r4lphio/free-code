# Testing Tom Basso's rules: results

These tests check four claims that Tom Basso makes in his interviews, on 24 ETFs from March 2007 to November 2026. They are research results, not trading advice. Past results do not predict future results.

## Setup

- **Universe.** 24 ETFs stand in for his futures book: stock indexes (SPY, QQQ, IWM, EFA, EEM, EWJ), bonds (TLT, IEF, LQD, TIP), commodities (GLD, SLV, USO, DBA, DBC), currencies (UUP, FXE, FXY, FXA), real estate (VNQ) and 4 sectors. The prices are Yahoo daily OHLC with dividend adjustment.
- **Entry and exit.** A stop order enters at a 21-day EMA ± 2.0 × 21-day ATR (Keltner). The exit and reverse is at the opposite band, which trails each day. These are his stated settings ([RM21 47:43](https://youtu.be/7v6DQ4qyYIo?t=2863)). He also uses Donchian and Bollinger bands, which are not tested here.
- **Sizing.** These are his 2022 settings ([TL22 38:16](https://youtu.be/SMWMraeRDXs?t=2296)):
  - 0.5% initial risk and 0.3% initial volatility per position.
  - Ongoing limits of 1% risk and 0.4% volatility. Trims are decided at the close and filled at the next open.
  - Caps of 16% total risk and 6% total volatility, with correlation assumed to be 1.0.
  - Fractional units are allowed. The account starts at $10M.
- **Costs and cash.** Trading costs 5 bps per side on traded value. Cash earns or pays the 13-week T-bill rate, as in a futures account. Short positions pay no borrow fee.

## Results

**1. Sizing study (his own 2022 experiment, rerun).** Each row uses the same 2,992 trades.

| Sizing | CAGR | Max drawdown | Sortino |
|---|---|---|---|
| Risk only | 0.0% | 44% | 0.13 |
| + initial volatility | same as above* | | |
| + ongoing trims | +0.4% | 40% | 0.15 |
| + portfolio caps | +0.4% | 39% | 0.15 |
| SPY buy and hold | +10.7% | 55% | 0.87 |
| Equal-weight ETFs, buy and hold | +6.2% | 35% | 0.83 |

\* With the stop 4 ATR away, the 0.5% risk limit always binds before the 0.3% volatility limit, so this layer never changes a position.

Sizing cut the worst drawdown by 5 points, from 44% to 39%. It did not turn a flat system into a profitable one. His own study showed a larger effect, from 42% to 30% ([TL22 40:31](https://youtu.be/SMWMraeRDXs?t=2431)). The win rate was 34.7%, which matches his lifetime figure of about 33% ([TL22 13:28](https://youtu.be/SMWMraeRDXs?t=808)). The system made money in 2008, 2014, 2020, 2022 and 2026 and lost in most other years. Short positions in stock ETFs during the bull market lost more than everything else earned. Without the T-bill interest, it lost 0.6% a year.

**2. Random entry (coin flip, his sizing, 3 × ATR trailing stop).**

| | Coin-flip median | Coin-flip runs that made money | His 21-day Keltner system |
|---|---|---|---|
| Before trading costs (100 runs) | +3.1% | 94% | +2.6% |
| After 5 bps per side (500 runs) | -1.8% | 14% | +0.4% |

Before trading costs, his claim holds: random entries with good exits and sizing make money ([CWT16 49:08](https://youtu.be/tlzOsbpIbgg?t=2948)). The coin flip even beat his entry rule. Random entry trades about 1.8 times as often (5,258 against 2,992 trades), so costs reverse the result. After costs, his system beats 89% of the coin-flip runs.

**3. Big winners.** The best 30 trades (1% of 2,992) made $11.6M on a $10M account. The other 2,962 lost $14.1M. The best 5% (150 trades) made $32.4M, and the rest lost $34.9M. This strongly supports his claim that a few trades pay for everything ([CWT16 31:12](https://youtu.be/tlzOsbpIbgg?t=1872)). Skipping even a few signals would have made the system worse.

**4. Lookback sweep (his "don't optimize" claim).**

| Lookback (days) | 9 | 15 | 21 | 30 | 40 | 50 |
|---|---|---|---|---|---|---|
| CAGR | +0.1% | +1.0% | +0.4% | +1.8% | +3.4% | +4.0% |
| Max drawdown | 45% | 37% | 39% | 34% | 32% | 31% |

The results rise steadily with the lookback. There is no flat plateau around 21. His 21 days was the second-weakest choice on this data. Do not now pick 50 as the "right" number, because that would be the optimization he warns about. The safe conclusion is that slower trend systems paid better on ETFs from 2007 to 2026.

## Limits

- ETFs are not futures. These ETFs have higher costs, contango drag (USO, DBC), and correlation between stock indexes that is near 1.
- The test uses one indicator (Keltner), not his three-band combination. It also ignores his other strategies, such as counter-trend models, option spreads and the stock hedge, which he says fill the drawdowns.
- 2007 to 2026 was a hard period for trend following. His live returns cannot be checked from these tests.
- The 5 bps cost is an estimate. Liquid ETFs like SPY cost less, and thin ones like DBA and FXA cost more, especially for stop orders that fill on a gap.

## Run it

From the `python/` folder. `python/README.md` has the setup.

```bash
mkdir -p data results
python fetch.py data                       # prices and T-bill rates into data/
python sizing_study.py data results        # test 1
python more_tests.py data results 500      # tests 2 to 4
python cost_check.py data results          # the before-costs runs for test 2
python charts.py results                   # the charts from the video
```

The full run takes about 1 minute on 24 cores.
