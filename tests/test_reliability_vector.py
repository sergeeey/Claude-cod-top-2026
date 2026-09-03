"""Tests for scripts/reliability_vector.py -- the security-critical test
slice reporter.

WHY: this script exists to make a security regression visible as its own
line instead of an invisible fraction of one aggregate pass rate (see
Frontier Agent Engineering 2026 gap analysis, 2026-09-02). It needs the
same test discipline as any other script -- the parsing logic is the part
most likely to silently break against a future pytest version's summary
wording, exactly the failure mode that would make this reporter itself
untrustworthy.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import reliability_vector as rv


def _result(
    passed=0, failed=0, skipped=0, output="", crashed=False, xfailed=0, xpassed=0
) -> rv.SuiteResult:
    return rv.SuiteResult(
        passed, failed, skipped, output, crashed, xfailed=xfailed, xpassed=xpassed
    )


class TestFormatLine:
    def test_all_passed(self):
        assert rv.format_line("Security-critical", _result(passed=187)) == (
            "[reliability-vector] Security-critical: 187/187 passed (100.0%)"
        )

    def test_some_failed(self):
        line = rv.format_line("General", _result(passed=2900, failed=34))
        assert "2900/2934" in line
        assert "%" in line

    def test_zero_zero_does_not_divide_by_zero(self):
        line = rv.format_line("Security-critical", _result())
        assert "0/0" in line
        assert "no tests matched" in line

    def test_skipped_count_is_surfaced_not_folded_into_denominator(self):
        """P2 finding (reviewer, 2026-09-02): a skipped test asserted
        nothing -- it must not silently vanish from the reported line, and
        must not be counted as a pass in the denominator."""
        line = rv.format_line("Security-critical", _result(passed=5, failed=0, skipped=2))
        assert "5/5 passed" in line
        assert "2 skipped" in line

    def test_no_skipped_omits_skip_note(self):
        line = rv.format_line("Security-critical", _result(passed=5, failed=0, skipped=0))
        assert "skipped" not in line

    def test_crashed_reports_collection_error_not_zero_zero(self):
        """P1 finding (reviewer, 2026-09-02): a collection error must never
        render as indistinguishable from '0 tests matched'."""
        line = rv.format_line("Security-critical", _result(crashed=True))
        assert "COLLECTION ERROR" in line
        assert "0/0" not in line

    def test_xfailed_count_is_surfaced_and_excluded_from_denominator(self):
        """External audit finding, 2026-09-03: a known, documented xfail
        marker in a security-marked file (e.g. test_guard_corpus_baseline.py)
        must not silently vanish into a misleading '100% passed' -- it is
        neither a pass nor a fail, and represents a deliberately tracked
        defect that should stay visible."""
        line = rv.format_line("Security-critical", _result(passed=411, failed=0, xfailed=2))
        assert "411/411 passed (100.0%)" in line
        assert "2 xfailed (known gaps)" in line

    def test_xpassed_count_is_surfaced_with_warning_marker(self):
        """An unexpected pass on a strict xfail marker means a tracked
        defect may have just been fixed -- it should stay visible instead
        of silently reporting as an ordinary pass. (Note: pytest's own
        strict-mode accounting also folds this into `failed`; this test
        only covers the visibility of the xpassed count itself.)"""
        line = rv.format_line("Security-critical", _result(passed=411, xpassed=1))
        assert "1 xpassed (!)" in line

    def test_no_xfailed_or_xpassed_omits_those_notes(self):
        line = rv.format_line("Security-critical", _result(passed=5))
        assert "xfailed" not in line
        assert "xpassed" not in line

    def test_skipped_xfailed_and_xpassed_all_shown_together(self):
        line = rv.format_line(
            "Security-critical",
            _result(passed=400, skipped=3, xfailed=2, xpassed=1),
        )
        assert "3 skipped" in line
        assert "2 xfailed (known gaps)" in line
        assert "1 xpassed (!)" in line


class TestRunMarkedSuiteParsing:
    """The subprocess call itself is mocked -- these pin the parsing logic
    against real pytest summary-line shapes captured empirically (no `===`
    banner padding when stdout is not a tty)."""

    def _mock_result(self, stdout: str, returncode: int = 0):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = ""
        result.returncode = returncode
        return result

    def test_parses_passed_only(self):
        with patch("subprocess.run", return_value=self._mock_result("402 passed in 6.06s")):
            result = rv.run_marked_suite("security")
        assert result.passed == 402
        assert result.failed == 0
        assert not result.crashed

    def test_parses_passed_with_deselected(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("402 passed, 2554 deselected in 6.06s"),
        ):
            result = rv.run_marked_suite("security")
        assert result.passed == 402
        assert result.failed == 0

    def test_parses_passed_and_failed(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("2 failed, 400 passed in 6.06s", returncode=1),
        ):
            result = rv.run_marked_suite("security")
        assert result.passed == 400
        assert result.failed == 2
        assert not result.crashed

    def test_parses_skipped(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("400 passed, 3 skipped in 6.06s"),
        ):
            result = rv.run_marked_suite("security")
        assert result.passed == 400
        assert result.skipped == 3

    def test_parses_xfailed(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("411 passed, 2 xfailed in 1.05s"),
        ):
            result = rv.run_marked_suite("security")
        assert result.passed == 411
        assert result.xfailed == 2
        assert not result.crashed

    def test_parses_xpassed(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("410 passed, 1 xpassed in 1.05s"),
        ):
            result = rv.run_marked_suite("security")
        assert result.passed == 410
        assert result.xpassed == 1

    def test_no_xfail_no_xpass_defaults_to_zero(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("400 passed in 6.06s"),
        ):
            result = rv.run_marked_suite("security")
        assert result.xfailed == 0
        assert result.xpassed == 0

    def test_setup_error_alongside_xfailed_is_still_flagged_as_crashed(self):
        """Codex review finding (PR #330, 2026-09-03), reproduced directly
        against a real pytest run (a fixture that raises alongside an
        unrelated xfail test): the summary reads "1 xfailed, 1 error", not
        "1 failed". Before this fix, the nonempty xfailed match alone made
        `crashed=False` -- a real setup/collection error in a
        SECURITY-marked file would silently fall into the "0/0, known gaps"
        branch instead of surfacing as the collection error it is."""
        with patch(
            "subprocess.run",
            return_value=self._mock_result("1 xfailed, 1 error in 0.57s", returncode=1),
        ):
            result = rv.run_marked_suite("security")
        assert result.crashed
        line = rv.format_line("Security-critical", result)
        assert "COLLECTION ERROR" in line
        assert "known gaps" not in line

    def test_error_word_alone_is_flagged_as_crashed(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("1 error in 0.1s", returncode=1),
        ):
            result = rv.run_marked_suite("security")
        assert result.crashed

    def test_no_tests_collected_returns_zero_zero_not_crashed(self):
        """Exit code 5 ('no tests were collected') is a legitimately benign
        outcome -- a marker that matches nothing is not a crash."""
        with patch(
            "subprocess.run",
            return_value=self._mock_result("no tests ran in 0.01s", returncode=5),
        ):
            result = rv.run_marked_suite("security")
        assert result.passed == 0
        assert result.failed == 0
        assert not result.crashed

    def test_collection_error_is_flagged_as_crashed_not_zero_zero(self):
        """P1 finding (reviewer, 2026-09-02): an ImportError/syntax error
        during collection (exit code 2, no 'passed'/'failed' text at all)
        must be surfaced as `crashed=True`, never silently reported as
        '0/0, no tests matched' -- that would hide the single most
        dangerous failure mode this script exists to catch."""
        with patch(
            "subprocess.run",
            return_value=self._mock_result(
                "ImportError while importing test module 'tests/test_broken.py'",
                returncode=2,
            ),
        ):
            result = rv.run_marked_suite("security")
        assert result.crashed
        assert result.passed == 0
        assert result.failed == 0


class TestMainCheckFlag:
    def test_check_returns_1_on_security_failure(self, monkeypatch):
        monkeypatch.setattr(
            rv, "run_marked_suite", lambda marker: _result(passed=5, failed=1, output="...")
        )
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py", "--check"])
        assert rv.main() == 1

    def test_check_returns_1_on_collection_error(self, monkeypatch):
        """The reviewer's P1 scenario end-to-end: a crashed security slice
        must fail --check, not silently return 0."""
        monkeypatch.setattr(
            rv, "run_marked_suite", lambda marker: _result(crashed=True, output="ImportError")
        )
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py", "--check"])
        assert rv.main() == 1

    def test_check_returns_0_when_security_all_pass(self, monkeypatch):
        monkeypatch.setattr(rv, "run_marked_suite", lambda marker: _result(passed=5))
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py", "--check"])
        assert rv.main() == 0

    def test_without_check_flag_always_returns_0_even_on_security_failure(self, monkeypatch):
        """This script reports; the main `pytest tests/` run in CI already
        enforces failure. --check is opt-in extra visibility, not a second
        silent gate that changes default behavior."""
        monkeypatch.setattr(rv, "run_marked_suite", lambda marker: _result(passed=5, failed=1))
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py"])
        assert rv.main() == 0

    def test_default_mode_does_not_rerun_general_suite(self, monkeypatch):
        """The expensive 'not security' rerun must only happen under --full --
        the default path exists specifically to avoid doubling CI's own
        already-completed full-suite run."""
        calls: list[str] = []

        def fake_run(marker):
            calls.append(marker)
            return _result(passed=5)

        monkeypatch.setattr(rv, "run_marked_suite", fake_run)
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py"])
        rv.main()
        assert calls == ["security"]

    def test_full_flag_also_reruns_general_suite(self, monkeypatch):
        calls: list[str] = []

        def fake_run(marker):
            calls.append(marker)
            return _result(passed=5)

        monkeypatch.setattr(rv, "run_marked_suite", fake_run)
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py", "--full"])
        rv.main()
        assert calls == ["security", "not security"]


class TestCollectTotalCount:
    def test_parses_collected_count(self, monkeypatch):
        result = MagicMock()
        result.stdout = "2966 tests collected in 3.2s"
        result.stderr = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: result)
        assert rv.collect_total_count() == 2966

    def test_singular_test_wording(self, monkeypatch):
        result = MagicMock()
        result.stdout = "1 test collected in 0.1s"
        result.stderr = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: result)
        assert rv.collect_total_count() == 1

    def test_no_match_returns_zero(self, monkeypatch):
        result = MagicMock()
        result.stdout = "unexpected output"
        result.stderr = ""
        monkeypatch.setattr("subprocess.run", lambda *a, **k: result)
        assert rv.collect_total_count() == 0
