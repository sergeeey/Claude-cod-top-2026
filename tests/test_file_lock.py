"""Tests for hooks/utils.py — file_lock().

WHY: file_lock is a new primitive added to close a real race condition in
mcp_circuit_breaker.py/mcp_circuit_breaker_post.py (concurrent read-modify-write
on the shared circuit-breaker state file silently losing updates). These tests
cover the lock itself in isolation; tests/test_circuit_breaker_lock_race.py
covers the actual race being closed end-to-end.
"""

import os
import threading
import time

from utils import file_lock


class TestFileLock:
    def test_acquires_and_releases(self, tmp_path):
        lock_path = tmp_path / "state.lock"
        with file_lock(lock_path) as acquired:
            assert acquired is True
            assert lock_path.exists()
        # WHY: the sentinel file must be removed on exit, or every
        # subsequent lock attempt would see it as permanently held.
        assert not lock_path.exists()

    def test_releases_even_on_exception(self, tmp_path):
        lock_path = tmp_path / "state.lock"
        try:
            with file_lock(lock_path):
                raise ValueError("boom")
        except ValueError:
            pass
        assert not lock_path.exists()

    def test_second_acquire_blocks_until_first_releases(self, tmp_path):
        lock_path = tmp_path / "state.lock"
        order: list[str] = []

        def holder():
            with file_lock(lock_path):
                order.append("holder-acquired")
                time.sleep(0.1)
                order.append("holder-released")

        t = threading.Thread(target=holder)
        t.start()
        time.sleep(0.02)  # let the holder acquire first

        with file_lock(lock_path, timeout=1.0) as acquired:
            order.append("waiter-acquired")
            assert acquired is True

        t.join()
        # WHY this exact order matters: it proves the waiter genuinely
        # blocked until the holder released, not that both ran concurrently.
        assert order == ["holder-acquired", "holder-released", "waiter-acquired"]

    def test_times_out_and_yields_false_instead_of_raising(self, tmp_path):
        """WHY False, not an exception: a hook must never crash or hang the
        tool call it's guarding just because another process briefly holds
        the lock -- best-effort proceeding beats blocking indefinitely."""
        lock_path = tmp_path / "state.lock"

        with file_lock(lock_path):  # hold it open for the whole inner block
            with file_lock(lock_path, timeout=0.1, poll_interval=0.02) as acquired:
                assert acquired is False

    def test_two_different_lock_paths_do_not_contend(self, tmp_path):
        lock_a = tmp_path / "a.lock"
        lock_b = tmp_path / "b.lock"
        with file_lock(lock_a):
            with file_lock(lock_b, timeout=0.5) as acquired:
                assert acquired is True

    def test_stale_lock_is_reaped_and_reacquired(self, tmp_path):
        """Regression (cross-model review, 2026-07-06): if a process is
        killed while holding the lock, `finally` never runs and the lock
        file is never cleaned up. Without staleness detection, every future
        call would wait out its full timeout and yield False forever --
        silently and permanently disabling the race protection this exists
        to provide. Simulate an abandoned lock (file exists, but old) and
        confirm a new holder can still acquire it instead of timing out."""
        lock_path = tmp_path / "state.lock"
        lock_path.touch()
        old_time = time.time() - 120  # older than any realistic stale_after
        os.utime(lock_path, (old_time, old_time))

        with file_lock(lock_path, timeout=1.0, stale_after=5.0) as acquired:
            assert acquired is True

    def test_fresh_lock_is_not_reaped_early(self, tmp_path):
        """Sanity check: stale_after must not reap a lock genuinely held by
        a live process -- only a lock OLDER than stale_after counts as
        abandoned. Without this, a slow-but-alive holder could get its lock
        yanked out from under it, reintroducing the exact race being closed."""
        lock_path = tmp_path / "state.lock"

        with file_lock(lock_path):  # held for the whole inner block below
            with file_lock(
                lock_path, timeout=0.2, poll_interval=0.02, stale_after=60.0
            ) as acquired:
                assert acquired is False

    def test_permission_error_on_open_is_treated_like_file_exists(self, tmp_path, monkeypatch):
        """Regression (found live by a 20-thread concurrency test, 2026-07-06):
        on Windows, a file mid-deletion by another thread can make a
        concurrent O_CREAT|O_EXCL open() raise PermissionError instead of
        FileExistsError. Before this fix, PermissionError propagated
        uncaught and crashed the hook; it must be treated the same as
        "someone else currently holds this lock" and retried."""
        import os as os_module

        lock_path = tmp_path / "state.lock"
        real_open = os_module.open
        calls = {"count": 0}

        def flaky_open(path, flags, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise PermissionError(13, "Permission denied")
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(os_module, "open", flaky_open)

        with file_lock(lock_path, timeout=1.0, poll_interval=0.02) as acquired:
            assert acquired is True
        assert calls["count"] >= 2  # first call raised, a retry succeeded

    def test_retry_after_permission_error_does_not_busy_loop(self, tmp_path, monkeypatch):
        """Sanity check: every retry path (including the FileNotFoundError-
        during-stat case) must sleep before re-attempting open() -- a tight
        zero-delay retry loop under real contention is exactly what produced
        the transient Windows PermissionError this fix responds to."""
        import os as os_module

        lock_path = tmp_path / "state.lock"
        real_open = os_module.open
        sleep_calls: list[float] = []
        real_sleep = time.sleep

        def counting_sleep(seconds):
            sleep_calls.append(seconds)
            real_sleep(0)  # don't actually slow the test down

        def flaky_open(path, flags, *args, **kwargs):
            if len(sleep_calls) == 0 and not lock_path.exists():
                raise PermissionError(13, "Permission denied")
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(os_module, "open", flaky_open)
        monkeypatch.setattr(time, "sleep", counting_sleep)

        with file_lock(lock_path, timeout=1.0, poll_interval=0.02) as acquired:
            assert acquired is True
        assert len(sleep_calls) >= 1
