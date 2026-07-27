"""Tests for commit_test_gate.py — warn on commit of untested source changes."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import commit_test_gate  # noqa: E402
from commit_test_gate import (
    _exit_code,
    _is_commit,
    _is_pytest,
    _is_source_py,
    _should_warn,
)
from hook_state import HookState  # noqa: E402


class TestIsPytest:
    def test_plain(self):
        assert _is_pytest("python -m pytest tests/ -q")

    def test_bare(self):
        assert _is_pytest("pytest")

    def test_collect_only_is_not_a_run(self):
        assert not _is_pytest("pytest --co")
        assert not _is_pytest("pytest --collect-only")

    def test_unrelated(self):
        assert not _is_pytest("ruff check .")

    def test_echo_pytest_is_not_a_real_run(self):
        """Regression (MEDIUM, hooks-02 audit): `echo pytest` previously
        matched the bare `\\bpytest\\b` substring search anywhere in the
        command, falsely counting as a real test run."""
        assert not _is_pytest("echo pytest")

    def test_printf_mentioning_pytest_is_not_a_real_run(self):
        assert not _is_pytest('printf "running pytest now"')

    def test_heredoc_body_mentioning_pytest_is_not_a_real_run(self):
        """Regression (MEDIUM, hooks-02 audit): a heredoc body that merely
        mentions the word "pytest" (e.g. a report template) previously
        counted as a real run -- the heredoc's actual command (`cat`) must
        be what's checked, not its opaque body text."""
        cmd = "cat <<EOF > report.txt\nRunning pytest suite now...\nEOF"
        assert not _is_pytest(cmd)

    def test_heredoc_body_line_starting_with_pytest_word_is_not_flagged(self):
        """Harder variant: the heredoc body LINE itself starts with the bare
        word "pytest" -- still must not be treated as the outer command,
        since the heredoc's real command is `cat`, not its body content."""
        cmd = "cat <<EOF\npytest was run successfully\nEOF"
        assert not _is_pytest(cmd)

    def test_venv_path_prefixed_pytest_is_a_real_run(self):
        assert _is_pytest(".venv/bin/pytest tests/ -q")

    def test_python_version_suffixed_module_invocation_is_a_real_run(self):
        assert _is_pytest("python3.11 -m pytest tests/")

    def test_pytest_after_cd_chain_is_a_real_run(self):
        assert _is_pytest("cd /repo && pytest tests/ -q")

    def test_pytest_on_second_line_without_chain_operator_is_a_real_run(self):
        """Real multi-line script (bash runs each line in sequence even
        without an explicit `&&` between them) -- must still be detected,
        unlike the heredoc-body case above."""
        assert _is_pytest("echo starting\npytest tests/ -q")

    def test_pytest_as_word_inside_another_command_name_not_flagged(self):
        assert not _is_pytest("run_pytest_wrapper.sh")


class TestExitCode:
    def test_zero_exit_code(self):
        assert _exit_code({"exit_code": 0}) == 0

    def test_nonzero_exit_code(self):
        assert _exit_code({"exit_code": 1}) == 1

    def test_returncode_fallback(self):
        assert _exit_code({"returncode": 2}) == 2

    def test_missing_defaults_to_zero(self):
        assert _exit_code({}) == 0


class TestIsCommit:
    def test_detects(self):
        assert _is_commit("git commit -m x")

    def test_detects_with_flags(self):
        assert _is_commit("git commit -F msg.txt")

    def test_non_commit(self):
        assert not _is_commit("git status")


class TestIsSourcePy:
    def test_source(self):
        assert _is_source_py("hooks/foo.py")

    def test_excludes_test_prefix(self):
        assert not _is_source_py("tests/test_foo.py")

    def test_excludes_test_suffix(self):
        assert not _is_source_py("foo_test.py")

    def test_excludes_tests_dir(self):
        assert not _is_source_py("a/tests/helper.py")

    def test_excludes_non_py(self):
        assert not _is_source_py("README.md")


class TestShouldWarn:
    def test_edit_after_test_warns(self):
        assert _should_warn({"last_edit": 200, "last_test": 100})

    def test_test_after_edit_clean(self):
        assert not _should_warn({"last_edit": 100, "last_test": 200})

    def test_never_tested_but_edited_warns(self):
        assert _should_warn({"last_edit": 100})

    def test_nothing_edited_clean(self):
        assert not _should_warn({"last_test": 100})

    def test_empty_state_clean(self):
        assert not _should_warn({})


class TestScenario:
    """The full flow: edit source, then commit without testing -> warn."""

    def test_edit_then_commit_warns(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("commit_test_gate")
        state["last_edit"] = 100.0
        state.save()
        assert _should_warn(HookState("commit_test_gate"))

    def test_edit_test_commit_clean(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("commit_test_gate")
        state["last_edit"] = 100.0
        state["last_test"] = 150.0
        state.save()
        assert not _should_warn(HookState("commit_test_gate"))


def _run_main(monkeypatch, tmp_path, data: dict) -> str:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            commit_test_gate.main()
        except SystemExit:
            pass
    return buf.getvalue()


class TestFailedPytestDoesNotStampSuccess:
    """Regression (HIGH, hooks-02 audit): a FAILED pytest run previously
    still stamped last_test, so a later commit avoided the "tests didn't
    pass" warning even though tests genuinely failed."""

    def test_successful_pytest_stamps_last_test(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/ -q"},
            "tool_response": {"exit_code": 0},
        }
        _run_main(monkeypatch, tmp_path, data)
        state = HookState("commit_test_gate")
        assert state.get("last_test", 0) != 0

    def test_failed_pytest_does_not_stamp_last_test(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/ -q"},
            "tool_response": {"exit_code": 1},
        }
        _run_main(monkeypatch, tmp_path, data)
        state = HookState("commit_test_gate")
        assert state.get("last_test", 0) == 0

    def test_failed_pytest_then_commit_still_warns(self, monkeypatch, tmp_path):
        """End-to-end: edit source, run pytest that FAILS, then attempt a
        commit -- the warning must still fire, since the failed run must
        not have been credited as a real test pass."""
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        failed_pytest_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/ -q"},
            "tool_response": {"exit_code": 1},
        }
        _run_main(monkeypatch, tmp_path, failed_pytest_data)

        commit_data = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "x"'},
        }
        out = _run_main(monkeypatch, tmp_path, commit_data)
        assert "untested" in out.lower()


class TestMultiEditStampsLastEdit:
    """Regression (MEDIUM, hooks-02 audit): source edits made through a
    MultiEdit PostToolUse event were not stamped at all, since only Edit
    and Write were handled."""

    def test_multiedit_stamps_last_edit(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, data)
        state = HookState("commit_test_gate")
        assert state.get("last_edit", 0) != 0

    def test_multiedit_on_test_file_does_not_stamp(self, monkeypatch, tmp_path):
        data = {
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": "tests/test_foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, data)
        state = HookState("commit_test_gate")
        assert state.get("last_edit", 0) == 0
