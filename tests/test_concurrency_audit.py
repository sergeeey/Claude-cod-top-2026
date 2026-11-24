"""Controlled concurrency reproductions for the hook state layer (audit 2026-10-17).

WHY this file exists: hooks run as separate processes and, inside one process,
in threads. Read-modify-write paths on shared state files were found without a
lock, and two helpers were found to fail under contention. Each test here drives
the real code path against real files (no mocked I/O) and either reproduces a
defect (it fails on the audited code) or is a control (it passes on the audited
code and guards the mechanism the fix relies on). The window of each race is
widened on purpose, with an injected delay or a stalled holder, so the outcome
does not depend on thread scheduling luck.
"""

import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import lib.state as state_mod  # noqa: E402
import post_commit_memory  # noqa: E402
from hook_state import HookState  # noqa: E402
from lib.state import atomic_write_json, file_lock  # noqa: E402


def _run_threads(target, count, args_for=lambda n: ()):
    threads = [threading.Thread(target=target, args=args_for(n)) for n in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class TestHookStateLostUpdate:
    """DEFECT: HookState.save() writes the whole snapshot it loaded at construction.
    Two invocations that load before either saves overwrite each other's keys.
    Consumers: iteration_guard (eo_loop: a lost entry resets a session's
    Evaluator-Optimizer counter to 0), commit_test_gate (a lost last_edit turns an
    untested edit into a passing gate)."""

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
    """DEFECT: HookState._load() maps any OSError to an empty dict. A transient
    read failure (a Windows sharing violation) therefore yields an empty snapshot,
    and the next save() writes it over the file, erasing every other key."""

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
    """DEFECT (Windows): save() calls os.replace() once and swallows the OSError.
    A reader holding the state file open (no FILE_SHARE_DELETE) makes that call
    fail, and the write is silently dropped. The repo's vector_store already
    retries this case; HookState does not."""

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
                time.sleep(0.12)  # releases well inside a bounded retry budget

        reader = threading.Thread(target=brief_reader)
        reader.start()
        assert opened.wait(5)
        state.save()
        reader.join()

        assert HookState("held", max_entries=None).get("b") == 2


class TestFileLockOwnership:
    def test_waiter_does_not_crash_when_a_stalled_holder_still_has_the_lock_open(self, tmp_path):
        """DEFECT (Windows): reaping a stale lock calls unlink() while the stalled
        holder still has the file open. PermissionError escapes file_lock() and
        crashes the waiting hook. On every platform the waiter must return normally,
        and when it does get the lock, a third process must not enter beside it
        once the stalled holder leaves."""
        lock = tmp_path / "stalled.lock"
        a_inside = threading.Event()
        a_may_leave = threading.Event()

        def stalled_holder():
            with file_lock(lock, timeout=1.0, stale_after=0.05) as acquired:
                assert acquired is True
                a_inside.set()
                a_may_leave.wait(5)

        holder = threading.Thread(target=stalled_holder)
        holder.start()
        assert a_inside.wait(5)
        time.sleep(0.2)  # the stalled holder's lock is now older than stale_after

        with file_lock(lock, timeout=0.3, poll_interval=0.02, stale_after=0.05) as waiter:
            if waiter:
                # reaped (POSIX semantics): this waiter holds the lock now
                a_may_leave.set()
                holder.join(5)
                with file_lock(lock, timeout=0.2, poll_interval=0.02, stale_after=60.0) as third:
                    assert third is False
        a_may_leave.set()
        holder.join(5)
        with file_lock(lock, timeout=1.0, poll_interval=0.02) as after:
            assert after is True

    def test_release_does_not_unlink_a_lock_file_that_now_belongs_to_someone_else(self, tmp_path):
        """DEFECT: file_lock()'s finally unlinks the lock path without checking who
        owns it. After a reap, the file can belong to another holder, and releasing
        must not delete it, or a third process enters while that holder is inside.
        Simulated by rewriting the lock file while this holder owns it."""
        lock = tmp_path / "owner.lock"
        with file_lock(lock, timeout=1.0) as acquired:
            assert acquired is True
            lock.write_text("another-holder", encoding="utf-8")
        assert lock.exists()
        assert lock.read_text(encoding="utf-8") == "another-holder"

    def test_abandoned_lock_wait_is_bounded_then_reclaimed(self, tmp_path):
        """CONTROL (deadlock scenario): a holder died without releasing. Waiters
        must give up at their own timeout, never hang, and reclaim the lock once
        it is older than stale_after."""
        lock = tmp_path / "abandoned.lock"
        os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))

        start = time.monotonic()
        with file_lock(lock, timeout=0.3, poll_interval=0.02, stale_after=60.0) as acquired:
            waited = time.monotonic() - start
            assert acquired is False
        assert waited < 2.0

        time.sleep(0.2)
        with file_lock(lock, timeout=1.0, poll_interval=0.02, stale_after=0.1) as acquired:
            assert acquired is True

    def test_mutual_exclusion_holds_under_eight_threads(self, tmp_path):
        """CONTROL: the lock itself serialises a read-modify-write under contention."""
        lock = tmp_path / "count.lock"
        counter = tmp_path / "count.txt"
        counter.write_text("0", encoding="utf-8")
        errors: list[str] = []

        def bump():
            for _ in range(25):
                with file_lock(lock, timeout=15.0) as acquired:
                    if not acquired:
                        errors.append("timeout")
                        return
                    value = int(counter.read_text(encoding="utf-8"))
                    counter.write_text(str(value + 1), encoding="utf-8")

        _run_threads(lambda: bump(), 8)
        assert errors == []
        assert int(counter.read_text(encoding="utf-8")) == 200


class TestAtomicWriteFromThreads:
    """DEFECT: atomic_write_json/atomic_write_text name the temp file with the PID
    only. Threads in one process share that name, so one thread's rename removes
    the file another thread is still writing. The repo hit this in
    test_circuit_breaker_lock_race (assert 19 == 20) and fixed only the caller's
    lock, not the helper."""

    def test_concurrent_writers_in_one_process_do_not_collide(self, tmp_path):
        path = tmp_path / "shared.json"
        errors: list[BaseException] = []

        def writer(n: int) -> None:
            for i in range(40):
                try:
                    atomic_write_json(path, {"writer": n, "i": i})
                except Exception as exc:  # every failure counts
                    errors.append(exc)

        _run_threads(writer, 8, args_for=lambda n: (n,))
        assert errors == []
        json.loads(path.read_text(encoding="utf-8"))


class TestAppendOnlyRecordsUnderContention:
    """DEFECT: post_commit_memory reads a file, appends in memory, and writes it
    back with no lock. The atomic write stops torn files but not lost updates,
    yet the code comments say it does. Two commits close together lose a record.
    The injected delay sits between the read and the write, where the race lives."""

    @staticmethod
    def _slow_write(real_write):
        def slow(path, text):
            time.sleep(0.02)
            real_write(path, text)

        return slow

    def test_concurrent_decision_records_are_not_lost(self, tmp_path, monkeypatch):
        decisions = tmp_path / "decisions.md"
        decisions.write_text("# Decisions\n", encoding="utf-8")
        monkeypatch.setattr(post_commit_memory, "find_decisions_file", lambda: decisions)
        slow = self._slow_write(state_mod.atomic_write_text)
        monkeypatch.setattr(post_commit_memory, "atomic_write_text", slow)
        monkeypatch.setattr(state_mod, "atomic_write_text", slow)
        errors: list[BaseException] = []

        def record(n: int) -> None:
            for i in range(5):
                try:
                    post_commit_memory.log_decision(
                        f"hash{n:02d}{i:02d}", f"arch: decision {n}-{i}"
                    )
                except Exception as exc:
                    errors.append(exc)

        _run_threads(record, 8, args_for=lambda n: (n,))
        assert errors == []
        text = decisions.read_text(encoding="utf-8")
        missing = [
            f"decision {n}-{i}"
            for n in range(8)
            for i in range(5)
            if f"decision {n}-{i}" not in text
        ]
        assert missing == []

    def test_concurrent_archive_lines_are_not_lost(self, tmp_path, monkeypatch):
        active_ctx = tmp_path / "activeContext.md"
        active_ctx.write_text("# Active\n", encoding="utf-8")
        now = datetime.now(UTC)
        slow = self._slow_write(state_mod.atomic_write_text)
        monkeypatch.setattr(post_commit_memory, "atomic_write_text", slow)
        monkeypatch.setattr(state_mod, "atomic_write_text", slow)
        errors: list[BaseException] = []

        def archive(n: int) -> None:
            for i in range(5):
                try:
                    post_commit_memory._archive_commit(active_ctx, f"- line {n}-{i}\n", now)
                except Exception as exc:
                    errors.append(exc)

        _run_threads(archive, 8, args_for=lambda n: (n,))
        assert errors == []
        archive_file = next((tmp_path / "history").glob("commits-*.md"))
        text = archive_file.read_text(encoding="utf-8")
        missing = [
            f"line {n}-{i}" for n in range(8) for i in range(5) if f"line {n}-{i}" not in text
        ]
        assert missing == []
