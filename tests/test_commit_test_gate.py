"""Tests for commit_test_gate.py — warn on commit of untested source changes."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import commit_test_gate
from commit_test_gate import (
    _exit_code,
    _is_commit,
    _is_pytest,
    _is_source_py,
    _should_warn,
)
from hook_state import HookState, commit_test_gate_state, git_root


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


class TestIsSourcePyProjectBoundary:
    # WHY: reproduces the actual bug (2026-09-05, found live) -- a .py file
    # written OUTSIDE the project (e.g. an OS temp scratchpad directory used
    # for manual verification scripts) previously still counted as "source
    # changed", stamping last_edit against a repo the file has nothing to do
    # with and triggering false commit-test-gate warnings/Stop-blocks.
    def test_file_outside_project_is_not_source(self, monkeypatch, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        monkeypatch.chdir(repo_root)

        scratchpad_dir = tmp_path / "unrelated_scratchpad"
        scratchpad_dir.mkdir()
        outside_file = scratchpad_dir / "verify_something.py"

        assert not _is_source_py(str(outside_file))

    def test_file_inside_project_is_still_source(self, monkeypatch, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        monkeypatch.chdir(repo_root)

        inside_file = repo_root / "hooks" / "foo.py"
        assert _is_source_py(str(inside_file))

    def test_relative_path_resolved_against_cwd_inside_project(self, monkeypatch, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        monkeypatch.chdir(repo_root)

        assert _is_source_py("hooks/foo.py")

    def test_file_in_sibling_repo_is_not_source(self, monkeypatch, tmp_path):
        """A .py file that belongs to a DIFFERENT project (its own .git)
        must not count as source for the current project's gate."""
        repo_a = tmp_path / "repo_a"
        repo_a.mkdir()
        (repo_a / ".git").mkdir()
        monkeypatch.chdir(repo_a)

        repo_b = tmp_path / "repo_b"
        repo_b.mkdir()
        (repo_b / ".git").mkdir()
        other_project_file = repo_b / "hooks" / "bar.py"

        assert not _is_source_py(str(other_project_file))


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
    # WHY (tmp_path / ".git").mkdir(): _state() anchors to git_root(cwd()), which
    # walks UPWARD looking for a .git. On this exact machine C:/Users/<user> (an
    # ancestor of every pytest tmp_path) is itself a git repo -- verified directly
    # while adding the base_dir fix -- so without a .git marker right here, state
    # would silently escape tmp_path and land in the REAL live
    # ~/.claude/state/commit_test_gate.json instead of the test's isolated
    # directory. Creating .git here matches the realistic case anyway (this hook
    # only ever runs inside an actual git repo in production).
    (tmp_path / ".git").mkdir(exist_ok=True)
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


def _run_main_capture_exit(monkeypatch, tmp_path, data: dict) -> tuple[str, int]:
    """Like _run_main, but returns (stderr_text, exit_code) -- the Stop
    handler blocks via exit code + stderr, not stdout JSON."""
    # See _run_main's WHY comment on the identical (tmp_path / ".git").mkdir() line.
    (tmp_path / ".git").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
    err_buf = io.StringIO()
    exit_code = 0
    with patch("sys.stderr", err_buf):
        try:
            commit_test_gate.main()
        except SystemExit as e:
            exit_code = e.code or 0
    return err_buf.getvalue(), exit_code


class TestStopBlocksUntestedChanges:
    """Survivorship-bias closure (2026-08-28): a warning at commit-time is
    easy to skim past, and 'tests passed' claimed at the end of a turn was
    previously unverifiable -- this makes ending the turn itself contingent
    on a real, passing pytest run since the last source edit."""

    def test_no_edits_stop_allowed_silently(self, monkeypatch, tmp_path):
        stop_data = {"hook_event_name": "Stop"}
        err, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 0
        assert err == ""

    def test_edit_then_stop_blocks(self, monkeypatch, tmp_path):
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        stop_data = {"hook_event_name": "Stop"}
        err, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 2
        assert "pytest" in err.lower()

    def test_edit_then_passing_test_then_stop_allowed(self, monkeypatch, tmp_path):
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        pytest_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/ -q"},
            "tool_response": {"exit_code": 0},
        }
        _run_main(monkeypatch, tmp_path, pytest_data)

        stop_data = {"hook_event_name": "Stop"}
        err, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 0
        assert err == ""

    def test_edit_then_failed_test_then_stop_still_blocks(self, monkeypatch, tmp_path):
        # A FAILED pytest run must not count as "tested" -- same principle
        # as TestFailedPytestDoesNotStampSuccess, applied to the Stop path.
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

        stop_data = {"hook_event_name": "Stop"}
        err, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 2

    def test_repeated_stop_attempts_eventually_fail_open(self, monkeypatch, tmp_path):
        """Regression-by-design: an unconditional block risks an infinite
        loop (no confirmed platform loop-prevention field exists for Stop,
        per this hook's own module docstring). After
        _MAX_CONSECUTIVE_STOP_BLOCKS blocked attempts with no intervening
        test run, the next Stop must be allowed through."""
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        stop_data = {"hook_event_name": "Stop"}
        codes = []
        for _ in range(commit_test_gate._MAX_CONSECUTIVE_STOP_BLOCKS + 1):
            _, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
            codes.append(code)

        assert codes[:-1] == [2] * commit_test_gate._MAX_CONSECUTIVE_STOP_BLOCKS
        assert codes[-1] == 0

    def test_fail_open_does_not_falsely_stamp_last_test(self, monkeypatch, tmp_path):
        """WHY this matters: failing open must be honest about NOT having
        verified the tests -- it must never look like a real test run
        happened, or a later commit-time check would be silently fooled."""
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        stop_data = {"hook_event_name": "Stop"}
        for _ in range(commit_test_gate._MAX_CONSECUTIVE_STOP_BLOCKS + 1):
            _run_main_capture_exit(monkeypatch, tmp_path, stop_data)

        state = HookState("commit_test_gate")
        assert state.get("last_test", 0) == 0

    def test_hookeventname_camelcase_also_detected(self, monkeypatch, tmp_path):
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        stop_data = {"hookEventName": "Stop"}
        _, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 2

    def test_stop_event_does_not_require_claude_invoked_by_bypass(self, monkeypatch, tmp_path):
        # Sanity check: a plain Stop event (no tool call involved at all)
        # must not be mistaken for a Bash/Edit/Write dispatch branch and
        # fall through with no action.
        edit_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "hooks/foo.py"},
            "tool_response": {},
        }
        _run_main(monkeypatch, tmp_path, edit_data)

        stop_data = {"hook_event_name": "Stop", "session_id": "abc", "cwd": str(tmp_path)}
        _, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 2

    def test_crash_in_stop_handler_fails_closed(self, monkeypatch, tmp_path):
        """A hook whose whole job is to BLOCK must not silently become an
        ALLOW on its own bug. WHY not hook_main(fail_closed=True) (see the
        main() WHY comment at the Stop dispatch site): that helper's
        fail-closed path emits a PreToolUse-shaped permissionDecision, which
        does nothing for a Stop event -- this hook fails closed natively
        (exit 2 + stderr) instead."""
        monkeypatch.setattr(
            commit_test_gate,
            "_handle_stop",
            lambda data: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        stop_data = {"hook_event_name": "Stop"}
        err, code = _run_main_capture_exit(monkeypatch, tmp_path, stop_data)
        assert code == 2


class TestGitRoot:
    """Regression (2026-09-02, dogfooding incident): this hook's four event
    types get DIFFERENT cwd from the harness -- Bash-triggered events see the
    current *shell* cwd (which drifts as `cd` runs), while Edit/Write/Stop
    events see the fixed *session* cwd. Anchoring state to the git root
    (stable regardless of subdirectory) makes all four event types agree on
    one file instead of silently stamping/reading different ones."""

    def test_finds_root_from_nested_subdirectory(self, tmp_path):
        (tmp_path / ".git").mkdir()
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        assert git_root(nested) == tmp_path.resolve()

    def test_returns_start_itself_when_already_at_root(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert git_root(tmp_path) == tmp_path.resolve()

    def test_git_as_a_file_counts_too(self, tmp_path):
        """Worktrees have `.git` as a FILE pointing at the real gitdir, not a
        directory -- `_git_root` must not require it to be a directory."""
        (tmp_path / ".git").write_text("gitdir: /somewhere/else\n", encoding="utf-8")
        nested = tmp_path / "sub"
        nested.mkdir()
        assert git_root(nested) == tmp_path.resolve()

    def test_falls_back_to_start_outside_any_git_repo(self, tmp_path, monkeypatch):
        # WHY monkeypatch Path.exists instead of relying on "tmp_path has no
        # ancestor with a .git": on this exact machine C:/Users/<user> (an
        # ancestor of every pytest tmp_path) is itself a git repo -- verified
        # directly (`test -d ~/.git`) while writing this test -- so the
        # "outside any git repo" premise can be false depending on the
        # machine, exactly the class of environment-dependence already fixed
        # in test_check_global_hooks.py. Mocking makes this deterministic.
        monkeypatch.setattr(Path, "exists", lambda self: False)
        assert git_root(tmp_path) == tmp_path

    def test_state_shared_across_different_shell_cwd_within_same_repo(self, tmp_path, monkeypatch):
        """The actual incident this fix closes: a pytest run stamped from a
        shell that had `cd`'d into a subdirectory must be visible to a Stop
        check running from the repo root -- both must resolve to ONE file."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "some" / "nested" / "dir"
        subdir.mkdir(parents=True)

        monkeypatch.chdir(subdir)
        state_from_subdir = commit_test_gate_state()
        state_from_subdir["last_test"] = 12345
        state_from_subdir.save()

        monkeypatch.chdir(tmp_path)
        state_from_root = commit_test_gate_state()
        assert state_from_root["last_test"] == 12345
        assert state_from_subdir.path == state_from_root.path
        # The stray erroneous "err" reference removed here (2026-09-04) was a
        # copy/paste artifact from writing this test, never a real assertion
        # about this test's own behavior -- it referenced an undefined name
        # and could only ever raise NameError, unconditionally, regardless of
        # whether _git_root/_state worked correctly or not. Replaced with a
        # real check: the value must actually be persisted to disk, not just
        # visible via the in-memory object each _state() call returns.
        assert json.loads(state_from_root.path.read_text(encoding="utf-8"))["last_test"] == 12345
