"""Wall time when K interpreters start at the same moment (process-creation contention).

Source of the "1 / 13 / 30 processes" table in docs/perf/REPORT.md.

    python docs/perf/adhoc/process_start_contention.py <path to python.exe>

Measured 2026-10-13, Windows 11, 24 CPUs, Python 3.11.13, median of 15 bursts (ms):

      K    plain      -S
      1       53      25
      2       57      27
      4       65      31
      8       81      37
     13       96      50
     18      114      64
     30      192      96
"""

import concurrent.futures as cf
import os
import statistics
import subprocess
import sys
import time

py = sys.argv[1] if len(sys.argv) > 1 else sys.executable
env = dict(os.environ)
env.pop("CLAUDE_INVOKED_BY", None)


def one(args):
    t = time.perf_counter()
    subprocess.run([py, *args], capture_output=True, env=env)
    return (time.perf_counter() - t) * 1000


def burst(k, args):
    t = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=k) as ex:
        list(ex.map(lambda _: one(args), range(k)))
    return (time.perf_counter() - t) * 1000


print("wall ms for K simultaneous no-op launches (median of 15)")
print(f"{'K':>3} {'plain':>8} {'-S':>8}")
for k in (1, 2, 4, 8, 13, 18, 30):
    row = []
    for args in (["-c", "pass"], ["-S", "-c", "pass"]):
        burst(k, args)  # warm-up burst
        row.append(statistics.median(burst(k, args) for _ in range(15)))
    print(f"{k:>3} {row[0]:>8.0f} {row[1]:>8.0f}")
