#!/usr/bin/env python3
"""Update README test/coverage badges from the CI log — never from local pytest.

WHY (recurring mistake [×3], PR #115/#124/#125): the README Tests/Coverage
badges are read by external viewers, so the CI environment IS the source of
truth. But local pytest on Windows counts ~4 more tests than CI on Linux —
because some tests are environment-dependent (test_artifact_schema_validator
needs the global ~/.claude hook installed; test_registry_matches_disk needs
PyYAML, absent in CI's minimal deps). Updating the badge from a local count
therefore drifts from CI every time, and the CI verify-metrics step fails.

This script removes the human-judgement step entirely: it reads the actual
"Actual: NNNN tests, MM% coverage" line that the CI verify-metrics step prints,
from the latest successful main run, and rewrites the badges to match. By
construction the badge then equals what CI will check.

Usage:
    python scripts/sync_readme_from_ci.py            # read CI, update README
    python scripts/sync_readme_from_ci.py --check    # report drift, write nothing (exit 1 if drift)

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
    # Replace every occurrence of the old test number and coverage with CI values.
    if old_tests != new_tests:
        text = text.replace(str(old_tests), str(new_tests))
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
        f"README: {cur_tests} tests, {cur_cov}% cov"
    )

    if cur_tests == ci_tests and cur_cov == ci_cov:
        print("[sync-readme] README already matches CI — nothing to do.")
        return 0

    if check_only:
        print("[sync-readme] DRIFT detected (run without --check to fix).")
        return 1

    new = _rewrite(text, cur_tests or 0, ci_tests, cur_cov or 0, ci_cov)
    README.write_text(new, encoding="utf-8")
    print(
        f"[sync-readme] README updated → {ci_tests} tests, "
        f"{ci_cov}% coverage (from CI run {run_id})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
