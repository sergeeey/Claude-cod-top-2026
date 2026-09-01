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


class TestFormatLine:
    def test_all_passed(self):
        assert rv.format_line("Security-critical", 187, 0) == (
            "[reliability-vector] Security-critical: 187/187 passed (100.0%)"
        )

    def test_some_failed(self):
        line = rv.format_line("General", 2900, 34)
        assert "2900/2934" in line
        assert "%" in line

    def test_zero_zero_does_not_divide_by_zero(self):
        line = rv.format_line("Security-critical", 0, 0)
        assert "0/0" in line
        assert "no tests matched" in line


class TestRunMarkedSuiteParsing:
    """The subprocess call itself is mocked -- these pin the parsing logic
    against real pytest summary-line shapes captured empirically (no `===`
    banner padding when stdout is not a tty)."""

    def _mock_result(self, stdout: str):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = ""
        return result

    def test_parses_passed_only(self):
        with patch("subprocess.run", return_value=self._mock_result("402 passed in 6.06s")):
            passed, failed, _ = rv.run_marked_suite("security")
        assert passed == 402
        assert failed == 0

    def test_parses_passed_with_deselected(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("402 passed, 2554 deselected in 6.06s"),
        ):
            passed, failed, _ = rv.run_marked_suite("security")
        assert passed == 402
        assert failed == 0

    def test_parses_passed_and_failed(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("2 failed, 400 passed in 6.06s"),
        ):
            passed, failed, _ = rv.run_marked_suite("security")
        assert passed == 400
        assert failed == 2

    def test_no_tests_collected_returns_zero_zero(self):
        with patch(
            "subprocess.run",
            return_value=self._mock_result("no tests ran in 0.01s"),
        ):
            passed, failed, _ = rv.run_marked_suite("security")
        assert passed == 0
        assert failed == 0


class TestMainCheckFlag:
    def test_check_returns_1_on_security_failure(self, monkeypatch):
        monkeypatch.setattr(rv, "run_marked_suite", lambda marker: (5, 1, "1 failed, 5 passed"))
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py", "--check"])
        assert rv.main() == 1

    def test_check_returns_0_when_security_all_pass(self, monkeypatch):
        monkeypatch.setattr(rv, "run_marked_suite", lambda marker: (5, 0, "5 passed"))
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py", "--check"])
        assert rv.main() == 0

    def test_without_check_flag_always_returns_0_even_on_security_failure(self, monkeypatch):
        """This script reports; the main `pytest tests/` run in CI already
        enforces failure. --check is opt-in extra visibility, not a second
        silent gate that changes default behavior."""
        monkeypatch.setattr(rv, "run_marked_suite", lambda marker: (5, 1, "1 failed, 5 passed"))
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
            return (5, 0, "5 passed")

        monkeypatch.setattr(rv, "run_marked_suite", fake_run)
        monkeypatch.setattr(rv, "collect_total_count", lambda: 100)
        monkeypatch.setattr("sys.argv", ["reliability_vector.py"])
        rv.main()
        assert calls == ["security"]

    def test_full_flag_also_reruns_general_suite(self, monkeypatch):
        calls: list[str] = []

        def fake_run(marker):
            calls.append(marker)
            return (5, 0, "5 passed")

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
