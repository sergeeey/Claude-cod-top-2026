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
_SKIPPED_RE = re.compile(r"(\d+)\s+skipped")


class SuiteResult:
    """Outcome of one `run_marked_suite()` call.

    WHY a distinct `crashed` flag, not just (0, 0) (reviewer finding,
    2026-09-02): pytest exit code 5 means "no tests collected" -- a
    genuinely benign case when a marker legitimately matches nothing.
    Exit code 2 (or any other nonzero code with no parsed passed/failed
    counts) means collection itself blew up -- an ImportError, a syntax
    error, a broken fixture in a SECURITY-marked file. Collapsing both into
    the same "0/0, no tests matched" message would silently report the
    single most dangerous failure mode (a security test file that cannot
    even be collected) as "nothing to see here" -- exactly the "average
    away a catastrophic dimension" failure this whole script exists to
    prevent, just one level up from where it was originally guarding.
    """

    def __init__(self, passed: int, failed: int, skipped: int, output: str, crashed: bool) -> None:
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.output = output
        self.crashed = crashed


# WHY 5: pytest's own documented exit code for "no tests were collected"
# (as opposed to 2, "an error occurred during test collection or before
# tests ran" -- e.g. an import failure in a marked file). Both look
# identical to the two regexes below (neither prints "N passed"/"N
# failed"), so returncode is the only way to tell "legitimately empty"
# from "something is broken" apart.
_NO_TESTS_COLLECTED_EXIT_CODE = 5


def run_marked_suite(marker: str) -> SuiteResult:
    """Run `pytest tests/ -m <marker>` and return a SuiteResult.

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
    skipped_matches = _SKIPPED_RE.findall(output)
    passed = int(passed_matches[-1]) if passed_matches else 0
    failed = int(failed_matches[-1]) if failed_matches else 0
    skipped = int(skipped_matches[-1]) if skipped_matches else 0

    crashed = (
        not passed_matches
        and not failed_matches
        and not skipped_matches
        and result.returncode not in (0, _NO_TESTS_COLLECTED_EXIT_CODE)
    )
    return SuiteResult(passed, failed, skipped, output, crashed)


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


def format_line(label: str, result: SuiteResult) -> str:
    if result.crashed:
        return (
            f"[reliability-vector] {label}: COLLECTION ERROR -- pytest could not even "
            "collect this slice (import failure, broken fixture, syntax error). This is "
            "NOT the same as '0 tests matched' -- see raw output."
        )
    total = result.passed + result.failed
    if total == 0:
        skip_note = f", {result.skipped} skipped" if result.skipped else ""
        return f"[reliability-vector] {label}: 0/0 (no tests matched{skip_note} -- see raw output)"
    pct = 100.0 * result.passed / total
    # WHY report skipped separately, not folded into `total` (reviewer P2
    # finding, 2026-09-02): a skipped security test asserted nothing -- it
    # is neither a pass nor a fail. Silently excluding it from the
    # denominator makes "100% passed" true even when a security-critical
    # test never actually ran (e.g. an environment-gated skip). Naming the
    # count keeps that gap visible instead of averaging it away.
    skip_note = f", {result.skipped} skipped" if result.skipped else ""
    return f"[reliability-vector] {label}: {result.passed}/{total} passed ({pct:.1f}%){skip_note}"


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

    sec = run_marked_suite("security")
    print(format_line("Security-critical", sec))

    if args.full:
        gen = run_marked_suite("not security")
        print(format_line("General", gen))
    else:
        total = collect_total_count()
        if total:
            print(f"[reliability-vector] ({sec.passed + sec.failed}/{total} of full suite)")

    if (sec.failed or sec.crashed) and args.check:
        reason = "COLLECTION ERROR in" if sec.crashed else "FAILING test(s) detected in"
        print(
            f"\n[reliability-vector] {reason} the security-critical slice -- "
            "never average this into the general pass rate:\n",
            file=sys.stderr,
        )
        print(sec.output, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
