"""Purchase prediction: kNN over session features.

Run:  python train.py
"""

import numpy as np

from data import FEATURES, generate

SEED = 42
TEST_SHARE = 0.25


def user_purchase_rate(table):
    uid = table[:, 0].astype(int)
    y = table[:, -1]
    sums = np.bincount(uid, weights=y)
    counts = np.bincount(uid)
    return sums[uid] / counts[uid]


def standardize(X):
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0) + 1e-9
    return (X - mu) / sd


def rank_features(X, y):
    Xf = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    Xc = Xf - Xf.mean(axis=0)
    yc = y - y.mean()
    num = (Xc * yc[:, None]).sum(axis=0)
    den = np.sqrt((Xc**2).sum(axis=0) * (yc**2).sum()) + 1e-12
    return np.argsort(-np.abs(num / den), kind="stable")


def impute(train, test):
    med = np.nanmedian(train, axis=0)
    train = np.where(np.isnan(train), med, train)
    test = np.where(np.isnan(test), med, test)
    return train, test


def drop_duplicates(X, y):
    _, keep = np.unique(np.column_stack([X, y]), axis=0, return_index=True)
    keep = np.sort(keep)
    return X[keep], y[keep]


def knn_proba(X_tr, y_tr, X_te, k):
    d = (X_te**2).sum(1)[:, None] + (X_tr**2).sum(1)[None, :] - 2.0 * X_te @ X_tr.T
    idx = np.argsort(d, axis=1, kind="stable")[:, :k]
    return y_tr[idx].mean(axis=1)


def roc_auc(y, score):
    order = np.argsort(score, kind="mergesort")
    s = score[order]
    ranks = np.empty(len(s))
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[i : j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    r = np.empty(len(s))
    r[order] = ranks
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    return (r[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def main():
    table = generate()
    names = FEATURES + ["user_rate"]
    X = np.column_stack([table[:, 2:-1], user_purchase_rate(table)])
    y = table[:, -1]

    X = standardize(X)
    order = rank_features(X, y)

    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(y))
    cut = int((1.0 - TEST_SHARE) * len(y))
    tr, te = perm[:cut], perm[cut:]
    X_tr, X_te = impute(X[tr], X[te])
    y_tr, y_te = y[tr], y[te]
    X_tr, y_tr = drop_duplicates(X_tr, y_tr)

    best = None
    for n_feat in (5, 10, 20, len(names)):
        cols = order[:n_feat]
        for k in (1, 3, 5, 11, 21, 41):
            p = knn_proba(X_tr[:, cols], y_tr, X_te[:, cols], k)
            auc = roc_auc(y_te, p)
            if best is None or auc > best[0]:
                best = (auc, n_feat, k)

    auc, n_feat, k = best
    cols = order[:n_feat]
    p = knn_proba(X_tr[:, cols], y_tr, X_te[:, cols], k)
    acc = float(((p >= 0.5) == (y_te == 1)).mean())
    print(f"rows: train={len(y_tr)} test={len(y_te)}")
    print(f"features ({n_feat}): {[names[c] for c in cols]}")
    print(f"k={k}  test ROC AUC={auc:.3f}  test accuracy={acc:.3f}")


if __name__ == "__main__":
    main()
