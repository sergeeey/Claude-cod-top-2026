import json
import os
import subprocess
import sys

MAT = sys.argv[1]
SCRIPT = os.path.join(MAT, "run_experiment.py")
OUT = os.path.join(MAT, "results.json")

RUNNER = r"""
import glob, random, runpy, sys
seed, order, script = sys.argv[1], sys.argv[2], sys.argv[3]
if seed != "none":
    random.seed(int(seed))
orig = glob.glob
if order == "fwd":
    glob.glob = lambda p, *a, **k: sorted(orig(p, *a, **k))
elif order == "rev":
    glob.glob = lambda p, *a, **k: sorted(orig(p, *a, **k), reverse=True)
runpy.run_path(script, run_name="__main__")
"""
runner_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runner.py")
with open(runner_path, "w", encoding="utf-8") as fh:
    fh.write(RUNNER)


def run(hashseed, pyseed, order):
    env = dict(os.environ, PYTHONHASHSEED=str(hashseed))
    out = subprocess.run(
        [sys.executable, runner_path, pyseed, order, SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    with open(OUT, encoding="utf-8") as fh:
        res = json.load(fh)
    lines = [l for l in out.splitlines() if not l.startswith("elapsed")]
    return res, "\n".join(lines)


def sig(res):
    return (
        res["effect"],
        tuple(sorted((g, d["ci_low"], d["ci_high"]) for g, d in res["groups"].items())),
    )


print("A: plain glob, unseeded random, hash=0 x3 -> effect")
print([run(0, "none", "native")[0]["effect"] for _ in range(3)])

print("B: random seeded, fwd glob, hash 0..5 -> effect, group key order, CI sig distinct")
sigs, orders, effects = set(), set(), set()
for h in range(6):
    r, _ = run(h, "1", "fwd")
    effects.add(r["effect"])
    orders.add(tuple(r["groups"]))
    sigs.add(sig(r))
print("effects:", effects, "key orders:", len(orders), "CI signatures:", len(sigs))

print("C: random seeded, hash 0, fwd vs rev glob -> effect")
print(run(0, "1", "fwd")[0]["effect"], run(0, "1", "rev")[0]["effect"])

print("D: everything fixed, two runs -> stdout equal, json equal except run_at")
r1, o1 = run(0, "1", "fwd")
r2, o2 = run(0, "1", "fwd")
print("stdout equal:", o1 == o2)
r1.pop("run_at")
r2.pop("run_at")
print("json equal sans run_at:", r1 == r2, "| data_dir in json:", "data_dir" in r1)
print("native glob order:", sorted(os.listdir(os.path.join(MAT, "data"))))
os.remove(OUT)
os.remove(runner_path)
