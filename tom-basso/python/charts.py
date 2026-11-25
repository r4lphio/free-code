"""Render the result charts as 1600 x 900 PNGs in the Quant Alchemy dark copper style.

Usage: python charts.py <results_dir>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

SURFACE = "#0f0f1a"
COPPER = "#d4924f"  # the Basso rules
GRAY = "#5a5650"  # context
TEXT, TEXT_2, GRID = "#f0ece4", "#9a9490", "#26243a"
SOURCE = "Data: Yahoo Finance daily, 24 ETFs, Mar 2007 to Nov 2026. 5 bps per side cost, T-bill interest on cash. Quant Alchemy."

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": TEXT, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False, "font.size": 15, "axes.titlesize": 17,
})
pct = FuncFormatter(lambda v, _: f"{v:.0%}")


def frame(title: str, subtitle: str, nrows: int = 1, left: float = 0.08) -> tuple[plt.Figure, list[plt.Axes]]:
    fig, axes = plt.subplots(nrows, 1, figsize=(16, 9), dpi=100, sharex=True, squeeze=False)
    fig.subplots_adjust(left=left, right=0.95, top=0.80, bottom=0.14, hspace=0.35)
    fig.text(0.08, 0.92, title, fontsize=30, fontweight="bold", color=TEXT)
    fig.text(0.08, 0.865, subtitle, fontsize=17, color=TEXT_2)
    fig.text(0.08, 0.025, SOURCE, fontsize=12, color=TEXT_2)
    return fig, list(axes[:, 0])


def coin_flip(res: Path) -> None:
    taxed = pd.read_csv(res / "random_entry.csv").cagr
    free = pd.read_csv(res / "random_entry_zero_cost.csv").cagr
    cc = pd.read_csv(res / "cost_check.csv")
    k = {(r.system, r.cost_bps): r.cagr for r in cc.itertuples()}
    fig, (top, bot) = frame("A coin flip beat a Market Wizard's entry rule",
                            "Random long or short entries with his sizing and a 3 x ATR trailing stop. Copper line: his 21-day Keltner system.", 2)
    bins = [x / 1000 for x in range(-80, 81, 4)]
    for ax, data, basso, label in ((bot, taxed, k[("Keltner 21", 5.0)], f"After trading costs: {len(taxed)} coin-flip runs, {(taxed > 0).mean():.0%} made money"),
                                   (top, free, k[("Keltner 21", 0.0)], f"Before trading costs: {len(free)} coin-flip runs, {(free > 0).mean():.0%} made money")):
        ax.hist(data, bins=bins, color=GRAY, edgecolor=SURFACE, linewidth=2)
        ax.axvline(basso, color=COPPER, linewidth=3)
        ax.axvline(data.median(), color=TEXT_2, linewidth=1.5, linestyle="--")
        # Put each label on the outer side of its line so the two never collide.
        basso_left = basso < data.median()
        y = ax.get_ylim()[1] * 0.92
        ax.text(basso, y, f"  Basso entry {basso:+.1%}  ", color=COPPER, fontsize=16, va="top", ha="right" if basso_left else "left")
        ax.text(data.median(), y, f"  coin-flip median {data.median():+.1%}  ", color=TEXT, fontsize=14, va="top", ha="left" if basso_left else "right")
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.set_title(label, loc="left", color=TEXT, pad=10)
        ax.set_ylabel("runs")
        ax.grid(axis="x", visible=False)
    bot.xaxis.set_major_formatter(pct)
    bot.set_xlabel("annual return (CAGR)")
    fig.savefig(res / "chart_coin_flip.png")


def big_winners(res: Path) -> None:
    bw = pd.read_csv(res / "big_winners.csv")
    row = bw[bw.top_pct == 0.01].iloc[0]
    n_all = len(pd.read_csv(res / "trades_case4.csv"))
    fig, (ax,) = frame("30 trades out of 2,992 paid for everything",
                       "Total profit and loss by group, Basso trend rules with his full sizing.", left=0.22)
    labels = [f"Best 30 trades (1%)", f"Other {n_all - int(row.n_trades):,} trades"]
    vals = [row.pnl_top / 1e6, row.pnl_rest / 1e6]
    bars = ax.barh(labels, vals, color=[COPPER, GRAY], height=0.5)
    for b, v in zip(bars, vals):
        ax.text(v + (0.4 if v > 0 else -0.4), b.get_y() + b.get_height() / 2, f"{'+' if v > 0 else '-'}${abs(v):.1f}M",
                va="center", ha="left" if v > 0 else "right", fontsize=22, fontweight="bold", color=TEXT)
    ax.axvline(0, color=TEXT_2, linewidth=1)
    ax.set_xlim(-20, 17)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{'-' if v < 0 else ''}${abs(v):.0f}M"))
    ax.set_xlabel("P&L on a $10M account, 2007 to 2026")
    ax.tick_params(axis="y", labelsize=18, colors=TEXT)
    fig.savefig(res / "chart_big_winners.png")


def sizing(res: Path) -> None:
    t = pd.read_csv(res / "sizing_study.csv", index_col=0)
    rows = [("Risk only (layers 1 and 2*)", "1. Risk only", COPPER), ("+ ongoing trims", "3. + ongoing trims", COPPER),
            ("+ portfolio caps", "4. + portfolio caps", COPPER), ("SPY buy and hold", "SPY buy and hold", GRAY)]
    fig, (ax,) = frame("Sizing trimmed the worst drop. It did not create a profit.",
                       "Maximum drawdown with the same trades as each of Basso's sizing layers is added.", left=0.25)
    dd = [t.loc[k, "max_dd"] for _, k, _ in rows]
    bars = ax.barh([r[0] for r in rows], dd, color=[r[2] for r in rows], height=0.55)
    for b, (_, k, _) in zip(bars, rows):
        ax.text(b.get_width() + 0.006, b.get_y() + b.get_height() / 2,
                f"-{t.loc[k, 'max_dd']:.0%} worst drop, {abs(t.loc[k, 'cagr']) if abs(t.loc[k, 'cagr']) < 0.0005 else t.loc[k, 'cagr']:+.1%} a year", va="center", fontsize=17, color=TEXT)
    ax.set_xlim(0, 0.8)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(pct)
    ax.tick_params(axis="y", labelsize=17, colors=TEXT)
    fig.text(0.08, 0.005 + 0.06, "* With stops 4 ATR away, the 0.5% risk limit always binds before the 0.3% volatility limit, so layer 2 changes nothing.",
             fontsize=12, color=TEXT_2)
    fig.savefig(res / "chart_sizing.png")


def equity(res: Path) -> None:
    c = pd.read_parquet(res / "sizing_curves.parquet")
    fig, (ax,) = frame("Flat for 19 years, except in four big trend years",
                       "Growth of $1. Basso rules with full sizing against SPY buy and hold. Log scale.")
    for col, color, name in (("SPY buy and hold", GRAY, "SPY buy and hold"), ("4. + portfolio caps", COPPER, "Basso rules")):
        s = c[col].dropna()
        ax.plot(s.index, s, color=color, linewidth=2.5, label=name)
        ax.text(s.index[-1], s.iloc[-1], f"  {name} ${s.iloc[-1]:.2f}", color=TEXT, fontsize=15, va="center")
    for year in (2008, 2014, 2020, 2022):
        ax.axvspan(pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31"), color=COPPER, alpha=0.08, linewidth=0)
    ax.text(pd.Timestamp("2008-07-01"), 0.4, "2008", color=TEXT_2, ha="center")
    ax.text(pd.Timestamp("2014-07-01"), 0.4, "2014", color=TEXT_2, ha="center")
    ax.text(pd.Timestamp("2020-07-01"), 0.4, "2020", color=TEXT_2, ha="center")
    ax.text(pd.Timestamp("2022-07-01"), 0.4, "2022", color=TEXT_2, ha="center")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    ax.set_ylim(0.35, 12)
    ax.legend(loc="upper left", frameon=False, labelcolor=TEXT)
    ax.set_xlim(c.index[0], c.index[-1] + pd.Timedelta(days=1700))
    ax.set_xticks([pd.Timestamp(f"{y}-01-01") for y in range(2008, 2027, 2)], [str(y) for y in range(2008, 2027, 2)])
    fig.savefig(res / "chart_equity.png")


def lookback(res: Path) -> None:
    s = pd.read_csv(res / "lookback_sweep.csv")
    fig, (ax,) = frame("His 21-day lookback was one of the weakest here",
                       "Annual return by Keltner lookback, all else the same. He picked 21 because a month has 21 trading days.")
    colors = [COPPER if n == 21 else GRAY for n in s.lookback]
    bars = ax.bar([f"{n} days" for n in s.lookback], s.cagr, color=colors, width=0.6)
    for b, r in zip(bars, s.itertuples()):
        ax.text(b.get_x() + b.get_width() / 2, r.cagr + 0.001, f"{r.cagr:+.1%}\n-{r.max_dd:.0%} worst drop",
                ha="center", va="bottom", fontsize=14, color=TEXT)
    ax.set_ylim(0, 0.055)
    ax.yaxis.set_major_formatter(pct)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("annual return (CAGR)")
    ax.tick_params(axis="x", labelsize=16, colors=TEXT)
    fig.savefig(res / "chart_lookback.png")


if __name__ == "__main__":
    out = Path(sys.argv[1])
    for draw in (coin_flip, big_winners, sizing, equity, lookback):
        draw(out)
    print("charts written to", out)
