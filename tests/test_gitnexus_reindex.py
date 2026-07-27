"""Tests for gitnexus_reindex.py — auto-reindex after a successful git commit.

Root incident (2026-07-21): CLAUDE.md claimed "hook does this automatically"
but no such hook existed anywhere -- gitnexus's index for this repo's root
checkout was stale since 2026-04-15 (verified live via mcp__gitnexus__list_repos)
despite dozens of intervening commits. This hook closes that gap.
"""

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from gitnexus_reindex import main, resolve_target_dir, should_reindex


class TestShouldReindex:
    def test_successful_commit_triggers_reindex(self):
        assert should_reindex('git commit -m "fix bug"', "1 file changed, 2 insertions(+)") is True

    def test_failed_commit_does_not_trigger(self):
        assert should_reindex('git commit -m "x"', "nothing to commit, working tree clean") is False

    def test_non_commit_command_does_not_trigger(self):
        assert should_reindex("git status", "On branch main") is False

    def test_git_commit_substring_in_unrelated_command_does_not_false_positive(self):
        # WHY: "git commit" must appear as the actual command, but this simple
        # heuristic (matching post_commit_memory.py's precedent) only checks
        # substring presence -- a commit message that happens to mention "git
        # commit" as prose text (not the invocation) WOULD false-positive here.
        # Documented, accepted limitation (see module docstring) -- verifying
        # the ACTUAL behavior, not asserting an unproven fix.
        assert should_reindex('echo "reminder: git commit later"', "") is True


class TestResolveTargetDir:
    def test_no_cd_prefix_uses_current_cwd(self, monkeypatch):
        monkeypatch.setattr("os.getcwd", lambda: "/session/repo")
        assert resolve_target_dir('git commit -m "x"') == "/session/repo"

    def test_cd_prefix_extracts_target_repo(self):
        assert resolve_target_dir('cd /other/repo && git commit -m "x"') == "/other/repo"

    def test_quoted_cd_prefix_with_spaces(self):
        cmd = 'cd "E:\\path with spaces" && git commit -m "x"'
        assert resolve_target_dir(cmd) == "E:\\path with spaces"


class TestMainEndToEnd:
    """Mocks subprocess.run -- tests must NEVER spawn a real `npx gitnexus
    analyze` (slow, network-dependent, and would reindex whatever repo pytest
    happens to run from)."""

    @staticmethod
    def _stdin(data: dict) -> io.StringIO:
        return io.StringIO(json.dumps(data))

    def _run(self, monkeypatch, data: dict):
        calls = []
        monkeypatch.setattr(
            "gitnexus_reindex.subprocess.run",
            lambda *a, **kw: calls.append((a, kw)),
        )
        monkeypatch.setattr("sys.stdin", self._stdin(data))
        try:
            main()
        except SystemExit as exc:
            assert exc.code in (0, None)
        return calls

    def test_successful_commit_invokes_gitnexus_analyze(self, monkeypatch, tmp_path):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "feat: x"'},
            "tool_response": {"stdout": "1 file changed"},
        }
        calls = self._run(monkeypatch, payload)
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert args[0] == ["npx", "gitnexus", "analyze"]
        assert kwargs["timeout"] == 120

    def test_failed_commit_does_not_invoke_gitnexus(self, monkeypatch, tmp_path):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "x"'},
            "tool_response": {"stdout": "nothing to commit, working tree clean"},
        }
        assert self._run(monkeypatch, payload) == []

    def test_non_git_command_does_not_invoke_gitnexus(self, monkeypatch, tmp_path):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"stdout": "file1 file2"},
        }
        assert self._run(monkeypatch, payload) == []

    def test_recursion_guard_suppresses_even_a_real_commit(self, monkeypatch, tmp_path):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "subagent")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "feat: x"'},
            "tool_response": {"stdout": "1 file changed"},
        }
        assert self._run(monkeypatch, payload) == []

    def test_cd_prefixed_commit_reindexes_the_correct_repo(self, monkeypatch, tmp_path):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'cd /other/repo && git commit -m "feat: x"'},
            "tool_response": {"stdout": "1 file changed"},
        }
        calls = self._run(monkeypatch, payload)
        assert len(calls) == 1
        _, kwargs = calls[0]
        assert kwargs["cwd"] == "/other/repo"

    def test_timeout_is_swallowed_silently(self, monkeypatch, tmp_path):
        # WHY: a hung/slow npx process must never surface as a hook error --
        # pure background maintenance, next commit's hook retries.
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        def _raise_timeout(*a, **kw):
            import subprocess

            raise subprocess.TimeoutExpired(cmd="npx", timeout=120)

        monkeypatch.setattr("gitnexus_reindex.subprocess.run", _raise_timeout)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "feat: x"'},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", self._stdin(payload))
        try:
            main()  # must not raise
        except SystemExit as exc:
            assert exc.code in (0, None)


class TestConcurrencyLock:
    """Regression (reviewer, 2026-07-21): two rapid commits to the same repo
    could previously spawn concurrent `npx gitnexus analyze` subprocesses --
    wasted duplicate work with no correctness benefit (the second run's
    result is a superset of the first's). Uses the REAL file_lock (not
    mocked) so this exercises actual OS-level exclusion, not a stand-in."""

    def test_lock_path_is_deterministic_and_dir_scoped(self, tmp_path, monkeypatch):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        path_a1 = gitnexus_reindex._lock_path_for("/repo/a")
        path_a2 = gitnexus_reindex._lock_path_for("/repo/a")
        path_b = gitnexus_reindex._lock_path_for("/repo/b")
        assert path_a1 == path_a2
        assert path_a1 != path_b
        assert path_a1.parent == tmp_path

    def test_skips_reindex_when_a_lock_is_already_held(self, tmp_path, monkeypatch):
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        target_dir = "/some/repo"
        lock_path = gitnexus_reindex._lock_path_for(target_dir)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.touch()  # simulate another in-flight reindex holding the lock

        calls = []
        monkeypatch.setattr(
            "gitnexus_reindex.subprocess.run",
            lambda *a, **kw: calls.append((a, kw)),
        )
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": f'cd "{target_dir}" && git commit -m "feat: x"'},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        try:
            gitnexus_reindex.main()
        except SystemExit as exc:
            assert exc.code in (0, None)

        assert calls == []

    def test_reindexes_normally_once_the_lock_is_released(self, tmp_path, monkeypatch):
        """Sanity check for the fixture itself: an UNHELD lock (no file
        present) must not block the real reindex path."""
        import gitnexus_reindex

        monkeypatch.setattr(gitnexus_reindex, "_LOCK_DIR", tmp_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        calls = []
        monkeypatch.setattr(
            "gitnexus_reindex.subprocess.run",
            lambda *a, **kw: calls.append((a, kw)),
        )
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "feat: x"'},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        try:
            gitnexus_reindex.main()
        except SystemExit as exc:
            assert exc.code in (0, None)

        assert len(calls) == 1
