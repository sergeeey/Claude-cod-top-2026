#!/usr/bin/env python3
"""Check the README test FLOOR and sync the coverage badge from the CI log.

WHY (recurring mistake [×3], PR #115/#124/#125): the README Tests/Coverage
badges are read by external viewers, so the CI environment IS the source of
truth. But local pytest on Windows counts ~4 more tests than CI on Linux —
because some tests are environment-dependent (test_artifact_schema_validator
needs the global ~/.claude hook installed; test_registry_matches_disk needs
PyYAML, absent in CI's minimal deps). Updating the badge from a local count
therefore drifts from CI every time, and the CI verify-metrics step fails.

This script removes the human-judgement step entirely: it reads the actual
"Actual: NNNN tests, MM% coverage" line that the CI verify-metrics step prints,
from the latest successful main run, and compares the README against it. What
it then DOES with each of the two numbers differs -- see SCOPE CHANGE below:
the coverage badge is rewritten to match, the test count is only checked,
because it is a floor rather than a figure to keep in step.

SCOPE CHANGE (PR E, 2026-09-12): the test count is now a FLOOR in README
("3600+"), not an exact figure, so this script CHECKS that floor rather than
syncing a number. The reasoning is one level up from the Windows/Linux gap
described above: if the count differs by platform, an exact figure asserts a
precision the measurement does not have. It is also not computable before the
event that validates it -- `_latest_main_run_id()` below reads the latest
successful run ON MAIN, while the number a PR needs comes from that PR's own
run, which is neither on main nor finished when a human would want to sync.
Five consecutive PRs of one cycle failed the README gate, every one of them for
"you added tests". Coverage is still synced, because it moves in both directions
and has no floor semantics.

Usage:
    python scripts/sync_readme_from_ci.py            # check the floor, sync coverage
    python scripts/sync_readme_from_ci.py --check    # report only, write nothing (exit 1 if drift)

Requires: gh CLI authenticated. Stdlib only otherwise.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"

# The CI verify-metrics step prints exactly: "Actual: 1352 tests, 75% coverage"
_CI_LINE = re.compile(r"Actual:\s*(\d+)\s*tests?,\s*(\d+)%\s*coverage")


def _latest_main_run_id() -> str | None:
    """Return the id of the most recent completed main 'Tests' run."""
    try:
        out = subprocess.run(
            [
                "gh",
                "api",
                "repos/sergeeey/Claude-cod-top-2026/actions/runs",
                "--jq",
                # first completed run on main for the Tests workflow
                '[.workflow_runs[] | select(.head_branch=="main" and .status=="completed")][0].id',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        rid = out.stdout.strip()
        return rid or None
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[sync-readme] gh api failed: {e}", file=sys.stderr)
        return None


def _ci_metrics(run_id: str) -> tuple[int, int] | None:
    """Parse (tests, coverage) from the CI run log. None if not found."""
    try:
        out = subprocess.run(
            ["gh", "run", "view", run_id, "--log"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[sync-readme] gh run view failed: {e}", file=sys.stderr)
        return None
    m = _CI_LINE.search(out.stdout)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _current_badge(text: str) -> tuple[int | None, int | None]:
    t = re.search(r"Tests-(\d+)", text)
    c = re.search(r"Coverage-(\d+)", text)
    return (int(t.group(1)) if t else None, int(c.group(1)) if c else None)


def _rewrite(text: str, old_tests: int, new_tests: int, old_cov: int, new_cov: int) -> str:
    """Rewrite ONLY the test/coverage badge contexts — never a bare number.

    WHY (Codex cross-model review caught this): a global `text.replace("1352",...)`
    would also hit a year, a hook count, or a URL fragment that happens to equal
    the old test number. Each replacement is anchored to a specific badge/prose
    context so an unrelated occurrence of the number is left untouched.
    """
    if old_tests != new_tests:
        o, n = str(old_tests), str(new_tests)
        # 1) shields.io badge:  Tests-1352
        text = re.sub(rf"Tests-{o}\b", f"Tests-{n}", text)
        # 2) prose:  "1352 tests"  /  "1352 passing"  (count immediately before the word)
        text = re.sub(rf"\b{o}(?=\s+tests\b)", n, text)
        text = re.sub(rf"\b{o}(?=\s+passing\b)", n, text)
    if old_cov != new_cov:
        text = re.sub(rf"Coverage-{old_cov}%25", f"Coverage-{new_cov}%25", text)
        text = re.sub(rf"\b{old_cov}% coverage", f"{new_cov}% coverage", text)
    return text


def main() -> int:
    check_only = "--check" in sys.argv
    run_id = _latest_main_run_id()
    if not run_id:
        print("[sync-readme] no completed main run found", file=sys.stderr)
        return 0  # fail-open: don't block
    metrics = _ci_metrics(run_id)
    if not metrics:
        print("[sync-readme] CI log has no 'Actual: N tests' line", file=sys.stderr)
        return 0
    ci_tests, ci_cov = metrics
    text = README.read_text(encoding="utf-8")
    cur_tests, cur_cov = _current_badge(text)
    print(
        f"[sync-readme] CI: {ci_tests} tests, {ci_cov}% cov | "
        f"README: >={cur_tests} tests (floor), {cur_cov}% cov"
    )

    # WHY the test count is CHECKED but no longer SYNCED (PR E, 2026-09-12): the
    # badge now carries a FLOOR ("3600+"), not an exact count. An exact count is a
    # property of CI's environment rather than of this repository -- this file's
    # own docstring above records the ~4-test Windows/Linux gap -- and is not
    # computable before the CI run that validates it. Rewriting the floor upward
    # on every sync would rebuild precisely the manual treadmill the floor exists
    # to remove: five consecutive PRs of one cycle failed this gate, every time
    # for "you added tests", never once for a real problem.
    #
    # The floor is raised DELIBERATELY, by someone deciding the larger claim is
    # worth making -- never mechanically, just because the number moved.
    floor_broken = cur_tests is not None and ci_tests < cur_tests
    if floor_broken:
        print(
            f"[sync-readme] FLOOR BROKEN: README claims >={cur_tests} tests but CI "
            f"counted {ci_tests} -- tests were removed, or the floor was set too high.",
            file=sys.stderr,
        )

    cov_drift = cur_cov is not None and cur_cov != ci_cov
    if not floor_broken and not cov_drift:
        print("[sync-readme] floor holds and coverage matches — nothing to do.")
        return 0

    if check_only:
        # WHY the message is split: this branch fires for a broken floor OR coverage
        # drift. The old single message told the user to "run without --check to fix
        # coverage" even when only the floor was broken -- which that run deliberately
        # does NOT fix. Name what is actually wrong, and what the fix path is for each.
        problems = []
        if floor_broken:
            problems.append("test floor broken (never auto-fixed -- investigate the missing tests)")
        if cov_drift:
            problems.append("coverage drift (run without --check to sync it)")
        print(f"[sync-readme] DRIFT detected: {'; '.join(problems)}.")
        return 1

    if floor_broken:
        # Deliberately NOT auto-lowered: a broken floor means tests disappeared,
        # which is a finding to investigate, not a number to quietly correct.
        print(
            "[sync-readme] floor NOT auto-adjusted — investigate the missing tests first.",
            file=sys.stderr,
        )

    if cov_drift:
        new = _rewrite(text, cur_tests or 0, cur_tests or 0, cur_cov or 0, ci_cov)
        README.write_text(new, encoding="utf-8")
        print(f"[sync-readme] coverage updated → {ci_cov}% (from CI run {run_id}).")

    return 1 if floor_broken else 0


if __name__ == "__main__":
    sys.exit(main())
