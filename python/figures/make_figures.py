"""
Regenerate every figure in docs/figures/ from the data on disk.

Each figure gets one function, registered in FIGURES at the bottom, so
`make figures` always rebuilds everything reproducibly. Figures are the
project's evidence — if a figure can't be regenerated from data, it doesn't
belong in the docs.

Figure 01 — coverage heatmap (symbol x month, colored by bar count).
The data-quality picture: dark = full coverage, light = thin IEX months,
gray = no data at all (e.g. PLTR before its Sept 2020 IPO). The counts come
from the kdb+ HDB via a q one-liner whose CSV output lands in data/reports/.
"""

import os
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORTS = os.path.join(PROJECT_ROOT, "data", "reports")
FIGDIR = os.path.join(PROJECT_ROOT, "docs", "figures")
Q_BIN = os.path.expanduser("~/.kx/bin/q")

# single-hue sequential ramp, light -> dark (blue steps 100..700)
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MISSING = "#e8e6e1"          # neutral gray: "no data", visually distinct from "few bars"
INK = "#3a3a37"


def run_q(script):
    """Run a q snippet against the HDB and raise if it fails.

    We write the snippet to a temp file and run `q file.q` rather than piping
    stdin: piped q always exits 0, even on errors, but a script file aborts
    with a real non-zero exit code we can check.
    """
    tmp = os.path.join(REPORTS, "_snippet.q")
    with open(tmp, "w") as fh:
        fh.write(script)
    proc = subprocess.run([Q_BIN, tmp, "-q"], capture_output=True,
                          text=True, cwd=PROJECT_ROOT, timeout=300)
    os.remove(tmp)
    if proc.returncode != 0:
        raise RuntimeError(f"q failed:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


def fig01_coverage():
    """Symbol x month heatmap of minute-bar counts."""
    # NOTE: partitioned tables only map-reduce over NATIVE by-columns, so we
    # group by (sym, date) in q and roll days up to months in pandas.
    csv_path = os.path.join(REPORTS, "coverage_by_day.csv")
    # variable is named covg because `cov` is a q KEYWORD (covariance) —
    # assigning to a keyword is an error
    run_q(f"""
\\l data/hdb
covg: select bars: count i by sym, date from bars
(hsym `$"{csv_path}") 0: csv 0: 0! covg
exit 0
""")
    cov = pd.read_csv(csv_path, parse_dates=["date"])
    cov["month"] = cov["date"].dt.to_period("M").astype(str)
    monthly = cov.groupby(["sym", "month"], as_index=False)["bars"].sum()
    grid = monthly.pivot(index="sym", columns="month", values="bars").sort_index()

    cmap = LinearSegmentedColormap.from_list("seqblue", BLUES)
    cmap.set_bad(MISSING)

    fig, ax = plt.subplots(figsize=(11, 13))
    im = ax.imshow(grid.to_numpy(dtype=float), aspect="auto", cmap=cmap,
                   vmin=0, interpolation="nearest")

    ax.set_yticks(np.arange(len(grid.index)))
    ax.set_yticklabels(grid.index, fontsize=4.5, color=INK)
    step = 6                                            # one x label per half year
    ax.set_xticks(np.arange(0, len(grid.columns), step))
    ax.set_xticklabels([str(m)[:7] for m in grid.columns[::step]],
                       fontsize=7, color=INK, rotation=45, ha="right")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title("Minute-bar coverage by symbol and month",
                 fontsize=11, color=INK, loc="left", y=1.022)
    ax.text(0, 1.008, "dark = dense IEX coverage · light = thin months · gray = no data (pre-IPO)",
            transform=ax.transAxes, fontsize=7.5, color="#6f6e69")

    cbar = fig.colorbar(im, ax=ax, shrink=0.35, pad=0.01)
    cbar.ax.tick_params(labelsize=7, length=0, labelcolor=INK)
    cbar.outline.set_visible(False)
    cbar.set_label("bars per month", fontsize=7.5, color=INK)

    fig.tight_layout()
    out = os.path.join(FIGDIR, "01_coverage.png")
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def fig03_rolling_betas():
    """Rolling Carhart betas for four familiar names, 2018 -> now.

    One panel per stock, three lines per panel: market beta (blue), value
    HML (orange), momentum WML (gray). Direct-labeled at the right edge, no
    legend box. The interesting stories: TSLA's wild market beta, XOM's value
    swings, and how 60-day-half-life estimates breathe with regimes.
    """
    csv_path = os.path.join(REPORTS, "betas_sample.csv")
    run_q(f"""
\\l data/hdb
t: select date, sym: value sym, mkt, hml, wml from betas where sym in `AAPL`JPM`XOM`TSLA
(hsym `$"{csv_path}") 0: csv 0: t
exit 0
""")
    t = pd.read_csv(csv_path, parse_dates=["date"])
    series = [("mkt", "market", "#256abf"), ("hml", "value", "#d85a30"),
              ("wml", "momentum", "#5f5e5a")]

    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5), sharex=True)
    for ax, symbol in zip(axes.flat, ["AAPL", "JPM", "XOM", "TSLA"]):
        d = t[t["sym"] == symbol].sort_values("date")
        for colname, label, color in series:
            ax.plot(d["date"], d[colname], color=color, linewidth=1.4)
            ax.annotate(label, (d["date"].iloc[-1], d[colname].iloc[-1]),
                        xytext=(4, 0), textcoords="offset points",
                        fontsize=7.5, color=color, va="center")
        ax.axhline(0, color="#d3d1c7", linewidth=0.8, zorder=0)
        ax.set_title(symbol, fontsize=10, color=INK, loc="left")
        ax.tick_params(labelsize=7.5, length=0, colors=INK)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.margins(x=0.02)
        ax.set_xlim(right=d["date"].iloc[-1] + pd.Timedelta(days=420))

    fig.suptitle("Rolling Carhart betas (250-day window, 60-day half-life)",
                 fontsize=11, color=INK, x=0.065, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(FIGDIR, "03_rolling_betas.png")
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def fig04_residual_autocorr():
    """THE thesis test: autocorrelation of 5-min residual returns by lag.

    Mean reversion = negative autocorrelation at short lags. Raw returns are
    plotted alongside as the control: if stripping the market component
    deepens the negative autocorrelation, the residual carries reversion
    beyond what raw prices show. Lags never cross a day boundary (the q side
    computes them within (sym, date) groups).
    """
    csv_path = os.path.join(REPORTS, "autocorr.csv")
    run_q(f"""
\\l data/hdb
t: select sym, date, ret5, resid from sig
one: {{[t;L]
  u: update lr: L xprev resid, lraw: L xprev ret5 by date, sym from t;
  u: select from u where not null resid, not null lr, not null ret5, not null lraw;
  enlist `lag`acRaw`acResid ! (L; cor[u`ret5; u`lraw]; cor[u`resid; u`lr]) }}
res: raze one[t;] each 1 + til 12
(hsym `$"{csv_path}") 0: csv 0: res
exit 0
""")
    ac = pd.read_csv(csv_path)
    minutes = ac["lag"] * 5

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="#d3d1c7", linewidth=1)
    for col, label, color in [("acRaw", "raw 5-min returns", "#888780"),
                              ("acResid", "market-stripped residuals", "#256abf")]:
        ax.plot(minutes, ac[col], color=color, linewidth=1.8,
                marker="o", markersize=4.5)
        ax.annotate(label, (minutes.iloc[-1], ac[col].iloc[-1]),
                    xytext=(8, 0), textcoords="offset points",
                    fontsize=8.5, color=color, va="center")

    ax.set_xlabel("lag (minutes)", fontsize=9, color=INK)
    ax.set_ylabel("autocorrelation", fontsize=9, color=INK)
    ax.set_title("Do residual returns mean-revert?", fontsize=11,
                 color=INK, loc="left", y=1.05)
    ax.text(0, 1.015, "negative at short lags = reversion. Pooled over all symbols and days, lags within-day only.",
            transform=ax.transAxes, fontsize=8, color="#6f6e69")
    ax.tick_params(labelsize=8, length=0, colors=INK)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(0, minutes.iloc[-1] * 1.28)

    fig.tight_layout()
    out = os.path.join(FIGDIR, "04_residual_autocorr.png")
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def _load_bt(csv_name, slip=0.0):
    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data", "model", csv_name))
    df["date"] = pd.Timestamp("2000-01-01") + pd.to_timedelta(df["qdate"], unit="D")
    df["net"] = df["gross"] - df["fees"] - df["traded"] * slip
    return df


def fig07_equity_curves():
    """The verdict in one picture: cumulative P&L, paper vs market fills.

    Paper fills (decision price, unattainable) show the signal exists;
    market fills (next bar's open) show the bid-ask bounce consuming it.
    The vertical gap between the curves IS the microstructure toll.
    """
    paper = _load_bt("bt_paper_10m.csv")
    market = _load_bt("backtest_daily.csv")
    market_net = _load_bt("backtest_daily.csv", slip=1e-4)

    fig, ax = plt.subplots(figsize=(9.5, 5))
    ax.axhline(0, color="#d3d1c7", linewidth=1)
    for df, label, color in [
            (paper, "paper fills (signal exists)", "#256abf"),
            (market, "market fills, gross (bounce forfeited)", "#888780"),
            (market_net, "market fills, net of 1bp slippage", "#d85a30")]:
        ax.plot(df["date"], df["net"].cumsum() / 1e3, color=color, linewidth=1.6)
        ax.annotate(label, (df["date"].iloc[-1], df["net"].cumsum().iloc[-1] / 1e3),
                    xytext=(8, 0), textcoords="offset points",
                    fontsize=8.5, color=color, va="center")
    ax.set_ylabel("cumulative P&L (thousand USD, on a 1M-USD book)", fontsize=9, color=INK)
    ax.set_title("The execution verdict: same signal, three fill assumptions",
                 fontsize=11, color=INK, loc="left")
    ax.tick_params(labelsize=8, length=0, colors=INK)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(paper["date"].iloc[0], paper["date"].iloc[-1] + pd.Timedelta(days=850))

    fig.tight_layout()
    out = os.path.join(FIGDIR, "07_equity_curves.png")
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


def fig09_cost_sensitivity():
    """Annualized Sharpe vs assumed slippage, per rebalance frequency.

    Shows (a) no configuration survives realistic taker costs, and (b) why:
    slower trading cuts the toll but the signal decays faster than the
    savings accrue. The curves converge to loss everywhere except s=0.
    """
    configs = [("backtest_daily.csv", "10-min rebalance", "#256abf"),
               ("bt_market_30m.csv", "30-min rebalance", "#d85a30"),
               ("bt_market_60m.csv", "60-min rebalance", "#5f5e5a")]
    slips = np.array([0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0])

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="#d3d1c7", linewidth=1)
    for csv_name, label, color in configs:
        df = _load_bt(csv_name)
        sharpes = []
        for s in slips * 1e-4:
            net = df["gross"] - df["fees"] - df["traded"] * s
            sharpes.append(net.mean() / net.std(ddof=1) * np.sqrt(252))
        ax.plot(slips, sharpes, color=color, linewidth=1.8, marker="o", markersize=4)
        ax.annotate(label, (slips[-1], sharpes[-1]), xytext=(8, 0),
                    textcoords="offset points", fontsize=8.5, color=color, va="center")
    ax.set_xlabel("assumed slippage (bp per side)", fontsize=9, color=INK)
    ax.set_ylabel("annualized Sharpe (net)", fontsize=9, color=INK)
    ax.set_title("Cost sensitivity: no taker configuration survives",
                 fontsize=11, color=INK, loc="left")
    ax.tick_params(labelsize=8, length=0, colors=INK)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(-0.1, 6.6)

    fig.tight_layout()
    out = os.path.join(FIGDIR, "09_cost_sensitivity.png")
    fig.savefig(out, dpi=160, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")


FIGURES = [fig01_coverage, fig03_rolling_betas, fig04_residual_autocorr,
           fig07_equity_curves, fig09_cost_sensitivity]

if __name__ == "__main__":
    os.makedirs(FIGDIR, exist_ok=True)
    os.makedirs(REPORTS, exist_ok=True)
    for fig in FIGURES:
        fig()
