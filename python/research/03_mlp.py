"""
Phase 5 challenger: a small MLP on the SAME features, folds, and metrics
as the OLS baseline (02_baseline_ols.py).

Design principles:
  - IDENTICAL inputs. Any outperformance must come from nonlinearity and
    feature interactions, not from extra information.
  - Small net, strong regularization: 2 hidden layers x 32 units, dropout.
    With 7 features and one target, anything bigger just memorizes noise.
  - Honest epoch selection: the last 15% of each fold's TRAIN dates are
    held out as a validation set for early stopping. The test year is
    never touched until the final evaluation.
  - Primary label: fwdres10 (chosen by the data in fig 04 / the baseline).

Run:  python3 python/research/03_mlp.py          (~10 min on Apple GPU)
"""

import os
import sys

import numpy as np
import pandas as pd
import torch
from torch import nn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "python", "validation"))
from common import FEATURES, MODEL_DIR, export_dataset, load_features, rank_ic
from purged_cv import walk_forward_splits

LABEL = "fwdres10"
SEED = 7
MAX_TRAIN_ROWS = 2_500_000      # subsample cap: keeps folds fast, plenty of data
BATCH = 16384
MAX_EPOCHS = 12
PATIENCE = 2

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")


class SmallMLP(nn.Module):
    def __init__(self, n_features):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 32), nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(32, 32), nn.ReLU(), nn.Dropout(0.1),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def train_one_fold(train, val, test):
    """Standardize on train, fit with early stopping on val, predict test."""
    mu = train[FEATURES].mean()
    sd = train[FEATURES].std().replace(0, 1.0)
    to_x = lambda d: torch.tensor(((d[FEATURES] - mu) / sd).to_numpy(np.float32))
    to_y = lambda d: torch.tensor(d[LABEL].to_numpy(np.float32))

    # scale labels to unit-ish variance so the loss is well-conditioned;
    # predictions are de-scaled after (affine, so rank metrics unaffected)
    y_scale = float(train[LABEL].std()) or 1.0

    Xtr, ytr = to_x(train).to(DEVICE), (to_y(train) / y_scale).to(DEVICE)
    Xva, yva = to_x(val).to(DEVICE), (to_y(val) / y_scale).to(DEVICE)

    torch.manual_seed(SEED)
    model = SmallMLP(len(FEATURES)).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    loss_fn = nn.MSELoss()

    best_val, best_state, bad_epochs = np.inf, None, 0
    n = len(Xtr)
    for epoch in range(MAX_EPOCHS):
        model.train()
        perm = torch.randperm(n, device=DEVICE)
        for i in range(0, n, BATCH):
            idx = perm[i:i + BATCH]
            opt.zero_grad()
            loss = loss_fn(model(Xtr[idx]), ytr[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(model(Xva), yva))
        if val_loss < best_val - 1e-7:
            best_val, bad_epochs = val_loss, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad_epochs += 1
            if bad_epochs >= PATIENCE:
                break
    model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        Xte = to_x(test).to(DEVICE)
        pred = (model(Xte).cpu().numpy()) * y_scale
    return pred, epoch + 1


def main():
    rng = np.random.default_rng(SEED)
    export_dataset()
    df = load_features().dropna(subset=[LABEL] + FEATURES)
    print(f"dataset: {len(df):,} rows on {DEVICE}")

    results = []
    dates = df["date"].to_numpy()
    for fold in walk_forward_splits(dates):
        tr_mask, te_mask = fold.masks(dates)
        train_all, test = df[tr_mask], df[te_mask]
        if len(train_all) < 100_000 or len(test) < 10_000:
            continue

        # early-stop validation = last 15% of train DATES (never the test year)
        udays = np.sort(train_all["date"].unique())
        cut = udays[int(len(udays) * 0.85)]
        train = train_all[train_all["date"] < cut]
        val = train_all[train_all["date"] >= cut]
        if len(train) > MAX_TRAIN_ROWS:
            keep = rng.choice(len(train), MAX_TRAIN_ROWS, replace=False)
            train = train.iloc[np.sort(keep)]

        pred, epochs = train_one_fold(train, val, test)
        yte = test[LABEL].to_numpy()
        oos_r2 = 1.0 - np.sum((yte - pred) ** 2) / np.sum((yte - yte.mean()) ** 2)
        t = test.copy()
        t["pred"] = pred
        ic, ic_t = rank_ic(t, "pred", LABEL)
        results.append({"fold": fold.name, "n_test": len(test), "epochs": epochs,
                        "oosR2": oos_r2, "rankIC": ic, "IC_t": ic_t})
        print(f"fold {fold.name}: IC={ic:.5f} t={ic_t:.2f} R2={oos_r2:.5f} ({epochs} epochs)")

    res = pd.DataFrame(results)
    out = os.path.join(MODEL_DIR, "mlp_results.csv")
    res.to_csv(out, index=False)
    print(f"\nsaved {out}")
    print("\nMLP summary (label fwdres10):")
    print(res[["oosR2", "rankIC", "IC_t"]].mean().to_string())

    base_path = os.path.join(MODEL_DIR, "baseline_ols_results.csv")
    if os.path.exists(base_path):
        base = pd.read_csv(base_path)
        base10 = base[base["label"] == LABEL]
        cmp = pd.DataFrame({
            "OLS": base10[["oosR2", "rankIC", "IC_t"]].mean(),
            "MLP": res[["oosR2", "rankIC", "IC_t"]].mean(),
        })
        print("\nhead-to-head (mean across folds):")
        print(cmp.to_string())


if __name__ == "__main__":
    main()
