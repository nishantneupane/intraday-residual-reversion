"""
Phase 5 baseline: OLS prediction of forward residual returns.

The baseline exists so the MLP (03_mlp.py) has something honest to beat.
Both scripts import data, features, folds, and metrics from common.py /
purged_cv.py, so the comparison is apples-to-apples by construction.

Metrics, defined:
  oosR2   1 - SSE/variance on the test year. For 5-15 minute horizons,
          anything reliably ABOVE ZERO is signal; 0.001 is real money.
  rankIC  Spearman correlation between prediction and outcome WITHIN each
          (date, bucket) cross-section, then averaged per day. Measures
          ranking skill — what a long-short portfolio actually monetizes.
  IC t    t-stat of the daily IC series: is the skill consistent?

Run:  python3 python/research/02_baseline_ols.py
"""

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "python", "validation"))
from common import FEATURES, LABELS, MODEL_DIR, export_dataset, load_features, rank_ic
from purged_cv import walk_forward_splits


def run_baseline(df):
    results = []
    for label in LABELS:
        d = df.dropna(subset=[label] + FEATURES)
        dates = d["date"].to_numpy()
        for fold in walk_forward_splits(dates):
            tr_mask, te_mask = fold.masks(dates)
            train, test = d[tr_mask], d[te_mask]
            if len(train) < 100_000 or len(test) < 10_000:
                continue
            # standardize on TRAIN stats only
            mu = train[FEATURES].mean()
            sd = train[FEATURES].std().replace(0, 1.0)
            Xtr = np.column_stack([np.ones(len(train)),
                                   ((train[FEATURES] - mu) / sd).to_numpy()])
            Xte = np.column_stack([np.ones(len(test)),
                                   ((test[FEATURES] - mu) / sd).to_numpy()])
            ytr, yte = train[label].to_numpy(), test[label].to_numpy()

            beta, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
            pred = Xte @ beta
            oos_r2 = 1.0 - np.sum((yte - pred) ** 2) / np.sum((yte - yte.mean()) ** 2)

            t = test.copy()
            t["pred"] = pred
            ic, ic_t = rank_ic(t, "pred", label)
            results.append({"label": label, "fold": fold.name, "n_test": len(test),
                            "oosR2": oos_r2, "rankIC": ic, "IC_t": ic_t,
                            "coef_z30": beta[1]})
    return pd.DataFrame(results)


if __name__ == "__main__":
    export_dataset()
    df = load_features()
    print(f"dataset: {len(df):,} rows, {df['date'].min().date()} -> {df['date'].max().date()}")
    res = run_baseline(df)
    pd.set_option("display.float_format", lambda v: f"{v:.5f}")
    print(res.to_string(index=False))
    out = os.path.join(MODEL_DIR, "baseline_ols_results.csv")
    res.to_csv(out, index=False)
    print(f"\nsaved {out}")
    print("\nsummary by label (mean across folds):")
    print(res.groupby("label")[["oosR2", "rankIC", "IC_t"]].mean().to_string())
