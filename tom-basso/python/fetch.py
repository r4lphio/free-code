"""Download daily OHLC (dividend-adjusted) for the test universe into data/prices.parquet.

Usage: python fetch.py <data_dir>
"""

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

# A diversified ETF basket that stands in for Basso's futures book:
# stock indexes, bonds, commodities, currencies, real estate, and a few sectors.
UNIVERSE = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ",
    "TLT", "IEF", "LQD", "TIP",
    "GLD", "SLV", "USO", "DBA", "DBC",
    "UUP", "FXE", "FXY", "FXA",
    "VNQ", "XLE", "XLU", "XLK", "XLV",
]
START = "2007-03-01"  # UUP and DBA start in early 2007
END = "2026-11-07"


def main(data_dir: Path) -> None:
    raw = yf.download(UNIVERSE, start=START, end=END, auto_adjust=True, progress=False, group_by="column")
    fields = ["Open", "High", "Low", "Close"]
    frames = {f: raw[f][UNIVERSE] for f in fields}
    panel = pd.concat(frames, axis=1)
    panel = panel.dropna(how="all")
    out = data_dir / "prices.parquet"
    panel.to_parquet(out)
    first = panel["Close"].apply(lambda s: s.first_valid_index())
    print(f"rows={len(panel)} from {panel.index[0].date()} to {panel.index[-1].date()}")
    print("latest first-valid date:", first.max().date(), first.idxmax())
    print("missing closes per symbol:", panel["Close"].isna().sum().to_dict())


def fetch_rates(data_dir: Path) -> None:
    """13-week T-bill yield (annual percent), used as the interest rate on cash."""
    irx = yf.download("^IRX", start=START, end=END, auto_adjust=False, progress=False)["Close"].squeeze()
    irx.rename("irx").to_frame().to_parquet(data_dir / "tbill.parquet")
    print("tbill rows", len(irx), "mean %", round(float(irx.mean()), 2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
    fetch_rates(Path(sys.argv[1]))
