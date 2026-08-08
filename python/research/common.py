"""
Shared data/feature/metric code for the Phase 5 models.

Both models (02_baseline_ols.py, 03_mlp.py) import from here, so they are
guaranteed to see IDENTICAL features, identical folds, and identical metrics
— the comparison between them is meaningful only because of this file.
"""

import os
import subprocess

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(PROJECT_ROOT, "data", "model")
DATASET = os.path.join(MODEL_DIR, "dataset.csv.gz")
Q_BIN = os.path.expanduser("~/.kx/bin/q")

LABELS = ["fwdres10", "fwdres15", "fwdres30"]
FEATURES = ["z30", "z60", "lrv", "lvs", "gapc", "tod_open", "tod_close"]
EPS = 1e-8


def export_dataset():
    """Pull the modeling columns out of kdb+ once; cache as csv.gz."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(DATASET):
        return
    snippet_path = os.path.join(MODEL_DIR, "_export.q")
    csv_path = DATASET[:-3]                            # drop .gz; gzip after
    with open(snippet_path, "w") as fh:
        fh.write(f"""
\\l data/hdb
t: select date, sym: value sym, bkt: `minute$time, cumres30, cumres60, rv60,
          vsurp, gap, fwdres10, fwdres15, fwdres30
   from sig where not null cumres30, not null rv60, rv60 > 0
(hsym `$"{csv_path}") 0: csv 0: t
exit 0
""")
    subprocess.run([Q_BIN, snippet_path, "-q"], cwd=PROJECT_ROOT, check=True,
                   timeout=1800)
    os.remove(snippet_path)
    subprocess.run(["gzip", "-f", csv_path], check=True, timeout=1800)
    print("exported dataset")


def load_features():
    """Load the cached dataset and engineer the model features."""
    df = pd.read_csv(DATASET, parse_dates=["date"])
    hh_mm = df["bkt"].str.split(":", expand=True).astype(int)
    df["minute_of_day"] = hh_mm[0] * 60 + hh_mm[1]

    # z30/z60: trailing residual moves scaled by the stock's own current
    # intraday vol — "how stretched is this stock right now, in its units"
    df["z30"] = (df["cumres30"] / (df["rv60"] + EPS)).clip(-8, 8)
    df["z60"] = (df["cumres60"] / (df["rv60"] + EPS)).clip(-8, 8)
    df["lrv"] = np.log(df["rv60"] + EPS)
    df["lvs"] = np.log(df["vsurp"].clip(0.05, 20.0)).fillna(0.0)
    df["gapc"] = df["gap"].clip(-0.10, 0.10).fillna(0.0)
    df["tod_open"] = (df["minute_of_day"] < 630).astype(float)     # < 10:30
    df["tod_close"] = (df["minute_of_day"] >= 900).astype(float)   # >= 15:00
    return df


def rank_ic(frame, pred_col, label_col):
    """Mean and t-stat of daily cross-sectional Spearman IC."""
    f = frame.copy()
    grp = f.groupby(["date", "bkt"], observed=True)
    f["pr"] = grp[pred_col].rank()
    f["yr"] = grp[label_col].rank()
    daily = (f.groupby("date", observed=True)[["pr", "yr"]]
              .corr().unstack().iloc[:, 1]).dropna()
    t_stat = daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily)))
    return daily.mean(), t_stat
