import csv
import glob
import json
import os
import random
import time
from datetime import datetime

import numpy as np

SEED = 20240501
N_BOOT = 2000
HOLDOUT = 0.8

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_PATH = os.path.join(BASE_DIR, "results.json")

PARAMS = {"seed": SEED, "n_boot": N_BOOT, "holdout": HOLDOUT}


def load_rows(data_dir):
    rows = []
    for path in glob.glob(os.path.join(data_dir, "*.csv")):
        with open(path, newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                rows.append((rec["group"], float(rec["value"])))
    return rows


def subsample(rows, frac):
    rows = list(rows)
    random.shuffle(rows)
    k = int(len(rows) * frac)
    return rows[:k]


def bootstrap_means(values, rng, n_boot):
    values = np.asarray(values, dtype=float)
    idx = rng.integers(0, len(values), size=(n_boot, len(values)))
    return values[idx].mean(axis=1)


def main():
    t0 = time.perf_counter()
    rng = np.random.default_rng(SEED)

    rows = subsample(load_rows(DATA_DIR), HOLDOUT)
    groups = {g for g, _ in rows}

    summary = {}
    for g in groups:
        vals = [v for gg, v in rows if gg == g]
        boots = bootstrap_means(vals, rng, N_BOOT)
        summary[g] = {
            "n": len(vals),
            "mean": round(float(np.mean(vals)), 4),
            "ci_low": round(float(np.percentile(boots, 2.5)), 4),
            "ci_high": round(float(np.percentile(boots, 97.5)), 4),
        }

    effect = summary["treatment"]["mean"] - summary["control"]["mean"]
    result = {
        "params": {k: v for k, v in PARAMS.items()},
        "groups": summary,
        "effect": round(effect, 4),
        "data_dir": DATA_DIR,
        "run_at": datetime.now().isoformat(timespec="seconds"),
    }

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(f"effect = {result['effect']:.4f}")
    for g in sorted(summary):
        print(g, summary[g])
    print(f"elapsed {time.perf_counter() - t0:.2f}s")


if __name__ == "__main__":
    main()
