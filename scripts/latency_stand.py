#!/usr/bin/env python3
"""Load stand for the hook critical path: latency tails, CPU, memory and throughput.

WHY: a tool call waits for the hooks of its event. Each hook is a separate Python process,
and the hooks of one event start together, so the wait is set by the slowest hook of the
group plus the cost of starting many processes at once. scripts/bench_hooks.py (origin/main)
measures one group at a time and reports medians. This stand starts the hooks of one turn
shape together, the way the harness does, and reports p50/p95/p99 of the phase wall time,
the tails of each hook, CPU time, peak working set and throughput with several sessions.

WHAT: for every session it builds a fixture git repository and an isolated HOME, then replays
fixed payloads for seven turn shapes. Two code trees ("arms") run interleaved sample by sample,
so machine drift hits both arms alike. Async hooks (their work runs in the background, the
user does not wait for it) and hooks that reach the network or a package manager are left out.

REPRODUCE:
    python scripts/latency_stand.py --python <python 3.11> --arm before=<tree_a>/hooks \
        --arm after=hooks --samples 100 --out artifacts/latency/run.json
    python scripts/latency_stand.py --python <python 3.11> --sessions 4 --samples 30 \
        --arm before=<tree_a>/hooks --arm after=hooks --out artifacts/latency/load4.json
    python scripts/latency_stand.py --compare artifacts/latency/run.json

METRICS: percentiles use the nearest-rank method. The phase wall time runs from the first
process start to the last process exit. The ratio of after to before comes with a 95 % bootstrap
interval from paired resampling (fixed seed). CPU is the child's own user plus system time
(os.times, read at exit). Memory is the peak resident set of each child, sampled from the parent
with psutil every 2 ms. Neither needs an import inside the hook process, so the stand adds no
modules to what a hook loads. Background work left by async hooks is not counted in either.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

SCRIPT_DIR = Path(__file__).resolve().parent
CHILD = SCRIPT_DIR / "latency_child.py"
SKIP_ALWAYS = frozenset({"webhook_notify.py", "gitnexus_reindex.py"})

FIXTURE_FILES = {
    ".claude/memory/activeContext.md": "# activeContext\n\n## Auto-commit log\n"
    "- [2026-10-16 09:00] `abc1234`: seed\n",
    ".claude/memory/decisions.md": "# Decisions\n",
    "src/mod.py": "def add(a, b):\n    return a + b\n",
    "tests/test_mod.py": "from src.mod import add\n\n\ndef test_add():\n"
    "    assert add(1, 2) == 3\n",
}


@dataclass(frozen=True)
class Shape:
    name: str
    event: str
    tool: str | None
    phase: str  # "prompt", "pre" or "post": which side of the tool call


SHAPES = (
    Shape("prompt", "UserPromptSubmit", None, "prompt"),
    Shape("pre_bash", "PreToolUse", "Bash", "pre"),
    Shape("pre_commit", "PreToolUse", "Bash", "pre"),
    Shape("post_bash", "PostToolUse", "Bash", "post"),
    Shape("post_commit", "PostToolUse", "Bash", "post"),
    Shape("pre_edit", "PreToolUse", "Edit", "pre"),
    Shape("post_edit", "PostToolUse", "Edit", "post"),
)


def payload_for(shape: Shape, repo: Path, session_id: str) -> bytes:
    """Fixed stdin payload for a shape. Commands and paths never change between runs."""
    base = {"session_id": session_id, "cwd": str(repo)}
    commit_cmd = "git commit -m 'feat: add mod'"
    data: dict[str, Any]
    if shape.name == "prompt":
        data = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Проверь, что тесты модуля mod проходят, и сформулируй вывод",
        }
    elif shape.name in ("pre_bash", "pre_commit"):
        cmd = commit_cmd if shape.name == "pre_commit" else "ls -la src"
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
        }
    elif shape.name in ("post_bash", "post_commit"):
        cmd = commit_cmd if shape.name == "post_commit" else "python -m pytest tests -q"
        out = "[main abc1234] feat: add mod" if shape.name == "post_commit" else "1 passed"
        data = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
            "tool_response": {"stdout": out, "stderr": "", "exit_code": 0},
        }
    elif shape.name == "pre_edit":
        data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(repo / "src" / "mod.py"),
                "old_string": "return a + b",
                "new_string": "return a + b  # sum",
            },
        }
    else:  # post_edit
        data = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(repo / "src" / "mod.py"),
                "old_string": "return a + b",
                "new_string": "return a + b  # sum",
            },
            "tool_response": {"success": True},
        }
    return json.dumps({**base, **data}, ensure_ascii=False).encode("utf-8")


def matcher_hits(matcher: str, tool: str | None) -> bool:
    if matcher in ("", "*"):
        return True
    if tool is None:
        return False
    return any(fnmatch.fnmatchcase(tool, alt.strip()) for alt in matcher.split("|"))


def select_hooks(manifest: dict, shape: Shape, skip: frozenset[str] = frozenset()) -> list[str]:
    """Script names that the manifest runs for this shape, one entry per registration.

    skip drops the named scripts. It exists for the gating what-if (--gate), never for the
    manifest itself.
    """
    names: list[str] = []
    for group in manifest.get("hooks", {}).get(shape.event, []):
        if not matcher_hits(str(group.get("matcher", "")), shape.tool):
            continue
        for hook in group.get("hooks", []):
            command = str(hook.get("command", ""))
            if "async_wrapper" in command:
                continue  # background by design, not on the user's critical path
            targets = [Path(t).name for t in command.replace('"', " ").split() if t.endswith(".py")]
            if not targets or targets[-1] in SKIP_ALWAYS or targets[-1] in skip:
                continue
            names.append(targets[-1])
    return names


class Session:
    """A fixture repository and an isolated HOME. Reset before every phase."""

    def __init__(self, root: Path, sid: str) -> None:
        self.root = root
        self.sid = sid
        self.repo = root / "repo"
        self.home = root / "home"
        self.repo.mkdir(parents=True)
        self.home.mkdir(parents=True)
        for rel, text in FIXTURE_FILES.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(text, encoding="utf-8")
        git = ["git", "-c", "user.name=stand", "-c", "user.email=stand@example.invalid"]
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run([*git, "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run([*git, "-C", str(self.repo), "commit", "-q", "-m", "feat: seed"], check=True)
        self.env = dict(os.environ)
        self.env.update(
            HOME=str(self.home),
            USERPROFILE=str(self.home),
            APPDATA=str(self.home / "AppData" / "Roaming"),
            LOCALAPPDATA=str(self.home / "AppData" / "Local"),
            PYTHONUTF8="1",
        )
        self.env.pop("CLAUDE_INVOKED_BY", None)

    def reset(self) -> None:
        """Restore the memory files and drop the state written by earlier phases."""
        for rel, text in FIXTURE_FILES.items():
            if rel.startswith(".claude/memory/"):
                (self.repo / rel).write_text(text, encoding="utf-8")
        shutil.rmtree(self.repo / ".claude" / "state", ignore_errors=True)
        shutil.rmtree(self.home, ignore_errors=True)
        self.home.mkdir(parents=True, exist_ok=True)
        self.env["HOME"] = str(self.home)
        self.env["USERPROFILE"] = str(self.home)


def _sample_rss(pid: int, peak: list[int], stop: threading.Event) -> None:
    """Track the peak resident set of one child until stop is set (parent side)."""
    try:
        proc = psutil.Process(pid)
    except psutil.Error:
        return
    while not stop.is_set():
        try:
            rss = proc.memory_info().rss
        except psutil.Error:
            return
        if rss > peak[0]:
            peak[0] = rss
        stop.wait(0.002)


def run_phase(
    python: str,
    hooks_dir: Path,
    names: list[str],
    shape: Shape,
    session: Session,
) -> tuple[float, list[dict]]:
    """Start the hooks of one shape together and wait for all of them."""
    session.reset()
    payload = payload_for(shape, session.repo, session.sid)
    records: list[dict] = []
    guard = threading.Lock()
    t0 = time.perf_counter()

    def worker(name: str) -> None:
        stats = session.root / f"stats-{uuid.uuid4().hex}.json"
        launched = time.perf_counter()
        proc = subprocess.Popen(
            [
                python,
                "-S",
                str(CHILD),
                "--hook",
                str(hooks_dir / name),
                "--stats",
                str(stats),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(session.repo),
            env=session.env,
        )
        spawned = time.perf_counter()  # the parent's Popen call returned: the child is running
        peak = [0]
        stop = threading.Event()
        sampler = threading.Thread(target=_sample_rss, args=(proc.pid, peak, stop), daemon=True)
        sampler.start()
        out, _err = proc.communicate(payload)
        stop.set()
        sampler.join()
        done = time.perf_counter()
        record: dict = {
            "hook": name,
            "wall_ms": (done - launched) * 1000,
            "end_ms": (done - t0) * 1000,
            "spawned_ms": (spawned - t0) * 1000,
            "rc": proc.returncode,
            "stdout_bytes": len(out),
            "cpu_ms": None,
            "peak_mb": peak[0] / (1024 * 1024) if peak[0] else None,
            "hook_exit": None,
        }
        try:
            cpu_text, code_text = stats.read_text(encoding="ascii").split()
            record.update(cpu_ms=float(cpu_text), hook_exit=int(code_text))
        except (OSError, ValueError):
            pass  # no stats: os._exit path, counted as missing
        with guard:
            records.append(record)

    threads = [threading.Thread(target=worker, args=(n,)) for n in names]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    phase_ms = max((r["end_ms"] for r in records), default=0.0)
    return phase_ms, records


def pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize_phases(phases: list[float]) -> dict:
    return {
        "n": len(phases),
        "p50_ms": pct(phases, 50),
        "p95_ms": pct(phases, 95),
        "p99_ms": pct(phases, 99),
        "mean_ms": statistics.fmean(phases) if phases else None,
        "max_ms": max(phases) if phases else None,
    }


def paired_ratio_ci(before: list[float], after: list[float], q: float) -> dict:
    """Ratio after/before of a percentile, with a 95 % bootstrap interval over samples."""
    rng = random.Random(20261017)
    n = len(before)
    base = pct(before, q)
    point = pct(after, q)
    ratios: list[float] = []
    for _ in range(2000):
        idx = [rng.randrange(n) for _ in range(n)]
        pb = pct([before[i] for i in idx], q)
        pa = pct([after[i] for i in idx], q)
        if pb and pa:
            ratios.append(pa / pb)
    ratios.sort()
    lo = ratios[int(0.025 * (len(ratios) - 1))] if ratios else None
    hi = ratios[int(0.975 * (len(ratios) - 1))] if ratios else None
    return {
        "ratio": (point / base) if base and point else None,
        "ci95": [lo, hi],
    }


def aggregate(samples: dict, arms: list[str], shapes: list[str]) -> dict:
    """Summaries per arm and shape: phase percentiles, per-hook tails, CPU and memory."""
    out: dict = {}
    for arm in arms:
        out[arm] = {}
        for shape in shapes:
            rows = samples[arm].get(shape, [])
            phases = [r["phase_ms"] for r in rows]
            # exec part of the phase: from the last Popen returning to the last exit
            execs = [
                r["phase_ms"] - max(h["spawned_ms"] for h in r["hooks"]) for r in rows if r["hooks"]
            ]
            hook_rows = [h for r in rows for h in r["hooks"]]
            per_hook: dict[str, dict] = {}
            for name in sorted({h["hook"] for h in hook_rows}):
                walls = [h["wall_ms"] for h in hook_rows if h["hook"] == name]
                cpus = [h["cpu_ms"] for h in hook_rows if h["hook"] == name and h["cpu_ms"]]
                peaks = [h["peak_mb"] for h in hook_rows if h["hook"] == name and h["peak_mb"]]
                per_hook[name] = {
                    "p50_ms": pct(walls, 50),
                    "p95_ms": pct(walls, 95),
                    "p99_ms": pct(walls, 99),
                    "cpu_ms_mean": statistics.fmean(cpus) if cpus else None,
                    "peak_mb_mean": statistics.fmean(peaks) if peaks else None,
                }
            sums_cpu = [sum(h["cpu_ms"] or 0 for h in r["hooks"]) for r in rows]
            sums_peak = [sum(h["peak_mb"] or 0 for h in r["hooks"]) for r in rows]
            errors = sum(1 for h in hook_rows if h["rc"] != 0)
            missing = sum(1 for h in hook_rows if h["cpu_ms"] is None)
            out[arm][shape] = {
                "phase": summarize_phases(phases),
                "exec": summarize_phases(execs),
                "hooks_per_phase": len(hook_rows) / len(rows) if rows else 0,
                "cpu_ms_per_phase_mean": statistics.fmean(sums_cpu) if sums_cpu else None,
                "peak_mb_sum_per_phase_p95": pct(sums_peak, 95),
                "errors": errors,
                "stats_missing": missing,
                "per_hook": per_hook,
            }
    return out


def gated_names(
    manifest: dict, args: argparse.Namespace, arms: dict[str, Path]
) -> dict[str, dict[str, list[str]]]:
    """Hook names per arm and shape. --gate ARM:SHAPE=hook.py,... drops those hooks for that arm."""
    gates: dict[tuple[str, str], frozenset[str]] = {}
    for item in args.gate:
        head, _, names = item.partition("=")
        arm, _, shape = head.partition(":")
        gates[(arm, shape)] = frozenset(n.strip() for n in names.split(",") if n.strip())
    return {
        arm: {
            s.name: select_hooks(manifest, s, gates.get((arm, s.name), frozenset())) for s in SHAPES
        }
        for arm in arms
    }


def run_sequential(args: argparse.Namespace, manifest: dict, arms: dict[str, Path]) -> dict:
    """One session per arm; samples interleave arms and shapes so drift hits all alike."""
    workdir = Path(tempfile.mkdtemp(prefix="latency-"))
    sessions = {name: Session(workdir / name, f"sid-{name}") for name in arms}
    base_names = {s.name: select_hooks(manifest, s) for s in SHAPES}
    names_by_arm = gated_names(manifest, args, arms)
    shapes = [s for s in SHAPES if base_names[s.name]]
    samples: dict = {arm: {s.name: [] for s in shapes} for arm in arms}
    arm_names = list(arms)
    for _ in range(args.warmup):
        for s in shapes:
            for arm in arm_names:
                run_phase(args.python, arms[arm], names_by_arm[arm][s.name], s, sessions[arm])
    for i in range(args.samples):
        for k, s in enumerate(shapes):
            order = arm_names if (i + k) % 2 == 0 else list(reversed(arm_names))
            for arm in order:
                phase_ms, hooks = run_phase(
                    args.python, arms[arm], names_by_arm[arm][s.name], s, sessions[arm]
                )
                samples[arm][s.name].append({"phase_ms": phase_ms, "hooks": hooks})
    shutil.rmtree(workdir, ignore_errors=True)
    return {
        "mode": "sequential",
        "samples_per_shape": args.samples,
        "shapes": {s.name: base_names[s.name] for s in shapes},
        "samples": samples,
    }


def run_load(args: argparse.Namespace, manifest: dict, arms: dict[str, Path]) -> dict:
    """Several sessions at once: each thread runs its own fixture per arm."""
    workdir = Path(tempfile.mkdtemp(prefix="latency-load-"))
    base_names = {s.name: select_hooks(manifest, s) for s in SHAPES}
    names_by_arm = gated_names(manifest, args, arms)
    shapes = [s for s in SHAPES if base_names[s.name]]
    arm_names = list(arms)
    samples: dict = {arm: {s.name: [] for s in shapes} for arm in arm_names}
    guard = threading.Lock()
    counts = {"phases": 0, "hooks": 0}

    def session_loop(c: int) -> None:
        sessions = {arm: Session(workdir / f"s{c}-{arm}", f"sid-{arm}-{c}") for arm in arm_names}
        for i in range(args.samples):
            for k, s in enumerate(shapes):
                order = arm_names if (i + k + c) % 2 == 0 else list(reversed(arm_names))
                for arm in order:
                    phase_ms, hooks = run_phase(
                        args.python, arms[arm], names_by_arm[arm][s.name], s, sessions[arm]
                    )
                    with guard:
                        samples[arm][s.name].append({"phase_ms": phase_ms, "hooks": hooks})
                        counts["phases"] += 1
                        counts["hooks"] += len(hooks)

    started = time.perf_counter()
    threads = [threading.Thread(target=session_loop, args=(c,)) for c in range(args.sessions)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - started
    shutil.rmtree(workdir, ignore_errors=True)
    return {
        "mode": "load",
        "sessions": args.sessions,
        "samples_per_session_shape": args.samples,
        "shapes": {s.name: base_names[s.name] for s in shapes},
        "samples": samples,
        "throughput": {
            "elapsed_s": round(elapsed, 2),
            "phases": counts["phases"],
            "hook_processes": counts["hooks"],
            "phases_per_s": counts["phases"] / elapsed,
            "hook_processes_per_s": counts["hooks"] / elapsed,
        },
    }


def report(result: dict, arm_names: list[str]) -> dict:
    shapes = list(result["shapes"])
    agg = aggregate(result["samples"], arm_names, shapes)
    out = {"aggregate": agg}
    if len(arm_names) == 2:
        before, after = arm_names
        comparisons: dict = {}
        for shape in shapes:
            b = [r["phase_ms"] for r in result["samples"][before][shape]]
            a = [r["phase_ms"] for r in result["samples"][after][shape]]
            if not b or not a:
                continue
            comparisons[shape] = {
                q: paired_ratio_ci(b, a, qv) for q, qv in (("p50", 50), ("p95", 95), ("p99", 99))
            }
        out["after_over_before"] = comparisons
    return out


def print_comparison(data: dict) -> None:
    arms = list(data["aggregate"])
    print(
        f"{'shape':<12}{'arm':<10}{'p50':>8}{'p95':>8}{'p99':>8}{'cpu/phase':>12}{'peakMB/sum':>12}"
    )
    for shape in data["aggregate"][arms[0]]:
        for arm in arms:
            row = data["aggregate"][arm].get(shape)
            if not row:
                continue
            ph = row["phase"]
            print(
                f"{shape:<12}{arm:<10}{ph['p50_ms']:>8.0f}{ph['p95_ms']:>8.0f}{ph['p99_ms']:>8.0f}"
                f"{(row['cpu_ms_per_phase_mean'] or 0):>12.0f}"
                f"{(row['peak_mb_sum_per_phase_p95'] or 0):>12.0f}"
            )
    for shape, cmp in data.get("after_over_before", {}).items():
        parts = []
        for q in ("p50", "p95", "p99"):
            r = cmp[q]
            if r["ratio"] is not None:
                lo, hi = r["ci95"]
                parts.append(f"{q} x{r['ratio']:.2f} [{lo:.2f}; {hi:.2f}]")
        print(f"{shape:<12} after/before: " + "  ".join(parts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--python", help="interpreter for the hooks (Python 3.11 env)")
    parser.add_argument("--arm", action="append", default=[], metavar="NAME=HOOKS_DIR")
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--sessions", type=int, default=1)
    parser.add_argument("--out")
    parser.add_argument("--compare", metavar="JSON")
    parser.add_argument(
        "--gate",
        action="append",
        default=[],
        metavar="ARM:SHAPE=HOOK.py,...",
        help="what-if only: drop these hooks for one arm and shape (never applied to the manifest)",
    )
    args = parser.parse_args()

    if args.compare:
        print_comparison(json.loads(Path(args.compare).read_text(encoding="utf-8"))["report"])
        return 0
    if not args.python or not args.arm:
        parser.error("--python and at least one --arm are required")
    arms: dict[str, Path] = {}
    for item in args.arm:
        name, _, path = item.partition("=")
        arms[name] = Path(path).resolve()
    manifest_path = next(iter(arms.values())) / "settings.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for arm_dir in arms.values():
        for s in SHAPES:
            for name in select_hooks(manifest, s):
                if not (arm_dir / name).exists():
                    parser.error(f"{arm_dir / name} is missing")

    started = time.time()
    result = (
        run_load(args, manifest, arms)
        if args.sessions > 1
        else run_sequential(args, manifest, arms)
    )
    result["started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    result["python"] = args.python
    result["platform"] = sys.platform
    result["arms"] = {name: str(path) for name, path in arms.items()}
    result["report"] = report(result, list(arms))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print_comparison(result["report"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
