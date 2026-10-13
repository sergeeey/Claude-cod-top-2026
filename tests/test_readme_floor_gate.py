"""Regression tests for the README test-floor gate in .github/workflows/ci.yml.

WHY this file exists: the gate is bash inside a workflow step, so nothing in the
Python suite exercised it. An independent review showed the consequence directly:
reverting `-i` on its greps -- which silently reopens a bypass where `3500+ Tests`
(capital T) sits beside a `Tests-3600%2B` badge and passes -- left every existing
test green. That is the "logic tested, wiring untested" failure this repository's
Cycle 2 replay documented, reproduced on the gate built to close it.

HOW: the relevant lines are extracted from ci.yml VERBATIM and run in bash against
small fixture READMEs. Nothing is re-implemented here, so editing a pattern in the
workflow changes what these tests exercise without anyone having to remember to
update a copy. The fixtures are synthetic on purpose: they unit-test the gate's own
logic, not a claim about real-world data.

Skipped when bash or PCRE grep is unavailable (some Windows setups). CI runs on
ubuntu-latest, where both are present.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"


def _bash_with_pcre_grep() -> str | None:
    bash = shutil.which("bash")
    if not bash:
        return None
    try:
        r = subprocess.run(
            # Same locale the gate run uses below. Without it Git-Bash's grep refuses -P
            # ("supports only unibyte and UTF-8 locales") and every test here silently
            # SKIPS -- a skipped suite looks exactly like a passing one in a summary line.
            [
                bash,
                "-c",
                "export LC_ALL=C.UTF-8; echo 3600+ tests | grep -oiP '\\d{3,5}(?=\\+\\s*tests\\b)'",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bash if r.returncode == 0 and r.stdout.strip() == "3600" else None


BASH = _bash_with_pcre_grep()
pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash with grep -P")


def _gate_script() -> str:
    """Return the README-floor portion of the CI step, exactly as written there."""
    lines = CI.read_text(encoding="utf-8").splitlines()

    floor_line = next(ln for ln in lines if ln.strip().startswith("README_FLOOR=$(grep"))

    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("BARE_NUMS=$(grep"))
    marker = next(i for i in range(start, len(lines)) if "two different test floors" in lines[i])
    end = next(i for i in range(marker, len(lines)) if lines[i].strip() == "done")

    body = [floor_line] + lines[start : end + 1]
    return "\n".join(ln.strip() for ln in body)


def _run(readme_text: str, actual: int, tmp_path: Path) -> tuple[int, str]:
    (tmp_path / "README.md").write_text(readme_text, encoding="utf-8", newline="\n")
    script = "\n".join(
        [
            "set -u",
            "export LC_ALL=C.UTF-8",
            f"ACTUAL_TESTS={actual}",
            "FAIL=0",
            _gate_script(),
            'echo "GATE_FAIL=$FAIL"',
        ]
    )
    r = subprocess.run(
        [BASH, "-c", script],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    out = r.stdout + r.stderr
    fail = 1 if "GATE_FAIL=1" in out else 0
    assert "GATE_FAIL=" in out, f"gate script did not complete:\n{out}"
    return fail, out


BADGE = "![Tests](https://img.shields.io/badge/Tests-3600%2B-00ff9f)\n"


class TestExtraction:
    def test_extracted_block_contains_all_three_checks(self):
        """Guards the extraction itself: if the CI step is restructured so this
        test can no longer find the gate, fail loudly rather than test nothing."""
        script = _gate_script()
        assert "README_FLOOR=$(grep" in script
        assert "BARE_NUMS=$(grep" in script
        assert "FLOOR_NUMS=$(grep" in script
        assert "two different test floors" in script


class TestFloorGate:
    def test_consistent_floors_pass(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3600+ tests.\nTotal: 3600+ tests\n", 3616, tmp_path)
        assert fail == 0, out

    def test_disagreeing_floor_fails(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3500+ tests.\n", 3616, tmp_path)
        assert fail == 1
        assert "two different test floors" in out

    def test_disagreeing_floor_with_capital_T_fails(self, tmp_path):
        """THE BYPASS independent review found. 3500 is met by 3616, so only the
        agreement check can catch it -- and only if the grep is case-insensitive."""
        fail, out = _run(BADGE + "Backed by 3500+ Tests.\n", 3616, tmp_path)
        assert fail == 1, "a capital-T floor must not be invisible to the gate"
        assert "two different test floors" in out

    def test_disagreeing_floor_without_space_fails(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3500+tests.\n", 3616, tmp_path)
        assert fail == 1
        assert "two different test floors" in out

    def test_unmet_floor_fails(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3600+ tests.\n", 3400, tmp_path)
        assert fail == 1
        assert "claims at least 3600" in out

    def test_bare_exact_count_fails(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3616 tests.\n", 3616, tmp_path)
        assert fail == 1
        assert "use the floor form" in out

    def test_bare_exact_count_with_capital_T_fails(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3616 Tests.\n", 3616, tmp_path)
        assert fail == 1
        assert "use the floor form" in out

    def test_bare_hyphenated_count_fails(self, tmp_path):
        fail, out = _run(BADGE + "Backed by 3616-tests.\n", 3616, tmp_path)
        assert fail == 1
        assert "use the floor form" in out


class TestNoFalsePositives:
    """The widening must not start flagging prose that is not a suite-total claim.
    A singular `tests?` was tried and flagged both of these."""

    def test_singular_test_cases_is_not_a_count_claim(self, tmp_path):
        fail, out = _run(BADGE + "Covers 200 test cases for the parser.\n", 3616, tmp_path)
        assert fail == 0, out

    def test_hyphenated_adjective_is_not_a_count_claim(self, tmp_path):
        fail, out = _run(BADGE + "A 3616-test suite would be slower.\n", 3616, tmp_path)
        assert fail == 0, out


class TestRealReadme:
    def test_real_readme_passes_at_a_count_above_its_floor(self, tmp_path):
        text = (REPO / "README.md").read_text(encoding="utf-8")
        fail, out = _run(text, 3616, tmp_path)
        assert fail == 0, out
