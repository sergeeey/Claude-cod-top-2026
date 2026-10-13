#!/usr/bin/env python3
"""Measure the wall-clock cost of every hook command in a settings manifest.

WHY: a Claude Code session runs 13 hook processes per user message, 18
per Bash call and 30 per Edit/Write (counts from hooks/settings.json).
Each is a fresh Python process, so the cost is paid on every turn. Nothing in
the repo measured it, so any "make hooks faster" claim had no baseline.

WHAT it does: for each (event, matcher) group in the manifest it runs every
command with a representative stdin payload, ``--runs`` times after
``--warmup`` discarded runs, and reports per-hook median / p90 / min wall time.
It also launches the whole group concurrently once per round (``group_parallel``)
because the harness runs the matching hooks of an event together; the
sequential sum is reported next to it so the reader can see the spread.

ISOLATION: HOME / USERPROFILE / APPDATA point at a throwaway directory and the
working directory is a throwaway git repo, so hooks cannot read or write the
real ``~/.claude`` state or the real repo. This also means hooks that read
real state (a knowledge graph, the thread database) do less work than in a
live session: the numbers are a floor for those hooks, not a ceiling.

REPRODUCE:
    python scripts/bench_hooks.py --runs 7 --out docs/perf/hook_bench_<tag>.json
    python scripts/bench_hooks.py --compare docs/perf/before.json docs/perf/after.json

Not measured: the harness's own spawn overhead, hook stdout parsing, and
anything that depends on a real session's state.

METRIC NOTE: ``parallel_wall_ms`` of a turn shape is the SLOWEST group of each
phase (Pre, Post), summed over the phases. Groups are measured one at a time,
so the contention of several groups of one phase starting together is not
included; the figure understates the real wait. It is fair for comparing two
variants measured the same way (``--ab``), not as an absolute latency.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS = ROOT / "hooks" / "settings.json"
DEFAULT_TIMEOUT_S = 30.0
# WHY: these reach the network or spawn a package manager; a benchmark must
# not do either. They are listed in the report as "skipped", never dropped.
SKIP_BY_DEFAULT = frozenset({"webhook_notify.py", "gitnexus_reindex.py"})

# Representative tool names per matcher alternative (first alternative that
# is a real tool wins). Anything unknown falls back to the matcher text.
_TOOL_FOR_MATCHER = {
    "Bash": "Bash",
    "Edit": "Edit",
    "Write": "Write",
    "Read": "Read",
    "Grep": "Grep",
    "Glob": "Glob",
    "Agent": "Agent",
    "Skill": "Skill",
    "WebFetch": "WebFetch",
    "WebSearch": "WebSearch",
}


def pick_tool(matcher: str) -> str:
    """Return a concrete tool name that the matcher selects."""
    if not matcher or matcher == "*":
        return "Bash"
    first = matcher.split("|")[0]
    if first.endswith("*"):
        return first[:-1] + "bench_tool"
    return _TOOL_FOR_MATCHER.get(first, first)


def build_payload(event: str, tool: str, workdir: Path) -> dict:
    """A minimal but realistic stdin payload for one hook invocation."""
    base: dict[str, object] = {
        "hook_event_name": event,
        "session_id": "bench",
        "cwd": str(workdir),
    }
    sample = str(workdir / "sample.py")
    if event == "UserPromptSubmit":
        base["prompt"] = "fix the failing test in tests/test_parser.py and explain why it broke"
    elif event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        base["tool_name"] = tool
        if tool == "Bash":
            base["tool_input"] = {"command": "ls -la"}
        elif tool in ("Edit", "Write"):
            base["tool_input"] = {
                "file_path": sample,
                "content": "x = 1\n",
                "old_string": "x = 1",
                "new_string": "x = 2",
            }
        elif tool == "Agent":
            base["tool_input"] = {
                "subagent_type": "explorer",
                "prompt": "find where foo is defined",
            }
        elif tool == "Skill":
            base["tool_input"] = {"skill": "status"}
        elif tool in ("WebFetch", "WebSearch"):
            base["tool_input"] = {"url": "https://example.com", "query": "example"}
        elif tool in ("Read", "Grep", "Glob"):
            base["tool_input"] = {"file_path": sample, "pattern": "x"}
        else:
            base["tool_input"] = {"q": "example"}
        if event == "PostToolUse":
            base["tool_response"] = {"stdout": "ok", "stderr": "", "exit_code": 0, "returncode": 0}
    elif event == "SessionStart":
        base["source"] = "startup"
    elif event in ("Stop", "SubagentStop"):
        base["stop_hook_active"] = False
    return base


def resolve_command(cmd: str, python: str | list[str], claude_home: Path) -> list[str]:
    """Turn a manifest command into an argv list.

    The manifest uses ``__PYTHON_CMD__`` and ``__CLAUDE_HOME__`` placeholders
    (install-time substitution). A command that does not start with the python
    placeholder is returned as-is split on whitespace, never silently dropped.
    """
    cmd = cmd.replace("__CLAUDE_HOME__", claude_home.as_posix())
    parts = cmd.split()
    if parts and parts[0] == "__PYTHON_CMD__":
        return [*([python] if isinstance(python, str) else python), *parts[1:]]
    return parts


def script_name(argv: list[str]) -> str:
    for token in argv:
        m = re.search(r"([\w\-]+\.py)$", token)
        if m:
            return m.group(1)
    return " ".join(argv)[:40]


def collect_commands(settings: dict) -> list[dict]:
    """Flatten the manifest to (event, matcher, command) rows, order preserved."""
    rows = []
    for event, blocks in settings.get("hooks", {}).items():
        for block in blocks:
            matcher = block.get("matcher", "") or "*"
            for hook in block.get("hooks", []):
                if hook.get("type", "command") == "command":
                    rows.append({"event": event, "matcher": matcher, "command": hook["command"]})
    return rows


def run_once(argv: list[str], payload: dict, env: dict, cwd: Path, timeout: float) -> dict:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd),
            timeout=timeout,
        )
        rc, out = proc.returncode, len(proc.stdout)
        err = proc.stderr.strip().splitlines()[-1][:120] if proc.returncode and proc.stderr else ""
    except subprocess.TimeoutExpired:
        rc, out, err = -999, 0, "timeout"
    return {"ms": (time.perf_counter() - start) * 1000.0, "rc": rc, "stdout_bytes": out, "err": err}


def stats(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "median_ms": round(statistics.median(ordered), 1),
        "min_ms": round(ordered[0], 1),
        "p90_ms": round(ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))], 1),
        "n": len(ordered),
    }


def python_baseline(python: str, runs: int, env: dict, cwd: Path) -> dict:
    """Interpreter-only floor: what a hook costs before it does anything."""
    out = {}
    for label, args in (
        ("python -c pass", ["-c", "pass"]),
        ("python -S -c pass", ["-S", "-c", "pass"]),
    ):
        samples = []
        for _ in range(runs + 1):
            t = time.perf_counter()
            subprocess.run([python, *args], capture_output=True, env=env, cwd=str(cwd), timeout=30)
            samples.append((time.perf_counter() - t) * 1000.0)
        out[label] = stats(samples[1:])
    return out


def python_argv(args: argparse.Namespace) -> list[str]:
    """Interpreter plus optional flags, e.g. ["python", "-S"]."""
    return [args.python, *args.python_flags.split()]


def make_env(home: Path) -> dict:
    env = dict(os.environ)
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        env[key] = str(home)
    env.pop("CLAUDE_INVOKED_BY", None)  # the recursion guard would make hooks exit at once
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def init_workdir(workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "sample.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q"], cwd=str(workdir), capture_output=True, timeout=30)


def run_benchmark(args: argparse.Namespace, variants: dict[str, list[str]] | None = None) -> dict:
    """Measure every hook command. Returns ``{variant_name: report}``.

    With one variant (the default) this is a plain benchmark. With two or more
    (``--ab``), the variants are interleaved INSIDE each hook's and each group's
    run loop, and the order alternates every iteration. A plain "run A, then run
    B later" comparison measured a 17% effect as 30% in this repo's first
    attempt, because machine load drifted between the two runs; interleaving
    makes the drift hit every variant equally.
    """
    variants = variants or {"base": python_argv(args)}
    settings = json.loads(Path(args.settings).read_text(encoding="utf-8"))
    claude_home = Path(args.claude_home).resolve()
    rows = collect_commands(settings)
    if args.events:
        wanted = set(args.events)
        rows = [r for r in rows if r["event"] in wanted]

    with tempfile.TemporaryDirectory(prefix="bench_hooks_") as tmp:
        tmp_path = Path(tmp)
        home, workdir = tmp_path / "home", tmp_path / "work"
        home.mkdir()
        init_workdir(workdir)
        env = make_env(home)
        py_version = subprocess.run(
            [args.python, "-c", "import sys;print(sys.version.split()[0])"],
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()
        settings_label = (
            str(Path(args.settings).resolve().relative_to(ROOT))
            if Path(args.settings).resolve().is_relative_to(ROOT)
            else str(args.settings)
        )
        git_sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=str(ROOT)
        ).stdout.strip()
        reports: dict[str, dict] = {}
        for name, argv0 in variants.items():
            reports[name] = {
                "schema": 1,
                "variant": name,
                "environment": {
                    "python": args.python,
                    "python_flags": " ".join(argv0[1:]),
                    "python_version": py_version,
                    "platform": platform.platform(),
                    "cpu_count": os.cpu_count(),
                    "runs": args.runs,
                    "warmup": args.warmup,
                    "interleaved_variants": list(variants),
                    "settings": settings_label,
                    "git_sha": git_sha,
                },
                "baseline": python_baseline(args.python, args.runs, env, workdir),
                "hooks": [],
                "groups": [],
                "skipped": [],
            }

        groups: dict[tuple[str, str], list[dict]] = {}
        for row in rows:
            if not row["command"].lstrip().startswith("__PYTHON_CMD__"):
                for rep in reports.values():
                    rep["skipped"].append(
                        {
                            "event": row["event"],
                            "hook": row["command"][:40],
                            "reason": "non-python command",
                        }
                    )
                continue
            argvs = {
                n: resolve_command(row["command"], a0, claude_home) for n, a0 in variants.items()
            }
            name = script_name(next(iter(argvs.values())))
            if name in SKIP_BY_DEFAULT and not args.include_risky:
                for rep in reports.values():
                    rep["skipped"].append(
                        {"event": row["event"], "hook": name, "reason": "network/package manager"}
                    )
                continue
            tool = pick_tool(row["matcher"])
            groups.setdefault((row["event"], row["matcher"]), []).append(
                {
                    "argvs": argvs,
                    "name": name,
                    "payload": build_payload(row["event"], tool, workdir),
                    "tool": tool,
                }
            )

        names = list(variants)
        for (event, matcher), members in groups.items():
            per_hook: dict[str, dict[str, dict]] = {n: {} for n in names}
            for m in members:
                acc: dict[str, dict[str, list]] = {
                    n: {"ms": [], "rc": [], "out": [], "err": []} for n in names
                }
                for i in range(args.runs + args.warmup):
                    # parity counted from the first MEASURED iteration, so an odd number of
                    # runs is not biased towards one starting order
                    order = names if (i - args.warmup) % 2 == 0 else names[::-1]
                    for n in order:
                        r = run_once(m["argvs"][n], m["payload"], env, workdir, args.timeout)
                        if i >= args.warmup:
                            acc[n]["ms"].append(r["ms"])
                            acc[n]["rc"].append(r["rc"])
                            acc[n]["out"].append(r["stdout_bytes"])
                            acc[n]["err"].append(r["err"])
                for n in names:
                    a = acc[n]
                    entry = {
                        "event": event,
                        "matcher": matcher,
                        "tool": m["tool"],
                        "hook": m["name"],
                        **stats(a["ms"]),
                        "exit_codes": sorted(set(a["rc"])),
                        "stdout_bytes_max": max(a["out"]),
                        "stderr_tail": next((e for e in a["err"] if e), ""),
                    }
                    per_hook[n][m["name"]] = entry
                    reports[n]["hooks"].append(entry)

            wall: dict[str, list[float]] = {n: [] for n in names}
            for i in range(args.runs + args.warmup):
                order = names if (i - args.warmup) % 2 == 0 else names[::-1]
                for n in order:
                    t = time.perf_counter()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as pool:
                        list(
                            pool.map(
                                lambda mm, nn=n: run_once(
                                    mm["argvs"][nn], mm["payload"], env, workdir, args.timeout
                                ),
                                members,
                            )
                        )
                    if i >= args.warmup:
                        wall[n].append((time.perf_counter() - t) * 1000.0)
            for n in names:
                reports[n]["groups"].append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "hooks": len(members),
                        "sequential_sum_median_ms": round(
                            sum(h["median_ms"] for h in per_hook[n].values()), 1
                        ),
                        "group_parallel": stats(wall[n]),
                    }
                )
    return reports


def per_turn_totals(report: dict) -> dict:
    """Aggregate groups into the three turn shapes a user actually pays for."""

    def pick(event: str, matchers: tuple[str, ...]) -> list[dict]:
        return [g for g in report["groups"] if g["event"] == event and g["matcher"] in matchers]

    shapes = {
        "user_message": [pick("UserPromptSubmit", ("*",)) + pick("UserPromptSubmit", ("",))],
        "bash_call": [
            pick("PreToolUse", ("Bash", "Bash|Read|Grep|Glob", "*")),
            pick("PostToolUse", ("Bash", "*")),
        ],
        "edit_call": [
            pick("PreToolUse", ("Edit|Write", "*")),
            pick("PostToolUse", ("Edit|Write", "*")),
        ],
    }
    out = {}
    for shape, phases in shapes.items():
        groups = [g for phase in phases for g in phase]
        out[shape] = {
            "processes": sum(g["hooks"] for g in groups),
            "sequential_sum_ms": round(sum(g["sequential_sum_median_ms"] for g in groups), 1),
            "parallel_wall_ms": round(
                sum(
                    max([g["group_parallel"]["median_ms"] for g in phase] or [0.0])
                    for phase in phases
                ),
                1,
            ),
        }
    return out


def render_markdown(report: dict) -> str:
    env = report["environment"]
    lines = [
        f"Hook benchmark, {env['platform']}, Python {env['python_version']}, "
        f"{env['cpu_count']} CPU, runs={env['runs']}, sha={env['git_sha']}",
        "",
        "| baseline | median ms |",
        "|---|---|",
    ]
    for k, v in report["baseline"].items():
        lines.append(f"| {k} | {v['median_ms']} |")
    lines += [
        "",
        "| turn shape | processes | sequential sum ms | slowest group per phase, ms |",
        "|---|---|---|---|",
    ]
    for shape, v in per_turn_totals(report).items():
        lines.append(
            f"| {shape} | {v['processes']} | {v['sequential_sum_ms']} | {v['parallel_wall_ms']} |"
        )
    lines += ["", "| event | matcher | hook | median ms | p90 ms |", "|---|---|---|---|---|"]
    for h in sorted(report["hooks"], key=lambda x: -x["median_ms"])[:25]:
        lines.append(
            f"| {h['event']} | {h['matcher']} | {h['hook']} | {h['median_ms']} | {h['p90_ms']} |"
        )
    return "\n".join(lines)


def compare(before_path: str, after_path: str) -> str:
    a = json.loads(Path(before_path).read_text(encoding="utf-8"))
    b = json.loads(Path(after_path).read_text(encoding="utf-8"))
    return compare_reports(a, b)


def compare_reports(a: dict, b: dict) -> str:
    ta, tb = per_turn_totals(a), per_turn_totals(b)
    lines = ["| turn shape | metric | before ms | after ms | change |", "|---|---|---|---|---|"]
    for shape in ta:
        for metric in ("sequential_sum_ms", "parallel_wall_ms"):
            x, y = ta[shape][metric], tb[shape][metric]
            pct = (y - x) / x * 100 if x else 0.0
            lines.append(f"| {shape} | {metric} | {x} | {y} | {pct:+.1f}% |")
    key = lambda h: (h["event"], h["matcher"], h["hook"])  # noqa: E731
    before = {key(h): h["median_ms"] for h in a["hooks"]}
    rows = []
    for h in b["hooks"]:
        if key(h) in before and before[key(h)]:
            rows.append((h["median_ms"] - before[key(h)], key(h), before[key(h)], h["median_ms"]))
    lines += ["", "| hook | before ms | after ms | delta ms |", "|---|---|---|---|"]
    for delta, k, x, y in sorted(rows)[:10]:
        lines.append(f"| {k[0]}/{k[2]} | {x} | {y} | {delta:+.1f} |")
    return "\n".join(lines)


_VOLATILE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\w.+:-]*|\b\d{9,}\b|[0-9a-f]{32,}")


def _normalise(text: str) -> str:
    """Drop timestamps / ids / temp-dir names that legitimately differ between two runs."""
    text = re.sub(r"bench_verify_\w+", "<tmp>", text)
    return _VOLATILE.sub("<v>", text).replace("\r\n", "\n").strip()


def verify_flags(args: argparse.Namespace) -> int:
    """Differential test: same hook, same payload, fresh HOME, with vs without flags."""
    settings = json.loads(Path(args.settings).read_text(encoding="utf-8"))
    claude_home = Path(args.claude_home).resolve()
    plain = [args.python]
    flagged = [args.python, *args.verify_flags.split()]
    mismatches, nondeterministic, checked, skipped = [], [], 0, 0
    for row in collect_commands(settings):
        if not row["command"].lstrip().startswith("__PYTHON_CMD__"):
            skipped += 1
            continue
        results = []
        for interp in (plain, plain, flagged):  # plain twice = determinism control
            with tempfile.TemporaryDirectory(prefix="bench_verify_") as tmp:
                home, workdir = Path(tmp) / "home", Path(tmp) / "work"
                home.mkdir()
                init_workdir(workdir)
                argv = resolve_command(row["command"], interp, claude_home)
                payload = build_payload(row["event"], pick_tool(row["matcher"]), workdir)
                proc = subprocess.run(
                    argv,
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    env=make_env(home),
                    cwd=str(workdir),
                    timeout=args.timeout,
                )
                results.append((proc.returncode, _normalise(proc.stdout), _normalise(proc.stderr)))
        checked += 1
        if results[0] != results[1]:
            nondeterministic.append(script_name(argv))  # differs from itself: not evidence
        elif results[1] != results[2]:
            mismatches.append(
                {
                    "event": row["event"],
                    "hook": script_name(argv),
                    "plain": results[0],
                    "flagged": results[2],
                }
            )
    print(
        f"verified {checked} hook commands with {args.verify_flags!r} "
        f"(skipped {skipped} non-python)"
    )
    print(f"non-deterministic even without the flag (excluded): {sorted(set(nondeterministic))}")
    print(f"mismatches caused by the flag: {len(mismatches)}")
    for m in mismatches[:20]:
        print(json.dumps(m, ensure_ascii=False)[:400])
    return 1 if mismatches else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    p.add_argument(
        "--claude-home", default=str(ROOT), help="resolves __CLAUDE_HOME__ (default: this repo)"
    )
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--python-flags", default="", help='interpreter flags for the hooks, e.g. "-S"')
    p.add_argument(
        "--ab",
        metavar="FLAGS",
        help="interleave plain vs FLAGS inside one run (write --ab=-S); writes "
        "<out>.plain.json and <out>.flags.json and prints the paired comparison",
    )
    p.add_argument(
        "--verify-flags",
        metavar="FLAGS",
        help="do not time anything: run every hook with and without FLAGS "
        "in a fresh HOME each time "
        "and report any difference in exit code or stdout",
    )
    p.add_argument("--runs", type=int, default=7)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    p.add_argument("--events", nargs="*", help="limit to these events")
    p.add_argument(
        "--include-risky", action="store_true", help="also run network/package-manager hooks"
    )
    p.add_argument("--out", help="write the JSON report here")
    p.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = p.parse_args(argv)
    if (args.ab is not None or args.verify_flags is not None) and args.python_flags:
        p.error("--python-flags cannot be combined with --ab / --verify-flags (they set the flags)")
    if args.ab is not None and args.verify_flags is not None:
        p.error("--ab and --verify-flags are separate modes")

    if args.compare:
        print(compare(*args.compare))
        return 0
    if args.verify_flags is not None:
        return verify_flags(args)
    if args.ab is not None:
        reports = run_benchmark(
            args, {"plain": [args.python], "flags": [args.python, *args.ab.split()]}
        )
        if args.out:
            stem = Path(args.out)
            stem.parent.mkdir(parents=True, exist_ok=True)
            for name, rep in reports.items():
                stem.with_suffix(f".{name}.json").write_text(
                    json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
                )
        print(compare_reports(reports["plain"], reports["flags"]))
        return 0
    report = next(iter(run_benchmark(args).values()))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
