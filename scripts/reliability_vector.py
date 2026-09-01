#!/usr/bin/env python3
"""Report the security-critical test slice as its OWN pass/fail line,
never folded into the general aggregate.

WHY (Frontier Agent Engineering 2026 gap analysis, Obsidian note,
2026-09-02): "never average away a catastrophic safety dimension with a
high helpfulness score" -- one aggregate ("2934 tests, 83% coverage")
cannot show whether the security-critical slice specifically passed. A
single flaky/failing general test and a single failing SSRF/secret-
redaction test look identical in a 99.97% pass rate; this script makes the
security dimension a separate, named number instead of an invisible
fraction of one.

This does NOT add new enforcement -- `pytest tests/` already fails the CI
job on any test failure, security-marked or not. It adds VISIBILITY: the
security-critical count is printed as its own labelled line so a reviewer
scanning CI output (or the README) sees "187/187 security-critical" as a
fact, not an inference from "2934 passed" alone.

WHY the default run does NOT also re-run the general (non-security) suite:
CI's own "Run pytest with coverage" step already executes the full suite
immediately before this one -- re-running ~2500 non-security tests here
would roughly double that step's wall-clock time for zero new information
(the main step already failed the job if anything there broke). Only the
`security`-marked slice (a few hundred tests, seconds) is re-run here, for
its own dedicated pass/fail count; `--full` opts into also re-running the
general suite for a genuinely standalone local check.

Usage:
  python scripts/reliability_vector.py            # security slice only (fast)
  python scripts/reliability_vector.py --check     # same, exit 1 on any
                                                    # security-marked failure
  python scripts/reliability_vector.py --full      # also re-run the general
                                                    # suite (local sanity check,
                                                    # not used by CI)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# WHY two independent \d+ (?:word) searches, not one combined summary-line
# regex: pytest's final line drops the `===` banner padding entirely when
# stdout isn't a real terminal (confirmed empirically -- captured
# subprocess output here is a bare "402 passed, 2554 deselected in 6.06s",
# no "=" characters at all), and the passed/failed/skipped segment ORDER
# and PRESENCE both vary by outcome mix. Searching for each count
# independently, anywhere in the final summary text, is robust to both.
_PASSED_RE = re.compile(r"(\d+)\s+passed")
_FAILED_RE = re.compile(r"(\d+)\s+failed")


def run_marked_suite(marker: str) -> tuple[int, int, str]:
    """Run `pytest tests/ -m <marker>` and return (passed, failed, raw_output).

    Deliberately a SEPARATE subprocess run, not a re-parse of the main
    coverage run's own report: keeps this script decoupled from whichever
    tool (coverage, json-report, etc.) the main run happens to use, and
    lets it be invoked standalone for a local sanity check.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-m", marker, "-q", "--no-header"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    # WHY search the LAST occurrence, not the first: pytest can print
    # "X passed" earlier in per-test progress output under some verbosity
    # settings; the summary line is always the final one.
    passed_matches = _PASSED_RE.findall(output)
    failed_matches = _FAILED_RE.findall(output)
    passed = int(passed_matches[-1]) if passed_matches else 0
    failed = int(failed_matches[-1]) if failed_matches else 0
    return passed, failed, output


def collect_total_count() -> int:
    """Fast, execution-free total test count via `--collect-only`, for
    context only ("X security-critical out of Y total") -- never executes
    a single test."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"(\d+)\s+tests?\s+collected", result.stdout + result.stderr)
    return int(match.group(1)) if match else 0


def format_line(label: str, passed: int, failed: int) -> str:
    total = passed + failed
    if total == 0:
        return f"[reliability-vector] {label}: 0/0 (no tests matched -- see raw output)"
    pct = 100.0 * passed / total
    return f"[reliability-vector] {label}: {passed}/{total} passed ({pct:.1f}%)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any security-marked test failed (redundant with the main "
        "suite run, but makes THIS dimension's failure visible by its own exit code)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also re-run the general (non-security) suite for a standalone check "
        "(expensive -- not used by CI, which already ran it in the prior step)",
    )
    args = parser.parse_args()

    sec_passed, sec_failed, sec_output = run_marked_suite("security")
    print(format_line("Security-critical", sec_passed, sec_failed))

    if args.full:
        gen_passed, gen_failed, _gen_output = run_marked_suite("not security")
        print(format_line("General", gen_passed, gen_failed))
    else:
        total = collect_total_count()
        if total:
            print(f"[reliability-vector] ({sec_passed + sec_failed}/{total} of full suite)")

    if sec_failed and args.check:
        print(
            "\n[reliability-vector] FAILING security-critical test(s) detected -- "
            "never average this into the general pass rate:\n",
            file=sys.stderr,
        )
        print(sec_output, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
