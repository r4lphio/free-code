"""Download daily OHLC prices (dividend adjusted) and the 13-week T-bill rate from Yahoo Finance.

Usage: python fetch_data.py data [--end 2026-11-07] [--symbols SPY QQQ ...]
Writes data/prices.parquet and data/tbill.parquet. The defaults are the episode's 24 ETFs and dates.
"""

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

# Stock indexes, bonds, commodities, currencies, real estate and four sectors.
UNIVERSE = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ",
    "TLT", "IEF", "LQD", "TIP",
    "GLD", "SLV", "USO", "DBA", "DBC",
    "UUP", "FXE", "FXY", "FXA",
    "VNQ", "XLE", "XLU", "XLK", "XLV",
]
START = "2007-03-01"  # UUP and DBA start in early 2007


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir", type=Path)
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default="2026-11-07", help="first day NOT included (Yahoo's convention)")
    ap.add_argument("--symbols", nargs="+", default=UNIVERSE)
    a = ap.parse_args()
    a.data_dir.mkdir(parents=True, exist_ok=True)

    raw = yf.download(a.symbols, start=a.start, end=a.end, auto_adjust=True, progress=False, group_by="column")
    panel = pd.concat({f: raw[f][a.symbols] for f in ("Open", "High", "Low", "Close")}, axis=1).dropna(how="all")
    panel.to_parquet(a.data_dir / "prices.parquet")
    print(f"prices: {len(panel)} days, {panel.index[0].date()} to {panel.index[-1].date()}, {len(a.symbols)} symbols")

    irx = yf.download("^IRX", start=a.start, end=a.end, auto_adjust=False, progress=False)["Close"].squeeze()
    irx.rename("irx").to_frame().to_parquet(a.data_dir / "tbill.parquet")
    print(f"T-bill rate: {len(irx)} days")


if __name__ == "__main__":
    main()
