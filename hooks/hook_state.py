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


class HookState:
    """Named dict-like persistent state backed by <cwd>/.claude/state/<name>.json.

    Usage::
        state = HookState("commit_test_gate")
        state["last_test"] = time.time()
        state.save()

    All I/O is best-effort: read failures return empty dict, write failures are
    silently swallowed so the hook never breaks the tool call that triggered it.
    """

    def __init__(self, name: str) -> None:
        self._path = Path.cwd() / ".claude" / "state" / f"{name}.json"
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

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def __setitem__(self, key: str, value: object) -> None:
        self._data[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    @property
    def path(self) -> Path:
        return self._path
