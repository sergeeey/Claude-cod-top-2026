"""Tests for scripts/pre_commit_checklist.py — one-command lint+type+test runner.

WHY: 0% coverage before this file. subprocess.run is mocked throughout so
these tests never actually re-invoke ruff/mypy/pytest (which would recurse
into pytest running pytest) -- they verify _run_step()'s pass/fail mapping
and main()'s step selection (--fast) and summary/exit-code logic instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pre_commit_checklist import _run_step, main


def _fake_result(returncode):
    result = mock.Mock()
    result.returncode = returncode
    return result


class TestRunStep:
    def test_returns_true_and_prints_pass_on_returncode_zero(self, capsys):
        with mock.patch("subprocess.run", return_value=_fake_result(0)):
            ok = _run_step("Lint (ruff)", ["ruff", "check", "."])
        assert ok is True
        assert "[PASS] Lint (ruff)" in capsys.readouterr().out

    def test_returns_false_and_prints_fail_on_nonzero_returncode(self, capsys):
        with mock.patch("subprocess.run", return_value=_fake_result(1)):
            ok = _run_step("Type check (mypy)", ["mypy", "."])
        assert ok is False
        assert "[FAIL] Type check (mypy)" in capsys.readouterr().out

    def test_prints_the_command_being_run(self, capsys):
        with mock.patch("subprocess.run", return_value=_fake_result(0)):
            _run_step("Lint (ruff)", ["ruff", "check", "."])
        assert "$ ruff check ." in capsys.readouterr().out


class TestMain:
    def test_default_runs_all_three_steps_and_returns_zero_on_success(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["pre_commit_checklist.py"])
        with mock.patch("subprocess.run", return_value=_fake_result(0)):
            code = main()
        out = capsys.readouterr().out
        assert code == 0
        assert "✓ Lint (ruff)" in out
        assert "✓ Type check (mypy)" in out
        assert "✓ Tests (pytest)" in out
        assert "Checklist passed." in out

    def test_fast_flag_skips_pytest_step(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["pre_commit_checklist.py", "--fast"])
        with mock.patch("subprocess.run", return_value=_fake_result(0)) as run_mock:
            code = main()
        out = capsys.readouterr().out
        assert code == 0
        assert "Tests (pytest)" not in out
        assert "pytest was SKIPPED" in out
        called_cmds = [call.args[0] for call in run_mock.call_args_list]
        assert not any("pytest" in cmd for cmd in called_cmds)

    def test_failing_step_returns_one_and_prints_failure_banner(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["pre_commit_checklist.py", "--fast"])

        def fake_run(cmd, cwd):
            return _fake_result(1 if "mypy" in cmd else 0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            code = main()
        out = capsys.readouterr().out
        assert code == 1
        assert "✗ Type check (mypy)" in out
        assert "Checklist FAILED" in out

    def test_success_message_still_mentions_reviewer_and_cross_model_steps(
        self, capsys, monkeypatch
    ):
        monkeypatch.setattr(sys, "argv", ["pre_commit_checklist.py"])
        with mock.patch("subprocess.run", return_value=_fake_result(0)):
            main()
        out = capsys.readouterr().out
        assert "Agent(reviewer)" in out
        assert "cross-model" in out
