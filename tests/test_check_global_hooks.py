"""Tests for scripts/check_global_hooks.py — worktree-vs-global hook diagnostic.

WHY: 0% coverage before this file. The script has no functions and no
`if __name__ == "__main__":` guard — every line runs at import time,
including os.listdir() on a hardcoded personal path
(C:/Users/serge/.claude/hooks) that does not exist on any machine but its
original author's. Real behavior on any other machine (including CI): the
unguarded os.listdir() call raises FileNotFoundError before the module
finishes importing. TestUnmockedImport documents that behavior, but mocks
os.listdir to simulate the path's absence rather than relying on the real
filesystem (fixed 2026-09-04) -- the literal hardcoded path is this repo's
own maintainer's real machine, where it genuinely exists, so leaving it
unmocked made the test fail specifically on the one machine this suite is
most often run on interactively. TestMockedRun exercises the intended
diagnostic logic by mocking os.path.exists/os.listdir before import (to
simulate presence, not absence), which is how coverage attributes these
module-level lines without ever touching a real filesystem path.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

MODULE_NAME = "check_global_hooks"


def _fresh_import():
    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


class TestUnmockedImport:
    def test_raises_filenotfounderror_when_the_hardcoded_global_path_is_absent(self):
        # WHY this is mocked now, not left to the real filesystem (fixed
        # 2026-09-04): the test's entire premise is "a machine without
        # GLOBAL" -- but GLOBAL = "C:/Users/serge/.claude/hooks" is this
        # repo's own maintainer's literal, real machine path, where it
        # genuinely exists. Relying on the ambient filesystem to make that
        # path absent is true on CI (Linux) and any other machine, but false
        # on the ONE machine this suite is most often run on interactively --
        # verified directly: this test failed with "DID NOT RAISE" on that
        # exact machine, because os.listdir(GLOBAL) succeeds there for real.
        # Mocking os.listdir to raise specifically for GLOBAL makes the test
        # deterministic on every machine, matching the mocking technique
        # TestMockedRun below already uses for the success path -- this is
        # that same technique applied to the absence path.
        def fake_listdir(path):
            if str(path).replace("\\", "/") == "C:/Users/serge/.claude/hooks":
                raise FileNotFoundError(path)
            return []

        with (
            mock.patch("os.listdir", side_effect=fake_listdir),
            pytest.raises(FileNotFoundError),
        ):
            _fresh_import()


class TestMockedRun:
    def _run_with(self, global_files, worktree_files):
        """Import the module with os.path.exists/os.listdir fully faked for
        BOTH sides (GLOBAL and WORKTREE), so the test is hermetic and does
        not depend on this repo's real, changing hooks/ inventory."""

        def fake_exists(path):
            path = str(path).replace("\\", "/")
            if path == "C:/Users/serge/.claude/hooks":
                return True
            if path.startswith("C:/Users/serge/.claude/hooks/"):
                return path.rsplit("/", 1)[-1] in global_files
            if path == "hooks":
                return True
            if path.startswith("hooks/"):
                return path.split("/", 1)[-1] in worktree_files
            return False

        def fake_listdir(path):
            path = str(path).replace("\\", "/")
            if path == "C:/Users/serge/.claude/hooks":
                return global_files
            if path == "hooks":
                return worktree_files
            return []

        with (
            mock.patch("os.path.exists", side_effect=fake_exists),
            mock.patch("os.listdir", side_effect=fake_listdir),
        ):
            return _fresh_import()

    def test_reports_missing_hook_as_absent_from_both(self, capsys):
        self._run_with(global_files=[], worktree_files=[])
        out = capsys.readouterr().out
        assert "REFERENCED BUT MISSING FROM WORKTREE" in out
        assert "estimand_guard: GLOBAL✗ | WORKTREE✗" in out

    def test_reports_hook_present_globally_but_not_in_worktree(self, capsys):
        self._run_with(global_files=["estimand_guard.py", "utils.py"], worktree_files=[])
        out = capsys.readouterr().out
        assert "estimand_guard: GLOBAL✓ | WORKTREE✗" in out

    def test_reports_hook_present_in_both(self, capsys):
        self._run_with(global_files=["estimand_guard.py"], worktree_files=["estimand_guard.py"])
        out = capsys.readouterr().out
        assert "estimand_guard: GLOBAL✓ | WORKTREE✓" in out

    def test_not_registered_section_present(self, capsys):
        self._run_with(global_files=["learning_tips.py"], worktree_files=[])
        out = capsys.readouterr().out
        assert "NOT REGISTERED" in out
        assert "learning_tips: GLOBAL✓" in out
        assert "cogniml_client: GLOBAL✗ (dev only)" in out

    def test_global_only_hooks_listed(self, capsys):
        self._run_with(
            global_files=["utils.py", "some_local_only_hook.py"],
            worktree_files=["utils.py"],
        )
        out = capsys.readouterr().out
        assert "GLOBAL hooks NOT in worktree" in out
        assert "some_local_only_hook" in out

    def test_utils_py_excluded_from_global_only_listing(self, capsys):
        self._run_with(global_files=["utils.py"], worktree_files=[])
        out = capsys.readouterr().out
        # utils.py is explicitly filtered out on both sides -- it must never
        # show up as a "global only" drift item.
        assert "- utils" not in out
