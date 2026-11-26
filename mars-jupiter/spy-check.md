# SPY cross-check: Python against TradingView

Use these dates and numbers to check the Pine indicator in TradingView. They come from `python/spy_check.py` and
`python/data/aspects.csv`, run on Yahoo Finance data to 18 November 2026:

```
python spy_check.py SPY
```

## 1. The marks (check the indicator)

In TradingView: SPY, daily (`1D`), dividend adjustment off. Each aspect should be marked on this bar:

| Exact time (UTC) | Aspect | SPY bar marked | Test trade |
|---|---|---|---|
| 2024-01-12 10:41 | trine | 2024-01-12 | long |
| 2024-02-27 08:29 | square | 2024-02-27 | short |
| 2024-04-19 15:28 | sextile | 2024-04-19 | long |
| 2024-08-14 15:21 | conjunction | 2024-08-14 | long |
| 2025-06-22 10:31 | sextile | 2025-06-23 (Monday) | long |
| 2025-09-05 02:58 | square | 2025-09-05 | short |
| 2025-10-28 06:19 | trine | 2025-10-28 | long |
| 2026-01-10 14:25 | opposition | 2026-01-12 (Monday) | short |
| 2026-03-22 00:01 | trine | 2026-03-23 (Monday) | long |
| 2026-05-05 02:08 | square | 2026-05-05 | short |
| 2026-06-28 04:50 | sextile | 2026-06-29 (Monday) | long |
| 2026-11-16 06:23 | conjunction | 2026-11-16 | long |

The next ones, drawn as dashed lines ahead of price: sextile 2027-09-20, square 2027-11-16, trine 2027-12-31,
opposition 2028-03-10.

Astronomy sites list the 2024 conjunction at about 16:50 UTC on 14 August, and the 2026 one on 15 or 16 November.
They time a conjunction by right ascension or closest approach; astrologers, and this indicator, use ecliptic
longitude. The date is the same; the time differs by hours.

## 2. The test trade on SPY

Hold 10 bars, 5 basis points each way, January 1993 to 18 November 2026:

| | Python |
|---|---|
| Closed trades | 142 |
| Average trade, after cost | -0.01% |
| Winning trades | 49.3% |

- If your chart has bars after 1 December 2026, the trade from the 16 November conjunction has closed too, so the
  count is 143 and the other two numbers move a little.
- TradingView's SPY prices can differ from Yahoo's by a few cents, so expect small differences in the average.
- To match the Python run exactly, run `python spy_check.py SPY --until <the day after your chart's last bar>`.

## 3. SPY in the full test

From the 50-market run, SPY's average trade after costs was -0.01%. The fake calendars (the same dates, slid by a
random number of days) averaged -0.04%. SPY beat 57% of them: no edge.
