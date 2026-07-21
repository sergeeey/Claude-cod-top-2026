#!/usr/bin/env python3
"""Compute the false-PASS rate for reviewer/security-guard verdicts.

WHY (external comparison, RAAS-2026 reference architecture, 2026-07-21): our reviewer and
security-guard agents issue LGTM/PASS verdicts constantly, but nothing measures how often
those verdicts turned out wrong -- the exact gap RAAS-2026 calls "false PASS rate" and this
repo already had the raw material for (git history + verdict text) without ever computing
it. hooks/verdict_logger.py now records every verdict with its commit/files; this script is
the other half: cross-reference recorded PASS-class verdicts against LATER commits that look
like they were fixing the same files.

Method (deliberately simple, not a claim of causation): for each LGTM/PASS record with a
resolvable git_head, look at commits AFTER that head, within a window (default 30 days),
whose message starts with fix/revert/hotfix (case-insensitive) AND whose changed files
overlap the verdict's `files` set. A hit counts as a false pass. This is a heuristic proxy,
not proof the reviewer was wrong -- a fix commit touching the same file could be unrelated
follow-up work, not a correction. Report this rate as a signal to investigate, not a verdict
on the reviewer.

No-silent-caps: with an empty or near-empty log (the bootstrap case right after this script
ships), the rate is reported as INSUFFICIENT_DATA, never a reassuring "0.0%" that would read
as "measured and clean" when it is actually "not measured yet".

Usage:
    python scripts/false_pass_rate.py                # human report
    python scripts/false_pass_rate.py --json          # machine-readable
    python scripts/false_pass_rate.py --window-days 14
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / ".claude" / "memory" / "verdict_log.jsonl"
PASS_VERDICTS = {"LGTM", "PASS"}
MIN_RECORDS_FOR_RATE = 5  # below this, a rate is noise, not a signal


def _run_git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            cwd=ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def load_records(log_path: Path = LOG_PATH) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a corrupt line must not crash the whole report
    return records


def _commits_after(sha: str, window_days: int) -> list[dict[str, Any]]:
    """Commits reachable from HEAD but not from `sha`, i.e. everything after it, within
    the time window. Returns [] on any git error (unresolvable sha, shallow clone, ...)."""
    log = _run_git(
        [
            "log",
            f"{sha}..HEAD",
            "--pretty=format:%H%x1f%aI%x1f%s",
        ]
    )
    if log is None:
        return []
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    commits = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit_sha, iso_date, subject = parts
        try:
            committed_at = datetime.fromisoformat(iso_date)
        except ValueError:
            continue
        if committed_at < cutoff:
            continue
        files_raw = _run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha])
        files = set(files_raw.splitlines()) if files_raw else set()
        commits.append({"sha": commit_sha, "subject": subject, "files": files})
    return commits


def _looks_like_a_fix(subject: str) -> bool:
    lowered = subject.lower()
    return any(lowered.startswith(prefix) for prefix in ("fix", "revert", "hotfix"))


def evaluate_record(record: dict[str, Any], window_days: int) -> dict[str, Any]:
    """Return the record annotated with a false_pass verdict, or a reason it couldn't be
    evaluated (missing git_head, no files, git lookup failed)."""
    sha = record.get("git_head")
    files = set(record.get("files") or [])
    if not sha:
        return {**record, "evaluated": False, "reason": "no git_head recorded"}
    if not files:
        return {**record, "evaluated": False, "reason": "no files recorded"}
    later_commits = _commits_after(sha, window_days)
    for commit in later_commits:
        if _looks_like_a_fix(commit["subject"]) and files & commit["files"]:
            return {
                **record,
                "evaluated": True,
                "false_pass": True,
                "matched_commit": commit["sha"][:8],
                "matched_subject": commit["subject"],
            }
    return {**record, "evaluated": True, "false_pass": False}


def compute(log_path: Path | None = None, window_days: int = 30) -> dict[str, Any]:
    # NOT a `= LOG_PATH` default: that would bind the module-level path at *import* time,
    # so a test (or future --log-path CLI flag) monkeypatching LOG_PATH afterward would be
    # silently ignored. Resolving it here reads the CURRENT value at call time instead.
    records = load_records(LOG_PATH if log_path is None else log_path)
    pass_records = [r for r in records if str(r.get("verdict", "")).upper() in PASS_VERDICTS]
    evaluated = [evaluate_record(r, window_days) for r in pass_records]
    scored = [r for r in evaluated if r.get("evaluated")]
    false_passes = [r for r in scored if r.get("false_pass")]

    result: dict[str, Any] = {
        "total_records": len(records),
        "pass_class_records": len(pass_records),
        "evaluable_records": len(scored),
        "false_passes": len(false_passes),
        "window_days": window_days,
    }
    if len(scored) < MIN_RECORDS_FOR_RATE:
        result["false_pass_rate"] = None
        result["status"] = "INSUFFICIENT_DATA"
        result["note"] = (
            f"Only {len(scored)} evaluable PASS-class verdicts (need "
            f"{MIN_RECORDS_FOR_RATE}+). Rate withheld, not reported as 0.0%, per "
            "no-silent-caps: an unmeasured system and a clean one must never look "
            "the same in the report."
        )
    else:
        result["false_pass_rate"] = len(false_passes) / len(scored)
        result["status"] = "MEASURED"
    result["false_pass_details"] = [
        {k: v for k, v in r.items() if k != "files"} for r in false_passes
    ]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--window-days", type=int, default=30)
    args = parser.parse_args(argv)

    result = compute(window_days=args.window_days)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("False-PASS rate report")
    print(f"  total verdict records:    {result['total_records']}")
    print(f"  PASS-class records:       {result['pass_class_records']}")
    print(f"  evaluable (has head+files): {result['evaluable_records']}")
    if result["status"] == "INSUFFICIENT_DATA":
        print(f"  false-pass rate:          INSUFFICIENT_DATA ({result['note']})")
    else:
        rate = result["false_pass_rate"]
        print(
            f"  false-pass rate:          {rate:.1%} ({result['false_passes']} of "
            f"{result['evaluable_records']})"
        )
        for d in result["false_pass_details"]:
            print(
                f"    - {d['agent']} {d['verdict']} at {d.get('git_head', '?')[:8]} "
                f'-> fixed by {d["matched_commit"]} "{d["matched_subject"]}"'
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
