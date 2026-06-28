"""Tests for hooks/hook_state.py — centralized file-based state for stateful hooks.

Replaces the inline _load_state/_save_state tests that used to live in
test_commit_test_gate.py and test_iteration_guard.py after those helpers
were consolidated into HookState.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hook_state import HookState


class TestLoadEmpty:
    def test_missing_file_returns_no_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("nonexistent")
        assert state.get("key") is None

    def test_default_value_returned(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("nonexistent")
        assert state.get("key", "fallback") == "fallback"

    def test_corrupt_json_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "bad.json").write_text("{not valid json", encoding="utf-8")
        state = HookState("bad")
        assert state.get("anything") is None


class TestSetAndGet:
    def test_set_and_get_int(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("test_state")
        state["answer"] = 42
        assert state["answer"] == 42

    def test_set_and_get_str(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("test_state")
        state["name"] = "hello"
        assert state.get("name") == "hello"

    def test_contains(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("test_state")
        state["present"] = True
        assert "present" in state
        assert "absent" not in state


class TestSaveAndReload:
    def test_roundtrip_int(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("roundtrip")
        state["last_test"] = 42.0
        state.save()
        assert HookState("roundtrip")["last_test"] == 42.0

    def test_roundtrip_multiple_keys(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("multi")
        state["a"] = 1
        state["b"] = "two"
        state["c"] = [3, 4]
        state.save()
        reloaded = HookState("multi")
        assert reloaded["a"] == 1
        assert reloaded["b"] == "two"
        assert reloaded["c"] == [3, 4]

    def test_overwrite_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("overwrite")
        state["x"] = 1
        state.save()
        state2 = HookState("overwrite")
        state2["x"] = 99
        state2.save()
        assert HookState("overwrite")["x"] == 99

    def test_independent_names(self, tmp_path, monkeypatch):
        """Two HookState instances with different names are independent."""
        monkeypatch.chdir(tmp_path)
        s1 = HookState("s1")
        s1["v"] = "alpha"
        s1.save()
        s2 = HookState("s2")
        s2["v"] = "beta"
        s2.save()
        assert HookState("s1")["v"] == "alpha"
        assert HookState("s2")["v"] == "beta"


class TestPath:
    def test_path_property(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("myname")
        assert state.path == tmp_path / ".claude" / "state" / "myname.json"


class TestBestEffortWrite:
    def test_write_failure_does_not_raise(self, tmp_path, monkeypatch):
        """OSError on write is silently swallowed — hooks must never crash."""
        monkeypatch.chdir(tmp_path)
        state = HookState("safe")
        state["v"] = 1
        # Make directory read-only so write fails
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_dir.chmod(0o444)
        try:
            state.save()  # must NOT raise
        finally:
            state_dir.chmod(0o755)
