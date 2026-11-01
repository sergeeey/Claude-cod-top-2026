"""Model of the gain from an `if` condition on hooks that only matter for one file.

Source of the "Edit|Write, all hooks vs always-on hooks" figures in docs/perf/REPORT.md.
This is a MODEL: it simply leaves the path-scoped hooks out of the group. It does not
run Claude Code, and it does not prove that the `if` rules would be matched as intended.

    python docs/perf/adhoc/if_gating_model.py <path to python.exe>

Measured 2026-10-13, Windows 11, 24 CPUs, Python 3.11.13, 20 paired rounds, order alternated:

    PreToolUse  Edit|Write: all=8 hooks,  always-on=6 hooks:  128 ms vs 118 ms  (-7.8%)
    PostToolUse Edit|Write: all=19 hooks, always-on=11 hooks: 234 ms vs 197 ms  (-15.9%)

Second run, with a full pytest running in the background (higher machine load):
    PreToolUse -6.2%, PostToolUse -23.1%. Run-to-run spread is real: quote the range.
"""

import concurrent.futures as cf
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import bench_hooks as bh  # noqa: E402

PY = [sys.argv[1] if len(sys.argv) > 1 else sys.executable]
settings = json.loads((ROOT / "hooks" / "settings.json").read_text(encoding="utf-8"))

# Hooks whose own code returns at once unless the edited file is one specific file
# (activeContext.md, experiments/*/decision.md, claim.md, dependency_graph.yaml,
# mutation_suite.yaml, sealed_holdout.yaml, null_results/INDEX.md).
PATH_SCOPED = {
    "activeContext_hygiene.py",
    "experiment_insight.py",
    "claim_entropy_tracker.py",
    "promotion_gate_guard.py",
    "reject_gate_guard.py",
    "independence_scorer.py",
    "mutation_tracker.py",
    "sealed_holdout_guard.py",
    "null_retroscan.py",
}


def members_for(event, matcher, tmp):
    workdir = Path(tmp) / "work"
    bh.init_workdir(workdir)
    (Path(tmp) / "home").mkdir(exist_ok=True)
    env = bh.make_env(Path(tmp) / "home")
    out = []
    for row in bh.collect_commands(settings):
        if row["event"] == event and row["matcher"] == matcher:
            argv = bh.resolve_command(row["command"], PY, ROOT)
            payload = bh.build_payload(event, bh.pick_tool(matcher), workdir)
            out.append((bh.script_name(argv), argv, payload))
    return out, env, workdir


def wall(members, env, workdir):
    t = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=len(members)) as ex:
        list(ex.map(lambda m: bh.run_once(m[1], m[2], env, workdir, 30.0), members))
    return (time.perf_counter() - t) * 1000


with tempfile.TemporaryDirectory() as tmp:
    for event in ("PreToolUse", "PostToolUse"):
        members, env, workdir = members_for(event, "Edit|Write", tmp)
        kept = [m for m in members if m[0] not in PATH_SCOPED]
        print(f"{event} Edit|Write: all={len(members)} hooks, always-on={len(kept)} hooks")
        a, b = [], []
        for i in range(21):
            order = ((members, a), (kept, b)) if i % 2 == 0 else ((kept, b), (members, a))
            for group, acc in order:
                w = wall(group, env, workdir)
                if i >= 1:  # round 0 is warm-up
                    acc.append(w)
        ma, mb = statistics.median(a), statistics.median(b)
        print(
            f"   parallel wall median: all {ma:.0f} ms  vs  always-on only {mb:.0f} ms"
            f"  ({(mb - ma) / ma * 100:+.1f}%)"
        )
