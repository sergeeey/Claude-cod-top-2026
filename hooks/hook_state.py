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
import tempfile
from pathlib import Path


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


class HookState:
    """Named dict-like persistent state backed by <cwd>/.claude/state/<name>.json.

    Usage::
        state = HookState("commit_test_gate")
        state["last_test"] = time.time()
        state.save()

    All I/O is best-effort: read failures return empty dict, write failures are
    silently swallowed so the hook never breaks the tool call that triggered it.
    Hooks run as separate subprocess invocations with no locking between them
    (pre-existing, not introduced by pruning): two near-simultaneous invocations
    for the same file each load a snapshot, and whichever saves last wins,
    silently discarding the other's write. Pruning adds one compounding case to
    this same lost-update class, not a new category -- a process working from a
    stale snapshot can evict a key another process had just legitimately
    refreshed, because that refresh isn't visible in the stale view. Low
    real-world probability for this repo's solo-developer usage; flagged so a
    future reader doesn't have to re-derive it from scratch.

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
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            result: dict = json.loads(self._path.read_text(encoding="utf-8"))
            return result
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self) -> None:
        """Persist current in-memory state to disk; silently ignore write failures.

        WHY atomic (write-to-temp + os.replace), not a direct write_text
        (HIGH, external re-audit 2026-07-07): a plain write_text truncates
        the file, then writes -- a hook killed/crashed mid-write (timeout,
        process termination) leaves a partially-written, corrupt JSON file
        behind. The NEXT HookState() load then hits the corrupt-JSON except
        branch and silently resets to {}, discarding every key that was
        already saved, not just the interrupted one. Writing to a sibling
        temp file first and only replacing the real path once the write is
        complete (os.replace is atomic on both POSIX and Windows) means a
        crash mid-write leaves the ORIGINAL file untouched -- worst case is
        losing this one save, never losing prior state.
        """
        self._prune()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json.dumps(self._data))
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, self._path)
            finally:
                # WHY: os.replace() above either succeeded (tmp_name no
                # longer exists, unlink is a no-op via the except) or the
                # write/fsync itself raised before reaching replace (tmp_name
                # still exists and must be cleaned up, not left behind).
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
        except OSError:
            pass  # WHY: state is advisory; disk errors must never block tool calls

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
