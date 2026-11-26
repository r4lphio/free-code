"""Download daily OHLC prices from Yahoo Finance, split adjusted but NOT dividend adjusted.

Square-of-nine levels depend on the price number itself, so the test uses prices as a chart shows them
(TradingView's default), not total-return prices. Splits are adjusted, dividends are not.

The symbols come from <data_dir>/universe.csv (columns symbol, asset_class, yahoo; see universe-50-rule.md).
ETFs start on 1 March 2007 or at their first trading day if later; crypto starts at Yahoo's first day.
Data rule: a market starts in the year after its last calendar year with 5% or more days where high = low
(a thinly traded young fund, with stale and bad prints). On 19 November 2026 that moved CPER to 2018,
IEFA to 2013, IUSB to 2015 and PDBC to 2016.

Usage: python fetch_data.py <data_dir> [--end 2026-11-18]
Writes <data_dir>/prices.parquet (columns: field, symbol).
"""

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

ETF_START = "2007-03-01"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", type=Path)
    ap.add_argument("--end", default="2026-11-18", help="first day NOT included (Yahoo's convention)")
    a = ap.parse_args()
    uni = pd.read_csv(a.data_dir / "universe.csv")
    frames = {}
    for sym, cls, yahoo in zip(uni.symbol, uni.asset_class, uni.yahoo):
        start = "2010-01-01" if cls == "crypto" else ETF_START
        raw = yf.download(yahoo, start=start, end=a.end, auto_adjust=False, progress=False)
        raw.columns = raw.columns.get_level_values(0)
        df = raw[["Open", "High", "Low", "Close"]].dropna()
        df = df[(df > 0).all(axis=1)]
        flat = (df.High == df.Low).groupby(df.index.year).mean()
        if (flat >= 0.05).any():
            df = df[df.index.year > flat[flat >= 0.05].index.max()]
        frames[sym] = df
        print(f"{sym}: {len(frames[sym])} days, {frames[sym].index[0].date()} to {frames[sym].index[-1].date()}")
    panel = pd.concat(frames, axis=1).swaplevel(axis=1).sort_index(axis=1)
    panel.to_parquet(a.data_dir / "prices.parquet")


if __name__ == "__main__":
    main()
