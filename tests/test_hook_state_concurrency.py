"""Concurrency regressions for HookState (audit 2026-10-17, F1-F3).

Each test drives the real save/load path against real files and fails on the code before the
fix. Hooks run as separate processes, so two invocations can load the same snapshot and save in
either order; these tests make that interleaving deterministic.
"""

import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import hook_state as hook_state_mod  # noqa: E402
from hook_state import HookState  # noqa: E402


class TestHookStateMergeEdges:
    """Edges of the merge: a second save on the same instance, the lock-timeout branch, and
    pruning that runs after the merge (review of fix/hook-state-merge)."""

    def test_second_save_does_not_revert_a_key_another_process_wrote(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        first = HookState("twice", max_entries=None)
        first["a"] = 1
        first.save()
        other = HookState("twice", max_entries=None)
        other["b"] = 2
        other.save()
        first.save()  # nothing new set on `first`: must not write its old snapshot over `b`
        final = HookState("twice", max_entries=None)
        assert final.get("a") == 1
        assert final.get("b") == 2

    def test_lock_timeout_still_merges_and_says_so(self, tmp_path, monkeypatch, capsys):
        from contextlib import contextmanager

        monkeypatch.chdir(tmp_path)
        seed = HookState("no_lock", max_entries=None)
        seed["keep_me"] = 1
        seed.save()

        @contextmanager
        def never_acquired(*_args, **_kwargs):
            yield False

        monkeypatch.setattr(hook_state_mod, "file_lock", never_acquired)
        writer = HookState("no_lock", max_entries=None)
        writer["new_key"] = 2
        writer.save()

        assert "lock timeout" in capsys.readouterr().err
        final = HookState("no_lock", max_entries=None)
        assert final.get("keep_me") == 1
        assert final.get("new_key") == 2

    def test_keys_survive_a_failed_replace_and_reach_disk_on_the_next_save(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        state = HookState("failed_replace", max_entries=None)
        state["kept"] = 1
        real_replace = hook_state_mod.replace_with_retry

        def refuse(*_args, **_kwargs):
            raise PermissionError(13, "sharing violation")

        monkeypatch.setattr(hook_state_mod, "replace_with_retry", refuse)
        state.save()  # the write fails: the dirty key must stay pending
        monkeypatch.setattr(hook_state_mod, "replace_with_retry", real_replace)
        state.save()  # the retry persists it
        assert HookState("failed_replace", max_entries=None).get("kept") == 1

    def test_timeout_budget_fits_under_the_five_second_hook_timeout(self):
        from lib import state as state_mod

        assert hook_state_mod._LOCK_TIMEOUT_S + state_mod._REPLACE_BUDGET_S + 0.5 < 5.0

    def test_prune_after_merge_evicts_the_oldest_disk_key_not_a_fresh_one(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        seed = HookState("capped", max_entries=3)
        seed["a"] = 1
        seed["b"] = 2
        seed["c"] = 3
        seed.save()
        first = HookState("capped", max_entries=3)
        second = HookState("capped", max_entries=3)  # both load a, b, c
        first["d"] = 4
        first.save()  # disk: b, c, d (a is the oldest and is evicted)
        second["a"] = 5  # refreshes a: a becomes the newest key
        second.save()
        final = HookState("capped", max_entries=3)
        assert set(final._data) == {"c", "d", "a"}


class TestHookStateLostUpdate:
    """DEFECT: HookState.save() wrote the whole snapshot it loaded at construction.
    Two invocations that load before either saves overwrote each other's keys.
    Consumers: iteration_guard (a lost entry resets a session's Evaluator-Optimizer
    counter to 0), commit_test_gate (a lost last_edit turns an untested edit into a
    passing gate)."""

    def test_two_handles_saving_different_keys_keep_both(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        first = HookState("lost_update", max_entries=None)
        second = HookState("lost_update", max_entries=None)  # loads the same snapshot
        first["session_a"] = {"count": 1, "sig": "a"}
        first.save()
        second["session_b"] = {"count": 1, "sig": "b"}
        second.save()  # stale snapshot: must not erase session_a
        final = HookState("lost_update", max_entries=None)
        assert "session_a" in final
        assert "session_b" in final

    def test_stale_snapshot_cannot_revert_a_newer_edit_stamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        edit_hook = HookState("gate", max_entries=None)
        test_hook = HookState("gate", max_entries=None)  # loaded before the edit stamp
        edit_hook["last_edit"] = 200.0
        edit_hook.save()
        test_hook["last_test"] = 150.0
        test_hook.save()
        final = HookState("gate", max_entries=None)
        assert final["last_edit"] == 200.0
        assert final["last_test"] == 150.0


class TestHookStateUnreadableLoad:
    """DEFECT: HookState._load() mapped any OSError to an empty dict. A transient read
    failure (a Windows sharing violation) therefore yielded an empty snapshot, and the
    next save() wrote it over the file, erasing every other key."""

    def test_failed_load_does_not_clobber_the_state_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        seed = HookState("clobber", max_entries=None)
        seed["keep_me"] = 1
        seed.save()

        real_read_text = Path.read_text

        def unreadable(self, *args, **kwargs):
            if self.name == "clobber.json":
                raise PermissionError(13, "sharing violation")
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", unreadable)
        writer = HookState("clobber", max_entries=None)  # load fails: empty snapshot
        monkeypatch.setattr(Path, "read_text", real_read_text)  # the file reads again
        writer["new_key"] = 2
        writer.save()

        final = HookState("clobber", max_entries=None)
        assert final.get("keep_me") == 1
        assert final.get("new_key") == 2

    def test_save_is_skipped_while_the_file_stays_unreadable(self, tmp_path, monkeypatch):
        """A save that cannot read the file on any retry must leave the file alone."""
        monkeypatch.chdir(tmp_path)
        seed = HookState("held_unreadable", max_entries=None)
        seed["keep_me"] = 1
        seed.save()
        writer = HookState("held_unreadable", max_entries=None)
        writer["new_key"] = 2

        real_read_text = Path.read_text

        def unreadable(self, *args, **kwargs):
            if self.name == "held_unreadable.json":
                raise PermissionError(13, "sharing violation")
            return real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", unreadable)
        writer.save()  # every read attempt fails: the save is skipped, the file is not written
        monkeypatch.setattr(Path, "read_text", real_read_text)

        final = HookState("held_unreadable", max_entries=None)
        assert final.get("keep_me") == 1
        assert final.get("new_key") is None

    def test_binary_garbage_in_the_state_file_is_treated_as_corrupt(self, tmp_path, monkeypatch):
        """Bytes that are not UTF-8 raise UnicodeDecodeError inside read_text, not JSON errors.
        They must be handled like corrupt JSON: no crash in the constructor or in save()."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "garbage.json").write_bytes(b"\xff\xfe\x00 not utf-8 \x80\x81")

        state = HookState("garbage", max_entries=None)  # must not raise
        assert state.get("anything") is None
        state["fresh"] = 1
        state.save()  # must not raise either
        assert HookState("garbage", max_entries=None).get("fresh") == 1


@pytest.mark.skipif(
    sys.platform != "win32", reason="os.replace refuses a file held open elsewhere only on Windows"
)
class TestHookStateWindowsReplace:
    """DEFECT (Windows): save() called os.replace() once and swallowed the OSError. A reader
    holding the state file open (no FILE_SHARE_DELETE) made that call fail, and the write was
    silently dropped."""

    def test_save_retries_past_a_brief_reader(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        seed = HookState("held", max_entries=None)
        seed["a"] = 1
        seed.save()
        state = HookState("held", max_entries=None)
        state["b"] = 2

        opened = threading.Event()

        def brief_reader():
            with open(state.path, "rb"):
                opened.set()
                time.sleep(0.12)  # releases well inside the bounded retry budget

        reader = threading.Thread(target=brief_reader)
        reader.start()
        assert opened.wait(5)
        state.save()
        reader.join()

        assert HookState("held", max_entries=None).get("b") == 2
