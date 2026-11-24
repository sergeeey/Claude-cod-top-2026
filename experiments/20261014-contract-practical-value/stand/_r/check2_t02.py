import sys

import numpy as np

sys.path.insert(0, sys.argv[1])
from data import FEATURES, generate  # noqa: E402
from train import rank_features, standardize, user_purchase_rate  # noqa: E402

t = generate()
names = FEATURES + ["user_rate"]
X = standardize(np.column_stack([t[:, 2:-1], user_purchase_rate(t)]))
y = t[:, -1]
perm = np.random.default_rng(42).permutation(len(y))
tr, te = perm[: int(0.75 * len(y))], perm[int(0.75 * len(y)) :]
a = rank_features(X, y)
b = rank_features(X[tr], y[tr])
print("full ", [names[i] for i in a[:12]])
print("train", [names[i] for i in b[:12]])
key = np.nan_to_num(t, nan=-9.0)
print("dup rows", len(t) - len(np.unique(key, axis=0)))
ktr = {tuple(r) for r in key[tr]}
print("test rows with exact copy in train", sum(tuple(r) in ktr for r in key[te]))
print("share of rows day>=135", round(float((t[:, 1] >= 135).mean()), 3))
uid = t[:, 0]
print("test users also in train", len(set(uid[te]) & set(uid[tr])), "of", len(set(uid[te])))
