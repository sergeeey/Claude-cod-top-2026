import os
import sys

import numpy as np

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
rng = np.random.default_rng(3)
mu = {"control": 10.0, "placebo": 10.4, "treatment": 11.2}
off = {"site_a": 0.0, "site_b": 0.6, "site_c": -0.4}
for site in ["site_a", "site_b", "site_c"]:
    with open(os.path.join(out, site + ".csv"), "w", newline="", encoding="utf-8") as f:
        f.write("group,value\n")
        for _ in range(30):
            g = ["control", "placebo", "treatment"][int(rng.integers(0, 3))]
            f.write(f"{g},{rng.normal(mu[g] + off[site], 1.5):.3f}\n")
