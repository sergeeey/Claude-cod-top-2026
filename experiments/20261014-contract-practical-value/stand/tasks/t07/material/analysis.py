import csv
import math
from pathlib import Path

import numpy as np

DATA = Path(__file__).with_name("cohorts.csv")


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["cs_call"] = int(r["cs_call"])
        for k in ("customers", "churned_180d", "churned_365d"):
            r[k] = int(r[k])
    return rows


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def summarize(rows, churn_col):
    n = sum(r["customers"] for r in rows)
    k = sum(r[churn_col] for r in rows)
    lo, hi = wilson(k, n)
    return n, k, k / n, lo, hi


def main():
    rows = load(DATA)
    eligible = [r for r in rows if r["tenure_band"] != "trial"]
    sample = [r for r in eligible if r["cs_call"] == 1]

    treated = [r for r in sample if r["feature_status"] == "on"]
    control = [r for r in sample if r["feature_status"] != "on"]

    n_t, k_t, p_t, lo_t, hi_t = summarize(treated, "churned_180d")
    n_c, k_c, p_c, lo_c, hi_c = summarize(control, "churned_365d")

    print(f"Клиентов в анализе: {n_t + n_c}")
    print(f"С функцией:  n={n_t:5d}  отток={p_t:.1%}  95% ДИ [{lo_t:.1%}; {hi_t:.1%}]")
    print(f"Без функции: n={n_c:5d}  отток={p_c:.1%}  95% ДИ [{lo_c:.1%}; {hi_c:.1%}]")
    print(f"Абсолютная разница: {(p_c - p_t) * 100:.1f} п.п.")
    print(f"Относительное снижение оттока: {(p_c - p_t) / p_c:.0%}")

    x = []
    y = []
    for r in treated:
        x += [1] * r["customers"]
        y += [1] * r["churned_180d"] + [0] * (r["customers"] - r["churned_180d"])
    for r in control:
        x += [0] * r["customers"]
        y += [1] * r["churned_365d"] + [0] * (r["customers"] - r["churned_365d"])
    corr = np.corrcoef(np.array(x), np.array(y))[0, 1]
    print(f"Корреляция 'функция включена' и 'отток': {corr:.2f}")


if __name__ == "__main__":
    main()
