"""Tests for commit_test_gate.py — warn on commit of untested source changes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from commit_test_gate import (
    _is_commit,
    _is_pytest,
    _is_source_py,
    _should_warn,
)
from hook_state import HookState


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
