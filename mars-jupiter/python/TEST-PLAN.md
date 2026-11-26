# Mars-Jupiter test plan

Written on 19 November 2026, after the prices and aspect dates were computed (about 16:20 MT) and before
the first test run. The results must follow this plan. Any change after the first run is listed at the end.

## Data

- Markets: the shared 50-instrument universe (`data/universe-50.csv`, rule in `data/universe-50-rule.md`):
  30 equity ETFs, 8 bond ETFs, 7 commodity ETFs, 5 coins.
- Prices: Yahoo Finance daily OHLC, split adjusted, not dividend adjusted, each market's full history
  (SPY from January 1993), to 18 November 2026. The rule's flat-day filter applies.
- Aspects: geocentric, apparent ecliptic longitude of date (tropical), NASA JPL DE440s through Skyfield.
  Five major aspects: conjunction 0, sextile 60, square 90, trine 120, opposition 180 degrees.
  Every exact crossing counts, including the second and third hits of a retrograde pass.

## Event day

The event day for a market is its first trading day on or after the UTC date of the exact aspect. Aspect
dates are known decades ahead, so trading on the event day uses no future data.

## Primary test (one number decides the headline)

- **The aspect trade.** On each event day, enter at the open. Long on conjunction, sextile and trine
  (the "easy" aspects), short on square and opposition (the "hard" aspects). Exit at the open 10 trading
  days later. One position per market at a time: an event during an open trade is skipped.
- **Costs:** 5 basis points each way (as in the Gann episode). Results before and after costs.
- **Measure:** the average trade return, after costs, averaged over markets (each market counts once),
  for all 50 markets and for each asset class. Also an equal-weight portfolio of all markets (flat days
  earn zero), as yearly return.
- **Baseline:** 1,000 copies of the aspect calendar, each shifted in time by one random number of days
  (30 days to 45 years, wrapped around the 1990 to 2036 span). A shift keeps the count, the spacing and the
  order of the aspects; it only breaks their link to the planets. The aspect trade is real only if it beats
  at least 95% of the shifted calendars.

## Secondary tests (descriptive; many comparisons, so some will pass by luck)

1. **Direction by aspect.** Average return from the event-day open to 5, 10 and 20 trading days later,
   per aspect type, long only, every event counted. Against the same shifted calendars.
2. **Volatility in orb.** Each day's absolute close-to-close return divided by the market's standard
   deviation over the previous 60 days. Days "in orb" are within 3 degrees of an exact aspect (separation
   at 00:00 UTC). In-orb average minus out-of-orb average, against the separation series shifted by the
   same random offsets.
3. **Turning points.** Share of events with a 10-day pivot (highest high or lowest low with 10 bars on each
   side) within 3 trading days of the event day. Against the shifted calendars. This uses future bars by
   design: it asks whether a turn happened near the date, not whether it could be traded.

## Robustness

- Hold 5 and 20 days. Costs 0 and 5 basis points. Only data from 1 March 2007 (the Gann episode's window).
- Per market: how many of the 50 beat 95% of their shifted calendars (luck alone gives about 2 or 3).

## Checks before any number is used

1. Aspect dates from a second, independent ephemeris (Swiss Ephemeris, Moshier mode, no JPL files) match.
2. Conjunction dates match published astronomy tables.
3. A second, plain implementation of the SPY trades matches trade for trade.
4. Cutting the data at random dates changes no earlier trade (no look-ahead).
5. A shift of zero days reproduces the real result exactly.

## Changes after the first run

Nothing in the plan above changed. Three things were added after the first run, and the results label them:

1. **Sextile split** (`scripts/posthoc.py`). The one standout of the secondary tests (stock ETFs after a
   sextile) is tested again in each half of the data and without 2008 and 2009.
2. **Two named claims** (`scripts/posthoc.py`). The source brief (`RESEARCH.md`) arrived after the first run.
   It names claims the plan did not test: David Williams, a low at the conjunction and the opposition; Matlock,
   an above-average rise in the 30 days before them. Both are tested on all 50 markets against the same shifts.
3. **Benchmarks** (`scripts/benchmarks.py`): buy and hold, and the share of days in a trade.
