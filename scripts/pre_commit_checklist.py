#!/usr/bin/env python3
"""Run this project's full pre-commit checklist as ONE command.

WHY this script exists (retrospective, 2026-07-07): CLAUDE.md's "MANDATORY
PRE-COMMIT CHECKLIST" lists lint + tests + reviewer + cross-model as 4
separate steps to remember. In practice, across a multi-hour session, mypy
was silently dropped from the routine "ran ruff+pytest" muscle memory for
an entire day of security fixes -- it only surfaced because CI itself ran
it, not because the checklist was actually followed locally. The lesson:
"remember to run 3 things" fails under session-length pressure; "run one
script" does not. This script exists so "I ran the checklist" means "I ran
`python scripts/pre_commit_checklist.py`", not "I recalled 3 commands from
memory."

This intentionally does NOT replace steps 3 (reviewer agent) and 4
(cross-model review) from CLAUDE.md's checklist -- those require spawning
an Agent, which a standalone script cannot do. It closes the gap for the
part that IS mechanical: lint, type-check, tests.

Usage:
    python scripts/pre_commit_checklist.py
    python scripts/pre_commit_checklist.py --fast   # skip pytest (ruff+mypy only)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_step(name: str, cmd: list[str]) -> bool:
    print(f"\n{'=' * 60}")
    print(f"→ {name}")
    print(f"  $ {' '.join(cmd)}")
    print("=" * 60)
    start = time.monotonic()
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    elapsed = time.monotonic() - start
    ok = result.returncode == 0
    status = "PASS" if ok else "FAIL"
    print(f"\n[{status}] {name} ({elapsed:.1f}s)")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip pytest -- only ruff + mypy (use before a quick doc/comment-only commit)",
    )
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = [
        ("Lint (ruff)", [sys.executable, "-m", "ruff", "check", "."]),
        (
            "Type check (mypy)",
            [sys.executable, "-m", "mypy", "--ignore-missing-imports", "hooks/", "scripts/"],
        ),
    ]
    if not args.fast:
        steps.append(
            (
                "Tests (pytest)",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/",
                    "-q",
                    "--tb=short",
                    "--ignore=tests/test_install.sh",
                ],
            )
        )

    results = [(name, _run_step(name, cmd)) for name, cmd in steps]

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, ok in results:
        print(f"  {'✓' if ok else '✗'} {name}")
        all_passed = all_passed and ok

    if args.fast:
        print("\n⚠ --fast mode: pytest was SKIPPED. Do not treat this as a full pass.")

    if not all_passed:
        print("\n❌ Checklist FAILED. Fix the above before committing.")
        return 1

    print("\n✅ Checklist passed. Still required before a 3+ file commit (not")
    print("   automated here): Agent(reviewer) pass, and a cross-model pass")
    print("   for hook/script changes (see CLAUDE.md's pre-commit checklist).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
