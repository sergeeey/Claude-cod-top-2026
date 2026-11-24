import csv, math, os
import numpy as np

OUT = "<HOME>/AppData/Local/Temp/claude/D--Claude-cod-top-2026/29a715b1-3478-43c8-b908-635a18c4834e/scratchpad/practical/tasks/t01/material"
os.makedirs(OUT, exist_ok=True)


def p2(z):
    return math.erfc(abs(z) / math.sqrt(2))


def p1(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def zprop(xa, na, xb, nb):
    p = (xa + xb) / (na + nb)
    return (xb / nb - xa / na) / math.sqrt(p * (1 - p) * (1 / na + 1 / nb))


def srm(na, nb):
    e = (na + nb) / 2
    chi = (na - e) ** 2 / e + (nb - e) ** 2 / e
    return math.erfc(math.sqrt(chi / 2))


found = None
for seed in range(20000):
    rng = np.random.default_rng(seed)
    tot = rng.poisson(720, 28)
    nb = rng.binomial(tot, 0.5)
    na = tot - nb
    ca = rng.binomial(na, 0.041)
    cb = rng.binomial(nb, 0.041)
    ra = rng.binomial(ca, 0.06)
    rb = rng.binomial(cb, 0.09)
    cna, cnb, cca, ccb = np.cumsum(na), np.cumsum(nb), np.cumsum(ca), np.cumsum(cb)
    k = None
    for d in range(28):
        if p1(zprop(cca[d], cna[d], ccb[d], cnb[d])) < 0.05:
            k = d
            break
    if k is None or not (8 <= k + 1 <= 13):
        continue
    if p2(zprop(cca[-1], cna[-1], ccb[-1], cnb[-1])) < 0.35:
        continue
    if p2(zprop(cca[k], cna[k], ccb[k], cnb[k])) < 0.05:
        continue
    if srm(cna[-1], cnb[-1]) < 0.25 or srm(cna[k], cnb[k]) < 0.25 or cna[k] == cnb[k]:
        continue
    sra, srb = ra[: k + 1].sum(), rb[: k + 1].sum()
    if srb / ccb[k] <= sra / cca[k] * 1.3:
        continue
    pr = p2(zprop(sra, cca[k], srb, ccb[k]))
    if not (0.2 < pr < 0.6):
        continue
    found = (seed, na, nb, ca, cb, ra, rb, k)
    break

seed, na, nb, ca, cb, ra, rb, k = found
print("seed", seed, "stop day", k + 1)
with open(os.path.join(OUT, "daily.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["day", "group", "users", "conversions", "refunds"])
    for d in range(28):
        w.writerow([d + 1, "A", na[d], ca[d], ra[d]])
        w.writerow([d + 1, "B", nb[d], cb[d], rb[d]])
NA, NB, CA, CB = na[: k + 1].sum(), nb[: k + 1].sum(), ca[: k + 1].sum(), cb[: k + 1].sum()
print(
    "at stop: nA",
    NA,
    "nB",
    NB,
    "cA",
    CA,
    "cB",
    CB,
    "rA",
    ra[: k + 1].sum(),
    "rB",
    rb[: k + 1].sum(),
)
print("day28: nA", na.sum(), "nB", nb.sum(), "cA", ca.sum(), "cB", cb.sum())

segs = [
    ("RU", "mobile"),
    ("RU", "desktop"),
    ("KZ", "mobile"),
    ("KZ", "desktop"),
    ("BY", "mobile"),
    ("BY", "desktop"),
    ("UZ", "mobile"),
    ("UZ", "desktop"),
]
probs = [0.24, 0.16, 0.13, 0.09, 0.12, 0.08, 0.11, 0.07]
for s2 in range(20000):
    r = np.random.default_rng(1000 + s2)
    ua = r.multinomial(NA, probs)
    ub = r.multinomial(NB, probs)
    xa = r.multivariate_hypergeometric(ua, CA)
    xb = r.multivariate_hypergeometric(ub, CB)
    ps = [p2(zprop(xa[i], ua[i], xb[i], ub[i])) for i in range(8)]
    zs = [zprop(xa[i], ua[i], xb[i], ub[i]) for i in range(8)]
    i = int(np.argmin(ps))
    if 0.008 < ps[i] < 0.025 and zs[i] > 0 and sorted(ps)[1] > 0.1:
        print("segseed", 1000 + s2)
        for j, (c, dv) in enumerate(segs):
            print(f'    ("{c}", "{dv}", {ua[j]}, {xa[j]}, {ub[j]}, {xb[j]}),  p={ps[j]:.4f}')
        break

r = np.random.default_rng(77)
old = np.round(np.exp(r.normal(math.log(650), 0.55, 40))).astype(int)
new = np.round(old * 1.05 + r.normal(0, 12, 40)).astype(int)
d = new - old
pp = p2(d.mean() / (d.std(ddof=1) / math.sqrt(40)))
pw = p2((new.mean() - old.mean()) / math.sqrt(old.var(ddof=1) / 40 + new.var(ddof=1) / 40))
print("bench paired p", pp, "welch p", pw, "mean diff", d.mean())
with open(os.path.join(OUT, "benchmark.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["device_id", "load_ms_old", "load_ms_new"])
    for i in range(40):
        w.writerow([f"dev{i + 1:02d}", old[i], new[i]])
