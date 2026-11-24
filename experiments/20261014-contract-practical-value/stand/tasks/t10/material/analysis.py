import csv
import numpy as np

DATA = "data.csv"
N_PERM = 10000
SEED = 2024


def load(path=DATA):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def select(rows):
    out = []
    for r in rows:
        if r["completed"] != "1":
            continue
        if int(r["pre_score"]) >= 85:
            continue
        out.append(r)
    return out


def gains(rows, group, site=None):
    return np.array(
        [
            float(r["post_score"]) - float(r["pre_score"])
            for r in rows
            if r["group"] == group and (site is None or r["site"] == site)
        ]
    )


def perm_test(a, b, n_perm=N_PERM, seed=SEED):
    rng = np.random.default_rng(seed)
    obs = a.mean() - b.mean()
    pooled = np.concatenate([a, b])
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        d = pooled[: len(a)].mean() - pooled[len(a) :].mean()
        if abs(d) >= abs(obs):
            hits += 1
    return obs, (hits + 1) / (n_perm + 1)


def cohen_d(a, b):
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return (a.mean() - b.mean()) / sp


def main():
    rows = load()
    n_all = len(rows)
    n_done = sum(r["completed"] == "1" for r in rows)
    print(f"enrolled: {n_all}")
    print(f"completed: {n_done}")
    print(f"dropout rate: {100 * (n_all - n_done) / n_all:.1f}%")

    sel = select(rows)
    t = gains(sel, "tutoring")
    c = gains(sel, "control")
    print(f"analysed: tutoring n={len(t)}, control n={len(c)}")
    print(f"mean gain tutoring: {t.mean():.2f} (sd {t.std(ddof=1):.2f})")
    print(f"mean gain control: {c.mean():.2f} (sd {c.std(ddof=1):.2f})")
    diff, p = perm_test(t, c)
    print(f"difference: {diff:.2f}, permutation p = {p:.4f}")
    print(f"cohen d: {cohen_d(t, c):.2f}")

    print("site  n_t  n_c  gain_t  gain_c  diff   p")
    for s in ["A", "B", "C"]:
        ts = gains(sel, "tutoring", s)
        cs = gains(sel, "control", s)
        d, ps = perm_test(ts, cs)
        print(f"{s:4} {len(ts):4} {len(cs):4} {ts.mean():7.2f} {cs.mean():7.2f} {d:6.2f} {ps:.4f}")

    resp = (t >= 5).sum()
    print(f"responders (gain >= 5) in tutoring: {resp}/{len(t)} = {100 * resp / len(t):.1f}%")


if __name__ == "__main__":
    main()
