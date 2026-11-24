import csv
import math
import sys

import numpy as np

MAT = "<HOME>/AppData/Local/Temp/claude/D--Claude-cod-top-2026/29a715b1-3478-43c8-b908-635a18c4834e/scratchpad/practical/tasks/t01/material"
sys.path.insert(0, MAT)
import analysis as a  # noqa: E402

a.main()
print("\n==== VERIFY ====")
d = a.load_daily()
A = d["A"].sum(0)
B = d["B"].sum(0)
print(
    "day28 two-sided p",
    a.two_sided(a.prop_z(A[1], A[0], B[1], B[0])),
    "SRM28",
    a.srm_pvalue(A[0], B[0]),
)
cA = d["A"][:9].sum(0)
cB = d["B"][:9].sum(0)
print("day9 two-sided p", a.two_sided(a.prop_z(cA[1], cA[0], cB[1], cB[0])))
pa, pb = cA[1] / cA[0], cB[1] / cB[0]
se = math.sqrt(pa * (1 - pa) / cA[0] + pb * (1 - pb) / cB[0])
print(
    "CI diff day9",
    pb - pa - 1.96 * se,
    pb - pa + 1.96 * se,
    "rel",
    (pb - pa - 1.96 * se) / pa,
    (pb - pa + 1.96 * se) / pa,
)
ra, rb = cA[2] / cA[1], cB[2] / cB[1]
se = math.sqrt(ra * (1 - ra) / cA[1] + rb * (1 - rb) / cB[1])
print("refund CI diff", rb - ra - 1.96 * se, rb - ra + 1.96 * se)
# power to detect doubling of refund rate 5.4% -> 10.8% with ~140/arm
p1, p2, n = ra, 2 * ra, (cA[1] + cB[1]) / 2
pbar = (p1 + p2) / 2
zb = (abs(p2 - p1) * math.sqrt(n) - 1.96 * math.sqrt(2 * pbar * (1 - pbar))) / math.sqrt(
    p1 * (1 - p1) + p2 * (1 - p2)
)
print("power to detect doubling of refund rate", 1 - a.norm_sf(zb))
r = list(csv.DictReader(open(MAT + "/benchmark.csv")))
o = np.array([float(x["load_ms_old"]) for x in r])
nw = np.array([float(x["load_ms_new"]) for x in r])
dd = nw - o
zp = dd.mean() / (dd.std(ddof=1) / math.sqrt(40))
print("paired z", zp, "p", a.two_sided(zp), "mean diff", dd.mean(), "share slower", (dd > 0).mean())
ps = sorted(
    a.two_sided(a.welch_z(m1, s1, n1, m2, s2, n2))
    for (n1, m1, s1), (n2, m2, s2) in a.METRICS.values()
)
print("metric ps", [round(x, 4) for x in ps], "bonferroni thr", 0.05 / 6)
segsum = np.array([s[2:] for s in a.SEGMENTS]).sum(0)
print("segment sums", segsum, "vs day9", cA[:2], cB[:2])
