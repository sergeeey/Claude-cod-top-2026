#!/usr/bin/env python3
"""Centralized file-based state store for stateful hooks.

WHY: commit_test_gate and iteration_guard both duplicated identical
_load_state/_save_state/_state_path boilerplate (3 functions × 2 hooks = 36
lines of identical code). This module removes that duplication.

Hooks run as separate subprocess invocations, so threading.local() does NOT
persist across hook firings. File-based persistence at
.claude/state/<name>.json is the correct pattern — already used by
commit_test_gate and iteration_guard. This module centralizes it.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from lib.state import file_lock, replace_with_retry


def git_root(start: Path) -> Path:
    """Walk upward from `start` looking for a `.git` entry (dir or file, for
    worktrees). Falls back to `start` unchanged if none is found.

    WHY this lives here, not privately in commit_test_gate.py (Codex review,
    PR #364, corrected before merge): commit_test_gate.py's own four event
    types get DIFFERENT cwd from the harness (Bash-triggered events see the
    drifting shell cwd, Edit/Write/Stop see the fixed session cwd), so
    anchoring ITS OWN state to Path.cwd() silently disagreed with itself
    across event types -- see base_dir's WHY comment on HookState.__init__
    below for the original 2026-09-02 incident. But commit_test_gate.json is
    also read by two OTHER hooks (iteration_guard.py's
    _lgtm_follows_stale_tests, ace_reflector.py's _read_last_test) that
    still called bare HookState("commit_test_gate") -- if only
    commit_test_gate.py itself anchored to the git root while its readers
    stayed on Path.cwd(), a session launched from a repo SUBDIRECTORY would
    silently break the previously-working common case (same cwd for
    everyone) instead of fixing the worktree-specific gap it was meant to
    close. Centralizing here lets every consumer resolve the exact same
    path with one shared function instead of three independent, easily
    drifting copies.

    Falls back to `start` (Path.cwd()'s old implicit behavior) outside a
    git repo rather than raising -- state resolution must never crash a
    tool call over a missing `.git`."""
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


# WHY (audit 2026-10-17, F2): a read that fails transiently is retried before the save is
# skipped. Three attempts with growing delays cover the usual Windows sharing window.
_READ_ATTEMPTS = 3

# WHY (review of fix/hook-state-merge, P1): the commit, edit and verdict hooks run with a 5 s
# timeout. The worst-case save is this lock wait, plus the read retries, plus the replace retry
# in lib/state.py (_REPLACE_BUDGET_S). Together they must stay well under 5 s, or a save that
# waits for a stalled lock gets the hook killed and loses its write.
_LOCK_TIMEOUT_S = 1.5


class HookState:
    """Named dict-like persistent state backed by <cwd>/.claude/state/<name>.json.

    Usage::
        state = HookState("commit_test_gate")
        state["last_test"] = time.time()
        state.save()

    All I/O is best-effort: read failures return empty dict, write failures are
    silently swallowed so the hook never breaks the tool call that triggered it.
    Concurrent invocations are safe as of audit 2026-10-17: save() merges the keys
    this invocation set into the latest on-disk state under the file's lock, so two
    invocations no longer overwrite each other's keys (see save()). Reads come from
    the snapshot taken at construction, so a value can be stale by the time it is used.

    WHY pruning (2026-07-19, follow-up from a stale eo_loop.json fail-closing
    iteration_guard mid-session): per-session-keyed state (iteration_guard,
    locality_escalation_guard, ace_reflector's turn-state) grows by one entry
    every session, forever, with no eviction -- observed live as a legacy
    bare-int entry plus a leaked test-fixture key surviving for weeks. Callers
    with a handful of FIXED keys (commit_test_gate, validation_theater_guard)
    never approach a reasonable threshold, so a uniform default is safe for
    every existing consumer without per-hook configuration.

    Eviction policy: least-recently-SET key first. `__setitem__` re-inserts
    the key at the end of the dict (Python dicts preserve insertion order),
    so repeatedly touching the same key keeps it "recent" without a separate
    timestamp field -- the file format is unchanged, still a flat key->value
    dict, so `iteration_guard`'s signed {count, sig} values and this class's
    own on-disk shape stay identical; only which top-level keys survive can
    change.
    """

    #: Default cap on top-level keys before save() evicts the oldest.
    #: Chosen to comfortably exceed any single day's session count for a
    #: solo-developer repo while keeping the state file small. Pass
    #: `max_entries=None` to disable pruning entirely (opt-out, not needed
    #: by any current caller).
    DEFAULT_MAX_ENTRIES = 50

    def __init__(
        self,
        name: str,
        max_entries: int | None = DEFAULT_MAX_ENTRIES,
        base_dir: Path | None = None,
    ) -> None:
        # WHY base_dir (2026-09-02, commit_test_gate dogfooding incident): the
        # default Path.cwd() means every caller implicitly assumes the hook
        # subprocess's OS cwd IS the right scope boundary. That's true for a
        # hook whose state is meant to be per-directory, but commit_test_gate
        # needs ONE file across all four of its event types -- and the harness
        # gives Bash-triggered events the current *shell* cwd (which drifts as
        # `cd` runs) while Edit/Write/Stop events get the fixed *session* cwd.
        # A passing pytest run stamped from a shell that had `cd`'d into a
        # subdirectory landed in a different file than the one Stop reads,
        # so a real, verified pass was invisible to the gate. base_dir lets a
        # caller opt out of Path.cwd() and anchor to something stable (e.g.
        # the git root) instead; every other existing caller passes nothing
        # and keeps the exact previous behavior.
        base = base_dir if base_dir is not None else Path.cwd()
        self._path = base / ".claude" / "state" / f"{name}.json"
        # WHY clamp instead of trusting the caller: 0 (or negative) would make
        # _prune() evict the key __setitem__ just inserted, in the same
        # save() call -- "prune aggressively" is not what 0 should mean, and
        # no current caller passes anything but the default, so this only
        # guards a hypothetical future misuse, not a real-world value.
        if max_entries is not None and max_entries < 1:
            max_entries = 1
        self._max_entries = max_entries
        self._dirty: set[str] = set()  # keys set since the last load or save
        self._data: dict = self._load()

    def _read_disk(self) -> dict | None:
        """The state currently on disk.

        {} when there is no usable file (missing, or corrupt JSON). None when the file
        exists but cannot be read right now, for example a Windows sharing violation while
        another process replaces it. Callers must tell these apart: an empty snapshot
        written back over an unreadable file erases every key (audit 2026-10-17, F2).
        """
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except UnicodeDecodeError:
            return {}  # binary garbage is corrupt state, the same as bad JSON (raised by read_text)
        except OSError:
            return None
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return result if isinstance(result, dict) else {}

    def _load(self) -> dict:
        disk = self._read_disk()
        return disk if disk is not None else {}

    def save(self) -> None:
        """Persist this invocation's changes on top of the latest on-disk state.

        WHY merge under a lock (audit 2026-10-17, F1): a hook loads a snapshot, changes some
        keys, then saves. Before, two invocations that loaded before either saved overwrote
        each other's keys: 8 processes x 50 invocations kept 1 of 400 records
        (artifacts/concurrency-stress-baseline.json, S1). Now the save takes the state file's
        lock, re-reads the file, applies only the keys this invocation set, and writes the
        merged result. Recency order is kept, so pruning still evicts the least recently set key.

        WHY never write over a file that cannot be read (audit 2026-10-17, F2): an empty
        snapshot written over an unreadable file erases every other key. If the file still
        cannot be read after a short retry, this save is skipped.

        WHY the replace is retried (audit 2026-10-17, F3): on Windows os.replace() fails while
        a reader holds the file open; replace_with_retry() covers that window. A save that still
        fails is skipped, as before, so a hook is never broken by its own state.

        If the lock times out, the save still merges (best effort). That is no worse than the
        old unlocked race, and it never erases other keys.

        Merging keeps keys that other invocations set. Two invocations that set the SAME key
        still race: the last writer wins for that key (for example a per-session counter that
        two hooks write at once).
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with file_lock(self._path.with_suffix(".lock"), timeout=_LOCK_TIMEOUT_S) as acquired:
                if not acquired:
                    print(
                        f"[hook-state] {self._path.name}: lock timeout, saving without the lock",
                        file=sys.stderr,
                    )
                self._merge_and_write()
        except OSError:
            pass  # WHY: state is advisory; disk errors must never block tool calls

    def _merge_and_write(self) -> None:
        disk: dict | None = None
        for attempt in range(_READ_ATTEMPTS):
            disk = self._read_disk()
            if disk is not None:
                break
            time.sleep(0.02 * (attempt + 1))
        if disk is None:
            return  # unreadable right now: never overwrite the file with a partial view
        merged = dict(disk)
        for key in self._data:  # local recency order, so the merge keeps it
            if key in self._dirty:
                merged.pop(key, None)
                merged[key] = self._data[key]
        self._data = merged
        self._prune()

        tmp_name: str | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(self._data))
                f.flush()
                os.fsync(f.fileno())
            replace_with_retry(tmp_name, self._path)
            tmp_name = None  # replaced: nothing left to clean up
            self._dirty.clear()  # persisted only now: a failed write keeps the keys for a retry
        except OSError:
            pass  # WHY: a failed write is advisory; the temp file is removed below
        finally:
            # WHY: a replace that succeeded leaves no temp file. One that did not (or a write
            # that raised before it) must not leave a stray temp file behind.
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def _prune(self) -> None:
        """Evict the least-recently-set keys once over `_max_entries`.

        No-op when max_entries is None (opt-out) or the count is already at
        or under the cap -- the common case for every existing caller.
        """
        if self._max_entries is None or len(self._data) <= self._max_entries:
            return
        excess = len(self._data) - self._max_entries
        for stale_key in list(self._data.keys())[:excess]:
            del self._data[stale_key]

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def __setitem__(self, key: str, value: object) -> None:
        # WHY pop-then-set, not a plain assignment: re-inserting an EXISTING
        # key at the end is what makes "oldest in dict order" == "least
        # recently touched" -- a plain `self._data[key] = value` on an
        # already-present key would leave it at its ORIGINAL position,
        # so a session updated many times in a row would incorrectly look
        # "old" to _prune() despite being the most active one.
        self._data.pop(key, None)
        self._data[key] = value
        self._dirty.add(key)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    @property
    def path(self) -> Path:
        return self._path


def commit_test_gate_state() -> HookState:
    """commit_test_gate.json, anchored to the git root -- the ONE shared
    accessor for all three hooks that read or write this file
    (commit_test_gate.py itself, iteration_guard.py's
    _lgtm_follows_stale_tests, ace_reflector.py's _read_last_test).

    WHY a shared function, not each caller repeating `HookState(
    "commit_test_gate", base_dir=git_root(Path.cwd()))` (Codex review,
    PR #364): three independent copies of the same resolution logic is
    exactly how this drifted in the first place -- commit_test_gate.py
    anchored itself to the git root while its two readers stayed on
    Path.cwd(), silently breaking agreement even in the previously-working
    same-cwd case. One function, one place to fix next time."""
    return HookState("commit_test_gate", base_dir=git_root(Path.cwd()))
