#!/usr/bin/env python3
"""Sequential profile of hooks: floor, per-hook wall, CPU, memory and import self-time.

No concurrency here, so the numbers are clean per process. Use it to find where a hook's
time goes before reaching for the A/B stand (scripts/latency_stand.py). Import self-time comes
from `python -X importtime`; the hook bodies can be checked with cProfile on the same child.

Usage: latency_profile.py --python <python 3.11> --hooks <hooks_dir> [--reps 3]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latency_stand as ls  # noqa: E402

IMPORT_RE = re.compile(r"import time:\s+(\d+) \|\s+(\d+) \|\s*(.*)")


def median_of(rows: list[dict], key: str) -> float | None:
    values = [r[key] for r in rows if r[key] is not None]
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--python", required=True)
    parser.add_argument("--hooks", required=True, type=Path)
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()
    args.hooks = (
        args.hooks.resolve()
    )  # the child runs in a fixture repo, so a relative path would not resolve
    manifest = json.loads((args.hooks / "settings.json").read_text(encoding="utf-8"))
    work = Path(tempfile.mkdtemp(prefix="latency-profile-"))
    sess = ls.Session(work / "s", "profile")
    noop_dir = work / "noop"
    noop_dir.mkdir()
    (noop_dir / "noop.py").write_text("pass\n", encoding="utf-8")
    shape_by_name = {s.name: s for s in ls.SHAPES}

    def one(shape_name: str, hook_dir: Path, name: str) -> dict:
        _phase, records = ls.run_phase(
            args.python, hook_dir, [name], shape_by_name[shape_name], sess
        )
        record: dict = records[0]
        return record

    def import_self(shape_name: str, name: str) -> tuple[float, dict[str, float]]:
        stats = work / f"imp-{uuid.uuid4().hex}.txt"
        sess.reset()
        payload = ls.payload_for(shape_by_name[shape_name], sess.repo, sess.sid)
        proc = subprocess.run(
            [
                args.python,
                "-S",
                "-X",
                "importtime",
                str(ls.CHILD),
                "--hook",
                str(args.hooks / name),
                "--stats",
                str(stats),
            ],
            input=payload,
            capture_output=True,
            cwd=str(sess.repo),
            env=sess.env,
        )
        total = 0.0
        per_module: dict[str, float] = defaultdict(float)
        for line in proc.stderr.decode("utf-8", "replace").splitlines():
            m = IMPORT_RE.match(line)
            if m:
                self_ms = int(m.group(1)) / 1000
                total += self_ms
                per_module[m.group(3).strip()] += self_ms
        return total, dict(per_module)

    floor = [one("prompt", noop_dir, "noop.py") for _ in range(10)]
    print(
        f"floor (empty hook): wall {median_of(floor, 'wall_ms'):.1f} ms, "
        f"cpu {median_of(floor, 'cpu_ms'):.1f} ms, rss {median_of(floor, 'peak_mb'):.1f} MB"
    )
    module_totals: dict[str, float] = defaultdict(float)
    print(f"{'shape':<11}{'hook':<34}{'wall':>8}{'cpu':>8}{'rssMB':>8}{'import_self':>13}")
    for shape_name in ("prompt", "pre_edit", "post_edit", "post_bash"):
        for name in ls.select_hooks(manifest, shape_by_name[shape_name]):
            rows = [one(shape_name, args.hooks, name) for _ in range(args.reps)]
            imp_total, per_module = import_self(shape_name, name)
            for mod, ms in per_module.items():
                module_totals[mod] += ms
            print(
                f"{shape_name:<11}{name:<34}{median_of(rows, 'wall_ms'):>8.1f}"
                f"{median_of(rows, 'cpu_ms'):>8.1f}{median_of(rows, 'peak_mb'):>8.1f}"
                f"{imp_total:>13.1f}"
            )
    print("module self-time summed over the profiled hooks (ms):")
    for mod, ms in sorted(module_totals.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {ms:9.1f}  {mod}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
