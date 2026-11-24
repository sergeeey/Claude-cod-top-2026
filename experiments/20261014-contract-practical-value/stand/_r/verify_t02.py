import sys
from itertools import combinations

import numpy as np

sys.path.insert(0, sys.argv[1])
from data import generate  # noqa: E402
from train import (  # noqa: E402
    impute,
    knn_proba,
    rank_features,
    roc_auc,
    standardize,
    user_purchase_rate,
)

ALL = ("scale", "select", "rate", "dup", "split", "tune")
GRID_F = (5, 10, 20, 33)
GRID_K = (1, 3, 5, 11, 21, 41)


def dedup_idx(X, y):
    key = np.nan_to_num(np.column_stack([X, y]), nan=-999.0)
    _, keep = np.unique(key, axis=0, return_index=True)
    return np.sort(keep)


def run(fix):
    table = generate()
    if "dup" in fix:
        table = table[dedup_idx(table[:, :-1], table[:, -1])]
    y, day, uid = table[:, -1], table[:, 1], table[:, 0].astype(int)
    n = len(y)
    if "split" in fix:
        tr, te = np.where(day < 135)[0], np.where(day >= 135)[0]
    else:
        perm = np.random.default_rng(42).permutation(n)
        cut = int(0.75 * n)
        tr, te = perm[:cut], perm[cut:]
    if "rate" in fix:
        rate = np.full(n, y[tr].mean())
        for i in range(n):
            m = (uid[tr] == uid[i]) & (day[tr] < day[i])
            if m.any():
                rate[i] = y[tr][m].mean()
    else:
        rate = user_purchase_rate(table)
    X = np.column_stack([table[:, 2:-1], rate])
    if "scale" in fix:
        mu, sd = np.nanmean(X[tr], 0), np.nanstd(X[tr], 0) + 1e-9
        X = (X - mu) / sd
    else:
        X = standardize(X)
    Xtr, Xte = impute(X[tr], X[te])
    keep = dedup_idx(Xtr, y[tr])
    tr, Xtr = tr[keep], Xtr[keep]
    ytr, yte = y[tr], y[te]
    if "tune" in fix:
        if "split" in fix:
            fit = day[tr] < 108
        else:
            fit = np.random.default_rng(1).random(len(tr)) < 0.8
        A, ya, B, yb = Xtr[fit], ytr[fit], Xtr[~fit], ytr[~fit]
    else:
        A, ya, B, yb = Xtr, ytr, Xte, yte
    order = rank_features(A, ya) if "select" in fix else rank_features(X, y)
    best = None
    for nf in GRID_F:
        c = order[:nf]
        for k in GRID_K:
            a = roc_auc(yb, knn_proba(A[:, c], ya, B[:, c], k))
            if best is None or a > best[0]:
                best = (a, nf, k)
    _, nf, k = best
    c = order[:nf]
    return roc_auc(yte, knn_proba(Xtr[:, c], ytr, Xte[:, c], k)), nf, k


print("all leaky   ", run(()))
print("all fixed   ", run(ALL))
for f in ALL:
    print(f"fix only {f:6s}", run((f,)))
for f in ALL:
    print(f"leak only {f:6s}", run(tuple(x for x in ALL if x != f)))

# decoy: AUC vs brute force with ties
rng = np.random.default_rng(0)
for _ in range(5):
    yy = (rng.random(200) < 0.4).astype(float)
    ss = rng.integers(0, 6, 200).astype(float)
    pos, neg = ss[yy == 1], ss[yy == 0]
    brute = ((pos[:, None] > neg[None]).sum() + 0.5 * (pos[:, None] == neg[None]).sum()) / (
        len(pos) * len(neg)
    )
    assert abs(brute - roc_auc(yy, ss)) < 1e-12
print("auc ok")
# decoy: prev_buys strictly past
t = generate()
t = t[dedup_idx(t[:, :-1], t[:, -1])]
bad = 0
for u in np.unique(t[:, 0]):
    r = t[t[:, 0] == u]
    r = r[np.argsort(r[:, 1])]
    bad += int(np.any(r[:, 8] != np.cumsum(r[:, -1]) - r[:, -1]))
print("prev_buys mismatched users:", bad)
# decoy: impute uses train only
a = np.array([[1.0], [np.nan], [3.0]])
b = np.array([[np.nan], [100.0]])
print("impute:", impute(a, b)[1].ravel(), "(expect 2.0 from train median)")
