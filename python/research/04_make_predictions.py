"""
Produce the OUT-OF-SAMPLE prediction file the backtester consumes.

For each walk-forward fold: fit the OLS model (the Phase 5 winner) on the
training years, predict the held-out test year. Concatenating the test
years gives predictions for 2021 -> present in which no prediction was
made by a model that saw its own period. This file is the contract
between research (Python) and execution (the C++ backtester):

    data/model/predictions.csv   columns: date, sym, bkt, pred

pred = expected next-10-minute residual return (label fwdres10).
"""

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "python", "validation"))
from common import FEATURES, MODEL_DIR, export_dataset, load_features
from purged_cv import walk_forward_splits

LABEL = "fwdres10"


def main():
    export_dataset()
    df = load_features().dropna(subset=[LABEL] + FEATURES)
    dates = df["date"].to_numpy()

    parts = []
    for fold in walk_forward_splits(dates):
        tr_mask, te_mask = fold.masks(dates)
        train, test = df[tr_mask], df[te_mask]
        if len(train) < 100_000 or len(test) < 10_000:
            continue
        mu = train[FEATURES].mean()
        sd = train[FEATURES].std().replace(0, 1.0)
        Xtr = np.column_stack([np.ones(len(train)), ((train[FEATURES] - mu) / sd).to_numpy()])
        Xte = np.column_stack([np.ones(len(test)), ((test[FEATURES] - mu) / sd).to_numpy()])
        beta, *_ = np.linalg.lstsq(Xtr, train[LABEL].to_numpy(), rcond=None)
        out = test[["date", "sym", "bkt"]].copy()
        out["pred"] = Xte @ beta
        parts.append(out)
        print(f"fold {fold.name}: {len(out):,} predictions")

    preds = pd.concat(parts, ignore_index=True)
    path = os.path.join(MODEL_DIR, "predictions.csv")
    preds.to_csv(path, index=False, float_format="%.8g")
    print(f"wrote {len(preds):,} rows to {path}")


if __name__ == "__main__":
    main()
