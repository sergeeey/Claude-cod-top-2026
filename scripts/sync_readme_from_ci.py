"""Sync README test-count and coverage badges from actual pytest/coverage output.

Usage:
    python scripts/sync_readme_from_ci.py [--check]

    --check   Dry-run: report drift without writing. Exit 1 if drift found.

WHY: README carries two static badges (Tests, Coverage) that drift as the
codebase grows. Hand-editing drifts every PR. This script reads the real
values and writes them back atomically, so the badge always matches CI.

Run from repo root. Requires: pytest, pytest-cov installed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
TESTS_DIR = REPO / "tests"

DRY_RUN = "--check" in sys.argv


def run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    return r.stdout + r.stderr


def get_test_count() -> int:
    out = run(["python", "-m", "pytest", str(TESTS_DIR), "--collect-only", "-q"])
    m = re.search(r"(\d+) tests? collected", out)
    if not m:
        print("[sync] ERROR: could not parse test count from pytest output")
        print(out[-500:])
        sys.exit(1)
    return int(m.group(1))


def get_coverage_pct() -> int:
    out = run(["python", "-m", "coverage", "report"])
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", out)
    if not m:
        print("[sync] WARNING: coverage report not available — run pytest --cov first")
        return -1
    return int(m.group(1))


def update_readme(tests: int, cov: int) -> bool:
    text = README.read_text(encoding="utf-8")
    original = text

    # Badge: Tests-NNNN-00ff9f
    text = re.sub(
        r"(Tests-)(\d+)(-00ff9f\?style=flat-square)",
        lambda m: f"{m.group(1)}{tests}{m.group(3)}",
        text,
    )

    # Badge: Coverage-NN%25-00ff9f
    if cov >= 0:
        text = re.sub(
            r"(Coverage-)(\d+)(%25-00ff9f\?style=flat-square)",
            lambda m: f"{m.group(1)}{cov}{m.group(3)}",
            text,
        )

    # Inline subheader: "1192 tests · 80% coverage"
    text = re.sub(r"\d+ tests(?= ·)", f"{tests} tests", text)

    # Comparison table: "1192 tests, TDD-first"
    text = re.sub(r"\d+ tests(?=,)", f"{tests} tests", text)
    if cov >= 0:
        text = re.sub(r"\d+% coverage", f"{cov}% coverage", text)

    changed = text != original
    if changed and not DRY_RUN:
        README.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    print("[sync] Collecting test count...")
    tests = get_test_count()
    print(f"[sync] Tests: {tests}")

    print("[sync] Reading coverage...")
    cov = get_coverage_pct()
    print(f"[sync] Coverage: {cov}%" if cov >= 0 else "[sync] Coverage: N/A (skipped)")

    changed = update_readme(tests, cov)

    if changed:
        if DRY_RUN:
            print(f"[sync] DRIFT DETECTED — README needs update (tests={tests}, cov={cov}%)")
            sys.exit(1)
        else:
            print(
                f"[sync] README updated: tests={tests}" + (f", coverage={cov}%" if cov >= 0 else "")
            )
    else:
        print("[sync] README already up-to-date. No changes.")


if __name__ == "__main__":
    main()
