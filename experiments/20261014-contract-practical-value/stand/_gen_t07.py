import csv
import os
import numpy as np

OUT = "tasks/t07/material"  # run from the stand folder
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261014)
N = 24000

bands = ["trial", "new", "mid", "long"]
band_p = [0.10, 0.30, 0.35, 0.25]
p_high = {"trial": 0.3, "new": 0.3, "mid": 0.5, "long": 0.7}
p_adopt = {"trial": (0.0, 0.0), "new": (0.05, 0.20), "mid": (0.12, 0.40), "long": (0.25, 0.60)}
base = {"trial": (0.55, 0.45), "new": (0.40, 0.25), "mid": (0.26, 0.14), "long": (0.14, 0.06)}
q_dec = {"trial": (0.20, 0.20), "new": (0.25, 0.12), "mid": (0.18, 0.08), "long": (0.12, 0.05)}

rows = []
dis_log = []
for i in range(N):
    b = bands[rng.choice(4, p=band_p)]
    hi = int(rng.random() < p_high[b])
    adopt = int(rng.random() < p_adopt[b][hi])
    dec = int(rng.random() < q_dec[b][hi])
    p365 = min(0.95, base[b][hi] + 0.40 * dec)
    ch365 = int(rng.random() < p365)
    drop = int(rng.integers(10, 250)) if dec else None
    disabled = adopt and dec and rng.random() < 0.75
    dis_day = drop + int(rng.integers(7, 45)) if disabled else None
    churn_day = None
    if ch365:
        if dec:
            start = dis_day if disabled else drop
            churn_day = min(364, start + int(rng.integers(5, 110)))
        else:
            churn_day = int(365 * rng.random() ** 1.3)
    status = "never" if not adopt else ("disabled" if disabled else "on")
    if status == "on":
        call = int(rng.random() < 0.80)
    else:
        call = int(rng.random() < (0.70 if dec else 0.10))
    ch180 = int(ch365 and churn_day <= 180)
    rows.append((b, "high" if hi else "low", status, call, ch180, ch365))
    if disabled:
        dis_log.append((i + 100001, drop, dis_day, churn_day if churn_day is not None else ""))

agg = {}
for b, act, st, call, c180, c365 in rows:
    k = (b, act, st, call)
    a = agg.setdefault(k, [0, 0, 0])
    a[0] += 1
    a[1] += c180
    a[2] += c365
with open(f"{OUT}/cohorts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(
        [
            "tenure_band",
            "activity_before",
            "feature_status",
            "cs_call",
            "customers",
            "churned_180d",
            "churned_365d",
        ]
    )
    for b in bands:
        for act in ["low", "high"]:
            for st in ["on", "disabled", "never"]:
                for call in [0, 1]:
                    if (b, act, st, call) in agg:
                        w.writerow([b, act, st, call, *agg[(b, act, st, call)]])

idx = sorted(rng.choice(len(dis_log), size=60, replace=False))
with open(f"{OUT}/feature_disable_log.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "activity_drop_day", "feature_disabled_day", "churn_day"])
    for j in idx:
        w.writerow(dis_log[j])
print("disablers total", len(dis_log), "rows", len(agg))
