# Free code: Mars-Jupiter aspects

From r4lph's video "My AI tested Mars-Jupiter aspects on 50 markets". My AI coding agent built this from public
data and public methods, tested it on 50 markets against random dates, and wrote this code. You can use it, change
it, and share it.

This is research and education, not trading advice. In our test, Mars-Jupiter aspects did no better than random
dates, before or after costs.

## What's in this folder

| File | For |
|---|---|
| `mars-jupiter-aspects.pine` | TradingView. Paste it in and see every Mars-Jupiter aspect on any chart. No coding needed. |
| `spy-check.md` | The dates and numbers to expect on SPY, so you can check that it works. |
| `python/` | The full test, for people who run Python. It has its own README. |

## What an aspect is

An aspect is the angle between two planets, seen from Earth along the zodiac (astrologers' term for the band of
sky the planets move through). The indicator marks the five main ones:

| Aspect | Angle | Astrologers call it | Test trade |
|---|---|---|---|
| Conjunction | 0° | a meeting | long |
| Sextile | 60° | easy | long |
| Square | 90° | hard | short |
| Trine | 120° | easy | long |
| Opposition | 180° | hard | short |

Mars laps Jupiter about every 2.2 years and passes every aspect on each lap. When Mars turns retrograde (seems to
move backward), it can cross the same angle two or three times in a few weeks. Each crossing is marked.

## Where the dates come from

The planet positions come from NASA JPL's public DE440s ephemeris (the planet tables NASA uses to fly
spacecraft), computed with the free Skyfield library. A second, independent ephemeris (Swiss Ephemeris) gives the
same 192 aspects from 1990 to 2035, to within 2 minutes. The dates are written into the script, so TradingView
needs no outside data. Nothing in this folder comes from any paid or private tool.

## Put it on a TradingView chart (about 2 minutes)

1. Go to tradingview.com and open a chart. A free account is fine.
2. Type `SPY` to load the symbol, and pick the daily timeframe (`1D`).
3. Leave dividend adjustment **off** (the `ADJ` button at the bottom right is not highlighted).
4. Open the **Pine Editor** tab at the bottom of the screen.
5. Delete the text in the editor. Open `mars-jupiter-aspects.pine` in any text editor, copy all of it, and paste it in.
6. Click **Save** (give it any name), then **Add to chart**.

You now see a shaded bar and a label at every aspect, dashed lines at the next four aspects ahead of price, and a
small table at the top right.

## What you see

- **Copper** marks a conjunction. **Green** marks the easy aspects (sextile, trine). **Red** marks the hard
  ones (square, opposition).
- Each label gives the aspect and its exact time in UTC. An aspect lands on the first bar on or after its date
  (a weekend aspect lands on Monday's bar).
- The table shows the next aspect and, if the test is on, the test trade's results on this chart.

## The test trade

Turn it on or off under "Test trade" in the settings. On the bar of each aspect, it enters at the open: long after
a conjunction, sextile or trine, short after a square or opposition. It exits at the open 10 bars later, and pays
5 basis points (0.05%) each way. One trade at a time. The table shows the closed trades, the average trade after
cost, and the share of winners. Use it on daily charts; on other timeframes "10 bars" means something else.

On SPY daily, it should show about 142 closed trades, an average of about 0.0% and about 49% winners (see
`spy-check.md`).

## Change the settings

Click the gear next to the indicator's name on the chart.

- **Aspects:** turn each of the five on or off.
- **Display:** labels, shading, how many upcoming aspects to draw, and the colors.
- **Test trade:** on or off, how many bars to hold, and the cost each way.

## What the test found

My AI tested the trade above on 50 markets: the 30 largest stock ETFs, the 8 largest bond ETFs, 7 commodity funds
and the 5 largest coins, each with its full price history (SPY from 1993) to November 2026. It compared the real
aspect dates with 1,000 fake calendars: the same dates, all slid by one random number of days.

- Across all 50 markets, the average trade lost 0.36% after costs. The fake calendars averaged about zero. The real
  dates did worse than 84% of them.
- No asset class beat the fake calendars. Crypto did worse than 97% of them.
- Not one of the 50 markets beat 95% of its fake calendars.
- Aspects did not come with more turning points or bigger moves than random dates.
- Stocks rose 2% in the 10 days after a sextile, better than 99% of fake calendars. But it was one of 75 such
  comparisons, it leans on one date (27 October 2008), and in the second half of the data it beat only 88%.
- Picking markets by today's size favors winners a little, because funds that shrank or closed aren't in the list.

## Sources

- NASA JPL ephemeris: Park, R. S., Folkner, W. M., Williams, J. G., and Boggs, D. H. (2021), "The JPL Planetary
  and Lunar Ephemerides DE440 and DE441", The Astronomical Journal 161:105. https://ssd.jpl.nasa.gov/doc/de440_de441.html
- Skyfield, by Brandon Rhodes: https://rhodesmill.org/skyfield/
- Swiss Ephemeris (the cross-check), Astrodienst: https://www.astro.com/swisseph/
- The aspects and their angles: "Astrological aspect", Wikipedia. https://en.wikipedia.org/wiki/Astrological_aspect
- The claims tested: Raymond Merriman's reversal dates (MMA market reports, 2024 and 2025); David Williams and
  Matlock, as reported by Graham Bates, "Financial Astrology in the 20th Century", The Urania Trust (2012).
  https://www.uraniatrust.org/astrology/financial-astrology
- Conjunction dates used as a check: EarthSky (2018, 2020, 2022, 2024) and Time and Date (2024).

An experiment in what AI agents can build and verify, not trading advice.
