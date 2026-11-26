"""Download daily OHLC prices from Yahoo Finance for the 50-instrument universe, full available history.

Prices are split adjusted, not dividend adjusted (the price a chart shows), as in universe-50-rule.md.
Every market starts at Yahoo's first day (its full history). One data filter applies: a market starts in the
year after its last calendar year with 5% or more days where high = low (stale prints of a thin young fund).

Usage: python fetch_data.py <data_dir> [--end 2026-11-19]
Reads <data_dir>/universe-50.csv. Writes <data_dir>/prices.parquet (columns: field, symbol).
"""

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", type=Path)
    ap.add_argument("--end", default="2026-11-19", help="first day NOT included (Yahoo's convention)")
    a = ap.parse_args()
    uni = pd.read_csv(a.data_dir / "universe-50.csv")
    frames = {}
    for sym, yahoo in zip(uni.symbol, uni.yahoo):
        raw = yf.download(yahoo, start="1990-01-01", end=a.end, auto_adjust=False, progress=False)
        raw.columns = raw.columns.get_level_values(0)
        df = raw[["Open", "High", "Low", "Close"]].dropna()
        df = df[(df > 0).all(axis=1)]
        flat = (df.High == df.Low).groupby(df.index.year).mean()
        if (flat >= 0.05).any():
            df = df[df.index.year > flat[flat >= 0.05].index.max()]
        frames[sym] = df
        print(f"{sym}: {len(df)} days, {df.index[0].date()} to {df.index[-1].date()}")
    panel = pd.concat(frames, axis=1).swaplevel(axis=1).sort_index(axis=1)
    panel.to_parquet(a.data_dir / "prices.parquet")


if __name__ == "__main__":
    main()
