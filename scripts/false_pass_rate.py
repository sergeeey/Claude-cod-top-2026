#!/usr/bin/env python3
"""Compute the suspected-false-PASS rate for reviewer/security-guard verdicts.

WHY (external comparison, RAAS-2026 reference architecture, 2026-07-21): our reviewer and
security-guard agents issue LGTM/PASS verdicts constantly, but nothing measures how often
those verdicts turned out wrong -- the exact gap RAAS-2026 calls "false PASS rate" and this
repo already had the raw material for (git history + verdict text) without ever computing
it. hooks/verdict_logger.py now records every verdict with its commit/files; this script is
the other half: cross-reference recorded PASS-class verdicts against LATER commits that look
like they were fixing the same files.

Method (deliberately simple, not a claim of causation): for each LGTM/PASS record with a
resolvable git_head and timestamp, look at commits committed strictly after the verdict's own
`ts`, up to `ts + window_days`, whose message starts with fix/revert/hotfix
(case-insensitive) AND whose changed files overlap the verdict's `files` set. A hit is a
SUSPECTED false pass -- not proof: a fix commit touching the same file could be unrelated
follow-up work, a different function in that file, a requirement that changed, or a bug
introduced by someone else after the review. Report this rate as a signal to investigate,
never as a verdict on the reviewer (external review, 2026-07-21, caught the original name
`false_pass_rate` overclaiming exactly this -- renamed to `suspected_false_pass_rate`
throughout; "the metric was named more precisely than it measures").

Two correctness fixes from that same review, both confirmed by reading the pre-fix code
before changing it (not taken on faith):
  1. Window is now anchored to the VERDICT's own `ts`, not to `datetime.now()`. The old
     `cutoff = now - window_days` meant an old verdict's genuinely-fast fix (5 days after
     the verdict, 90 days ago) could fall outside a `now`-anchored 30-day cutoff and be
     silently excluded -- the exact "committed_at < cutoff: continue" bug this review named.
  2. A verdict younger than its own observation window (no fix found YET, but the window
     hasn't elapsed) is `PENDING`, not silently counted as a confirmed clean pass. The old
     code counted it as `evaluated=True, false_pass=False` the instant it was logged --
     zero observation time, full vote of confidence. This is what let the review's stress
     case happen: 100 same-day PASS records + 1 old genuine false pass would have reported
     a reassuring 0.99%, when only the one old record had actually completed observation.

No-silent-caps (unchanged principle, now applied more honestly): with too few COMPLETED
evaluations, the rate is INSUFFICIENT_DATA, never a reassuring "0.0%" that would read as
"measured and clean" when it is actually "not measured yet" or "still pending".

Deliberately NOT done in this pass (documented, not silently dropped -- see
docs/false-pass-rate.md "Next" section): binding the verdict to a precise reviewed-file list
(vs. the current best-effort commit/working-tree diff union) requires reviewer.md and
security-guard.md to return a structured scope, a change to their own output contract, not
just this script; verifier coverage requires giving verifier an equally strict verdict
format first. Both are real, both are bigger changes than a bugfix pass, tracked separately.

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


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _commits_in_window(
    sha: str, verdict_ts: datetime | None, window_days: int
) -> list[dict[str, Any]]:
    """Commits reachable from HEAD but not from `sha` (i.e. everything after it), further
    restricted to (verdict_ts, verdict_ts + window_days] when verdict_ts is known.

    Anchored to verdict_ts, NOT datetime.now() -- an old verdict's fast, genuine fix must
    not fall out of the window just because a lot of time has passed since TODAY. When
    verdict_ts is unavailable (older log records predating the `ts` field), no date bound
    is applied at all -- degrades to "everything reachable from HEAD after sha", matching
    the pre-fix behavior for that legacy case only.

    Returns [] on any git error (unresolvable sha, shallow clone, ...).
    """
    log = _run_git(["log", f"{sha}..HEAD", "--pretty=format:%H%x1f%aI%x1f%s"])
    if log is None:
        return []
    window_end = verdict_ts + timedelta(days=window_days) if verdict_ts else None
    commits = []
    for line in log.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit_sha, iso_date, subject = parts
        committed_at = _parse_ts(iso_date)
        if committed_at is None:
            continue
        if verdict_ts is not None and committed_at < verdict_ts:
            continue  # sanity net against committer-date anomalies (rebase/backdate)
        if window_end is not None and committed_at > window_end:
            continue
        files_raw = _run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha])
        files = set(files_raw.splitlines()) if files_raw else set()
        commits.append({"sha": commit_sha, "subject": subject, "files": files})
    return commits


def _looks_like_a_fix(subject: str) -> bool:
    lowered = subject.lower()
    return any(lowered.startswith(prefix) for prefix in ("fix", "revert", "hotfix"))


def evaluate_record(
    record: dict[str, Any], window_days: int, now: datetime | None = None
) -> dict[str, Any]:
    """Return the record annotated with a suspected-false-pass verdict, PENDING (still
    within its own observation window with no fix found yet), or a reason it couldn't be
    evaluated at all (missing git_head/files)."""
    sha = record.get("git_head")
    files = set(record.get("files") or [])
    if not sha:
        return {
            **record,
            "status": "UNEVALUABLE",
            "evaluated": False,
            "reason": "no git_head recorded",
        }
    if not files:
        return {
            **record,
            "status": "UNEVALUABLE",
            "evaluated": False,
            "reason": "no files recorded",
        }

    verdict_ts = _parse_ts(record.get("ts"))
    matching_commits = _commits_in_window(sha, verdict_ts, window_days)
    for commit in matching_commits:
        if _looks_like_a_fix(commit["subject"]) and files & commit["files"]:
            return {
                **record,
                "status": "SUSPECTED_FALSE_PASS",
                "evaluated": True,
                "suspected_false_pass": True,
                "matched_commit": commit["sha"][:8],
                "matched_subject": commit["subject"],
            }

    # No matching fix found yet. If the verdict is younger than its own observation
    # window, absence of evidence is not evidence of absence -- it's PENDING, not clean.
    if verdict_ts is not None:
        window_end = verdict_ts + timedelta(days=window_days)
        clock = now or datetime.now(UTC)
        if clock < window_end:
            return {**record, "status": "PENDING", "evaluated": False}

    return {**record, "status": "CLEAN", "evaluated": True, "suspected_false_pass": False}


def compute(
    log_path: Path | None = None, window_days: int = 30, now: datetime | None = None
) -> dict[str, Any]:
    # NOT a `= LOG_PATH` default: that would bind the module-level path at *import* time,
    # so a test (or future --log-path CLI flag) monkeypatching LOG_PATH afterward would be
    # silently ignored. Resolving it here reads the CURRENT value at call time instead.
    records = load_records(LOG_PATH if log_path is None else log_path)
    pass_records = [r for r in records if str(r.get("verdict", "")).upper() in PASS_VERDICTS]
    annotated = [evaluate_record(r, window_days, now=now) for r in pass_records]
    scored = [r for r in annotated if r.get("evaluated")]
    pending = [r for r in annotated if r.get("status") == "PENDING"]
    suspected = [r for r in scored if r.get("suspected_false_pass")]

    result: dict[str, Any] = {
        "total_records": len(records),
        "pass_class_records": len(pass_records),
        "pending_records": len(pending),
        "evaluable_records": len(scored),
        "suspected_false_passes": len(suspected),
        "window_days": window_days,
    }
    if len(scored) < MIN_RECORDS_FOR_RATE:
        result["suspected_false_pass_rate"] = None
        result["status"] = "INSUFFICIENT_DATA"
        result["note"] = (
            f"Only {len(scored)} PASS-class verdicts have COMPLETED their {window_days}-day "
            f"observation window (need {MIN_RECORDS_FOR_RATE}+; {len(pending)} more are "
            "still PENDING). Rate withheld, not reported as 0.0%, per no-silent-caps: an "
            "unmeasured system and a clean one must never look the same in the report."
        )
    else:
        result["suspected_false_pass_rate"] = len(suspected) / len(scored)
        result["status"] = "MEASURED"
    result["suspected_false_pass_details"] = [
        {k: v for k, v in r.items() if k != "files"} for r in suspected
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

    print("Suspected-false-PASS rate report")
    print(f"  total verdict records:      {result['total_records']}")
    print(f"  PASS-class records:         {result['pass_class_records']}")
    print(f"  still pending observation:  {result['pending_records']}")
    print(f"  evaluable (window elapsed): {result['evaluable_records']}")
    if result["status"] == "INSUFFICIENT_DATA":
        print(f"  suspected-false-pass rate:  INSUFFICIENT_DATA ({result['note']})")
    else:
        rate = result["suspected_false_pass_rate"]
        print(
            f"  suspected-false-pass rate:  {rate:.1%} ({result['suspected_false_passes']} of "
            f"{result['evaluable_records']})"
        )
        for d in result["suspected_false_pass_details"]:
            print(
                f"    - {d['agent']} {d['verdict']} at {d.get('git_head', '?')[:8]} "
                f'-> possibly fixed by {d["matched_commit"]} "{d["matched_subject"]}"'
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
