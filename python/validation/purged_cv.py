"""
Purged walk-forward cross-validation splits.

Why not ordinary K-fold: our labels are FORWARD sums (next 10-30 minutes),
so a random shuffle would put a label's future inside another fold's
training set — the model would be graded on questions it saw the answers
to. Financial ML's most common silent failure.

The scheme (walk-forward with an embargo):

    train: everything up to Dec 31 of year Y
    embargo: skip the next `embargo_days` trading days
    test:  year Y+1 (after the embargo)

then roll Y forward one year. The embargo is belt-and-braces: our labels
only look 30 minutes ahead and never cross a day boundary, so even 1 day
would do; 5 keeps the design safe if someone later adds multi-day labels.

Usage:
    for fold in walk_forward_splits(dates):        # dates: np.array of date64
        train_mask, test_mask = fold.masks(dates)
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Fold:
    name: str
    train_end: np.datetime64      # train: date <= train_end
    test_start: np.datetime64     # test: test_start <= date <= test_end
    test_end: np.datetime64

    def masks(self, dates):
        train = dates <= self.train_end
        test = (dates >= self.test_start) & (dates <= self.test_end)
        return train, test


def walk_forward_splits(dates, embargo_days=5, min_train_years=1):
    """Yearly expanding-window folds over the span of `dates`."""
    unique_days = np.unique(dates)
    years = np.arange(int(str(unique_days[0])[:4]) + min_train_years,
                      int(str(unique_days[-1])[:4]) + 1)
    folds = []
    for year in years:
        train_end = np.datetime64(f"{year - 1}-12-31")
        # embargo counted in TRADING days present in the data
        after = unique_days[unique_days > train_end]
        if len(after) <= embargo_days:
            continue
        test_start = after[embargo_days]
        test_end = min(np.datetime64(f"{year}-12-31"), unique_days[-1])
        if test_start > test_end:
            continue
        folds.append(Fold(str(year), train_end, test_start, test_end))
    return folds
