"""
Phase 7: factor attribution — the last referee.

Regress the strategy's DAILY returns on the Carhart four factors:

    r_strat[t] = alpha + b_mkt*MKT[t] + b_smb*SMB[t] + b_hml*HML[t] + b_wml*WML[t] + e

If the strategy earns money only through factor exposures, alpha ~ 0 and the
project produced factor timing, not alpha. If alpha survives with the betas
~ 0, the P&L is genuinely idiosyncratic — which is what the whole
neutralization machinery was for.

We attribute the PAPER-fill series (the one with positive P&L; the market-
fill series is flat-to-negative, and attributing a zero is uninformative,
though it is reported for completeness). Newey-West (HAC) standard errors —
daily strategy returns are autocorrelated enough to make plain OLS t-stats
overconfident.

Run:  python3 python/research/05_attribution.py
"""

import os

import numpy as np
import pandas as pd
import statsmodels.api as sm

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "model")
FACTORS = os.path.join(PROJECT_ROOT, "data", "raw", "factors", "carhart_daily.csv")

BOOK = 1_000_000.0          # gross notional the P&L is earned on
SERIES = {
    "paper 10-min": ("bt_paper_10m.csv", 0.0),
    "market 10-min": ("backtest_daily.csv", 0.0),
    "market 60-min net@0.5bp": ("bt_market_60m.csv", 0.5e-4),
}


def load_pnl(csv_name, slip):
    df = pd.read_csv(os.path.join(MODEL_DIR, csv_name))
    # qdate = days since 2000-01-01 (kdb+'s epoch)
    df["date"] = pd.Timestamp("2000-01-01") + pd.to_timedelta(df["qdate"], unit="D")
    df["ret"] = (df["gross"] - df["fees"] - df["traded"] * slip) / BOOK
    return df[["date", "ret"]]


def attribute(name, pnl, factors):
    j = pnl.merge(factors, on="date", how="inner")
    X = sm.add_constant(j[["mkt_rf", "smb", "hml", "wml"]])
    model = sm.OLS(j["ret"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    alpha_annual = model.params["const"] * 252
    print(f"\n=== {name} ({len(j)} days) ===")
    print(f"alpha: {alpha_annual*100:+.2f}%/yr  (t = {model.tvalues['const']:+.2f})")
    for f in ["mkt_rf", "smb", "hml", "wml"]:
        print(f"beta {f:6s}: {model.params[f]:+.4f}  (t = {model.tvalues[f]:+.2f})")
    print(f"R^2: {model.rsquared:.4f}")
    return {"series": name, "alpha_annual": alpha_annual,
            "alpha_t": model.tvalues["const"], "r2": model.rsquared,
            **{f"b_{f}": model.params[f] for f in ["mkt_rf", "smb", "hml", "wml"]},
            **{f"t_{f}": model.tvalues[f] for f in ["mkt_rf", "smb", "hml", "wml"]}}


if __name__ == "__main__":
    factors = pd.read_csv(FACTORS, parse_dates=["date"])
    rows = [attribute(name, load_pnl(csv, slip), factors)
            for name, (csv, slip) in SERIES.items()]
    out = os.path.join(MODEL_DIR, "attribution.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nsaved {out}")
