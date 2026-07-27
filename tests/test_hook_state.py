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


class TestPruning:
    """Regression (2026-07-19): per-session-keyed state files (iteration_guard,
    locality_escalation_guard) grew by one entry every session forever -- a
    stale legacy entry was observed fail-closing iteration_guard mid-session.
    """

    def test_under_threshold_keeps_everything(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("small", max_entries=5)
        for i in range(5):
            state[f"session-{i}"] = i
        state.save()
        reloaded = HookState("small", max_entries=5)
        assert len(reloaded._data) == 5
        for i in range(5):
            assert reloaded[f"session-{i}"] == i

    def test_over_threshold_evicts_oldest(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("bounded", max_entries=3)
        for i in range(5):
            state[f"session-{i}"] = i
        state.save()
        reloaded = HookState("bounded", max_entries=3)
        assert len(reloaded._data) == 3
        # oldest two (session-0, session-1) evicted; newest three survive
        assert "session-0" not in reloaded
        assert "session-1" not in reloaded
        assert reloaded["session-2"] == 2
        assert reloaded["session-3"] == 3
        assert reloaded["session-4"] == 4

    def test_re_setting_existing_key_refreshes_recency(self, tmp_path, monkeypatch):
        """A session touched again must NOT look 'old' just because it was
        first created early -- re-setting moves it to the recent end."""
        monkeypatch.chdir(tmp_path)
        state = HookState("recency", max_entries=3)
        state["a"] = 1
        state["b"] = 2
        state["c"] = 3
        state["a"] = 100  # touch "a" again -- must now count as most-recent
        state["d"] = 4  # pushes count to 4, one over the cap of 3
        state.save()
        reloaded = HookState("recency", max_entries=3)
        assert len(reloaded._data) == 3
        assert "b" not in reloaded  # least-recently-touched, evicted
        assert reloaded["a"] == 100  # survived because it was re-touched
        assert reloaded["c"] == 3
        assert reloaded["d"] == 4

    def test_max_entries_none_disables_pruning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("unbounded", max_entries=None)
        for i in range(200):
            state[f"session-{i}"] = i
        state.save()
        reloaded = HookState("unbounded", max_entries=None)
        assert len(reloaded._data) == 200

    def test_default_max_entries_matches_documented_constant(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        state = HookState("defaulted")
        assert state._max_entries == HookState.DEFAULT_MAX_ENTRIES

    def test_fixed_key_caller_unaffected_by_pruning(self, tmp_path, monkeypatch):
        """commit_test_gate / validation_theater_guard style callers use a
        handful of fixed keys, never approaching the default cap -- pruning
        must be a complete no-op for them."""
        monkeypatch.chdir(tmp_path)
        state = HookState("fixed_keys")
        state["last_edit"] = 1.0
        state["last_test"] = 2.0
        state.save()
        reloaded = HookState("fixed_keys")
        assert reloaded["last_edit"] == 1.0
        assert reloaded["last_test"] == 2.0

    def test_signed_iteration_guard_shaped_value_survives_pruning_untouched(
        self, tmp_path, monkeypatch
    ):
        """Pruning only removes whole top-level keys -- it must never mutate
        the surviving iteration_guard-shaped {count, sig} value itself."""
        monkeypatch.chdir(tmp_path)
        state = HookState("eo_loop_shaped", max_entries=2)
        state["old-session"] = {"count": 1, "sig": "deadbeef"}
        state["session-a"] = {"count": 2, "sig": "aaaa"}
        state["session-b"] = {"count": 3, "sig": "bbbb"}
        state.save()
        reloaded = HookState("eo_loop_shaped", max_entries=2)
        assert "old-session" not in reloaded
        assert reloaded["session-a"] == {"count": 2, "sig": "aaaa"}
        assert reloaded["session-b"] == {"count": 3, "sig": "bbbb"}


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


class TestAtomicWrite:
    """Regression (HIGH, external re-audit 2026-07-07): save() used a plain
    write_text (truncate-then-write), so a hook killed/crashed mid-write left
    a partially-written, corrupt JSON file -- the NEXT load hit the
    corrupt-JSON except branch and silently reset to {}, discarding every
    key that was already saved, not just the interrupted one."""

    def test_no_leftover_temp_file_after_save(self, tmp_path, monkeypatch):
        """The write-to-temp-then-replace implementation detail must not
        leak a stray .tmp file into the state directory on the happy path."""
        monkeypatch.chdir(tmp_path)
        state = HookState("cleanup")
        state["v"] = 1
        state.save()

        state_dir = tmp_path / ".claude" / "state"
        leftover = [f for f in state_dir.iterdir() if f.suffix == ".tmp"]
        assert leftover == []

    def test_crash_during_write_leaves_prior_state_intact(self, tmp_path, monkeypatch):
        """Simulates a hook process dying mid-write (after the temp file is
        created but before os.replace runs) -- the ORIGINAL file, with its
        prior valid state, must be untouched, not corrupted or reset to {}."""
        monkeypatch.chdir(tmp_path)

        state = HookState("crashy")
        state["existing"] = "value that must survive"
        state.save()

        import os as os_module

        real_replace = os_module.replace

        def failing_replace(*args, **kwargs):
            raise OSError("simulated crash before replace completes")

        monkeypatch.setattr("hook_state.os.replace", failing_replace)

        state2 = HookState("crashy")
        state2["new_key"] = "this save will fail"
        state2.save()  # must NOT raise, and must NOT corrupt the original file

        monkeypatch.setattr("hook_state.os.replace", real_replace)

        reloaded = HookState("crashy")
        assert reloaded["existing"] == "value that must survive"

    def test_no_stray_temp_file_left_after_failed_replace(self, tmp_path, monkeypatch):
        """The temp file created before a failed os.replace() must be cleaned
        up, not accumulate on disk across repeated failed saves."""
        monkeypatch.chdir(tmp_path)

        def failing_replace(*args, **kwargs):
            raise OSError("simulated failure")

        monkeypatch.setattr("hook_state.os.replace", failing_replace)

        state = HookState("nostray")
        state["v"] = 1
        state.save()

        state_dir = tmp_path / ".claude" / "state"
        leftover = [f for f in state_dir.iterdir() if f.suffix == ".tmp"]
        assert leftover == []
