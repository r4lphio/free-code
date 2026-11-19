"""Download daily OHLC prices from Yahoo Finance, split adjusted but NOT dividend adjusted.

Square-of-nine levels depend on the price number itself, so the test uses prices as a chart shows them
(TradingView's default), not total-return prices. Splits are adjusted, dividends are not.

Usage: python fetch_data.py <data_dir> [--end 2026-11-18]
Writes <data_dir>/prices.parquet (columns: field, symbol).
"""

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

ETFS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ",
    "TLT", "IEF", "LQD", "TIP",
    "GLD", "SLV", "USO", "DBA", "DBC",
    "UUP", "FXE", "FXY", "FXA",
    "VNQ", "XLE", "XLU", "XLK", "XLV",
]
EXTRA = ["BTC-USD"]  # Bitcoin, from 2014. (Yahoo's S&P 500 index has no real opens before 2014, so it is left out.)
START = {"BTC-USD": "2014-09-17"}
ETF_START = "2007-03-01"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", type=Path)
    ap.add_argument("--end", default="2026-11-18", help="first day NOT included (Yahoo's convention)")
    a = ap.parse_args()
    a.data_dir.mkdir(parents=True, exist_ok=True)
    frames = {}
    for sym in ETFS + EXTRA:
        raw = yf.download(sym, start=START.get(sym, ETF_START), end=a.end, auto_adjust=False, progress=False)
        raw.columns = raw.columns.get_level_values(0)
        frames[sym] = raw[["Open", "High", "Low", "Close"]].dropna()
        print(f"{sym}: {len(frames[sym])} days, {frames[sym].index[0].date()} to {frames[sym].index[-1].date()}")
    panel = pd.concat(frames, axis=1).swaplevel(axis=1).sort_index(axis=1)
    panel.to_parquet(a.data_dir / "prices.parquet")


if __name__ == "__main__":
    main()
