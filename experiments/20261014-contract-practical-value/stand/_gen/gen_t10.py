import csv
import sys
import numpy as np

out = sys.argv[1]
rng = np.random.default_rng(42)
rows = []
sites = ["A"] * 44 + ["B"] * 44 + ["C"] * 12
drop_idx = set(rng.choice(100, size=20, replace=False).tolist())
for i in range(100):
    group = "tutoring" if i % 2 == 0 else "control"
    site = sites[i]
    age = int(rng.integers(9, 15))
    pre = float(np.clip(np.round(rng.normal(64, 12)), 30, 98))
    if group == "tutoring":
        sessions = int(rng.integers(6, 25))
        mu = {"A": 8.5, "B": 4.5, "C": 9.0}[site] + 0.08 * (sessions - 15)
    else:
        sessions = 0
        mu = 2.8
    if pre >= 85:
        mu -= 3.0
    gain = np.round(rng.normal(mu, 4.8))
    completed = 0 if i in drop_idx else 1
    post = "" if completed == 0 else str(int(min(100, pre + gain)))
    rows.append([f"S{i + 1:03d}", group, site, age, sessions, int(pre), post, completed])

with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "group", "site", "age", "sessions", "pre_score", "post_score", "completed"])
    w.writerows(rows)
