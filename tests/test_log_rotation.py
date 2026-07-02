"""Unit tests for rotate_log_if_large() — shared size-based log rotation.

WHY: hook_triggers.jsonl, model_usage.jsonl, hook_events.jsonl, audit.log,
and sessions.log are append-only and were never rotated — on a long-lived
machine they grow without bound (model_usage.jsonl appends once per tool
call). Without tests we cannot prove (a) rotation only triggers past the
size threshold, (b) backups shift correctly and the oldest is discarded,
(c) failures are silent, (d) each of the 5 call sites actually invokes it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from utils import rotate_log_if_large

# WHY: the 5 production call sites use rotate_log_if_large()'s default
# max_bytes (5 MiB) with no override, so an integration test proving they
# actually rotate must write a file at/over that same default threshold —
# not an arbitrary small size the direct unit tests above use with an
# explicit max_bytes= override.
_OVER_DEFAULT_THRESHOLD = "x" * (5 * 1024 * 1024)


class TestRotateLogIfLarge:
    """Direct unit tests for the shared rotation helper."""

    def test_no_rotation_when_file_missing(self, tmp_path: Path) -> None:
        """A log file that doesn't exist yet is left alone (no-op)."""
        log = tmp_path / "missing.jsonl"
        rotate_log_if_large(log, max_bytes=100)
        assert not log.exists()

    def test_no_rotation_under_threshold(self, tmp_path: Path) -> None:
        """A small file is never rotated — this must never touch normal logs."""
        log = tmp_path / "small.jsonl"
        log.write_text("small content\n", encoding="utf-8")
        rotate_log_if_large(log, max_bytes=1024)
        assert log.read_text(encoding="utf-8") == "small content\n"
        assert not (tmp_path / "small.jsonl.1").exists()

    def test_rotates_when_at_or_over_threshold(self, tmp_path: Path) -> None:
        """A file at/over max_bytes is moved to path.1; a fresh file can be appended after."""
        log = tmp_path / "big.jsonl"
        log.write_text("x" * 200, encoding="utf-8")
        rotate_log_if_large(log, max_bytes=100)
        assert not log.exists()
        rotated = tmp_path / "big.jsonl.1"
        assert rotated.exists()
        assert rotated.read_text(encoding="utf-8") == "x" * 200

    def test_shifts_existing_backups(self, tmp_path: Path) -> None:
        """path.1 -> path.2, path -> path.1 when a .1 backup already exists."""
        log = tmp_path / "big.jsonl"
        log.write_text("current", encoding="utf-8")
        (tmp_path / "big.jsonl.1").write_text("old-1", encoding="utf-8")
        rotate_log_if_large(log, max_bytes=1)
        assert (tmp_path / "big.jsonl.1").read_text(encoding="utf-8") == "current"
        assert (tmp_path / "big.jsonl.2").read_text(encoding="utf-8") == "old-1"
        assert not log.exists()

    def test_discards_oldest_backup_beyond_limit(self, tmp_path: Path) -> None:
        """With backups=2, a pre-existing .2 is dropped when rotation shifts .1 -> .2."""
        log = tmp_path / "big.jsonl"
        log.write_text("current", encoding="utf-8")
        (tmp_path / "big.jsonl.1").write_text("old-1", encoding="utf-8")
        (tmp_path / "big.jsonl.2").write_text("ancient", encoding="utf-8")
        rotate_log_if_large(log, max_bytes=1, backups=2)
        assert (tmp_path / "big.jsonl.1").read_text(encoding="utf-8") == "current"
        assert (tmp_path / "big.jsonl.2").read_text(encoding="utf-8") == "old-1"
        # WHY: "ancient" must be gone — it was the oldest backup beyond the cap.
        assert "ancient" not in (tmp_path / "big.jsonl.2").read_text(encoding="utf-8")

    def test_silent_on_oserror(self, tmp_path: Path) -> None:
        """A filesystem error during rotation must never raise — hooks stay fail-open."""
        log = tmp_path / "big.jsonl"
        log.write_text("x" * 200, encoding="utf-8")
        with patch("pathlib.Path.rename", side_effect=OSError("disk full")):
            rotate_log_if_large(log, max_bytes=100)  # must not raise
        assert log.exists()  # untouched since rename failed


class TestRotationWiredIntoCallSites:
    """Confirm each of the 5 unbounded-log writers actually rotates before appending."""

    def test_log_audit_event_rotates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import utils

        monkeypatch.setattr(utils.Path, "home", lambda: tmp_path)
        log_dir = tmp_path / ".claude" / "logs"
        log_dir.mkdir(parents=True)
        big = log_dir / "audit.log"
        big.write_text(_OVER_DEFAULT_THRESHOLD, encoding="utf-8")

        with patch("utils.rotate_log_if_large", wraps=utils.rotate_log_if_large) as spy:
            utils.log_audit_event("test_event", "details")

        spy.assert_called_once_with(big)
        assert (log_dir / "audit.log.1").exists()
        assert "test_event" in big.read_text(encoding="utf-8")

    def test_log_hook_trigger_rotates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import utils

        log_path = tmp_path / "hook_triggers.jsonl"
        log_path.write_text(_OVER_DEFAULT_THRESHOLD, encoding="utf-8")
        monkeypatch.setattr("utils.HOOK_TRIGGERS_LOG", log_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)

        with patch("utils.rotate_log_if_large", wraps=utils.rotate_log_if_large) as spy:
            utils.log_hook_trigger("vtg", "perfect_score", "warning", "sample")

        spy.assert_called_once_with(log_path)
        assert (tmp_path / "hook_triggers.jsonl.1").exists()

    def test_model_usage_tracker_rotates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import io

        import model_usage_tracker

        log_path = tmp_path / "model_usage.jsonl"
        log_path.write_text(_OVER_DEFAULT_THRESHOLD, encoding="utf-8")
        monkeypatch.setattr(model_usage_tracker, "LOG_FILE", log_path)
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        monkeypatch.setattr(
            "sys.stdin",
            io.StringIO(
                '{"tool_name": "Bash", "session_id": "abc12345", "tool_response": {}, "tool_input": {}}'
            ),
        )

        with patch(
            "model_usage_tracker.rotate_log_if_large",
            wraps=model_usage_tracker.rotate_log_if_large,
        ) as spy:
            model_usage_tracker.main()

        spy.assert_called_once_with(log_path)
        assert (tmp_path / "model_usage.jsonl.1").exists()

    def test_hook_observability_rotates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import io
        import json

        import hook_observability

        log_path = tmp_path / "hook_events.jsonl"
        log_path.write_text(_OVER_DEFAULT_THRESHOLD, encoding="utf-8")
        monkeypatch.setattr(hook_observability, "LOG_FILE", log_path)
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash"}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

        with patch(
            "hook_observability.rotate_log_if_large",
            wraps=hook_observability.rotate_log_if_large,
        ) as spy:
            with pytest.raises(SystemExit) as exc_info:
                hook_observability.main()

        assert exc_info.value.code == 0
        spy.assert_called_once_with(log_path)
        assert (tmp_path / "hook_events.jsonl.1").exists()

    def test_session_save_sessions_log_rotates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import session_save

        log_dir = tmp_path / ".claude" / "logs"
        log_dir.mkdir(parents=True)
        big = log_dir / "sessions.log"
        big.write_text(_OVER_DEFAULT_THRESHOLD, encoding="utf-8")

        monkeypatch.setattr("session_save.DRY_RUN", False)
        monkeypatch.setattr("session_save.find_project_memory", lambda: None)
        monkeypatch.setattr("os.path.exists", lambda _p: False)
        monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path) + p[1:])

        with patch(
            "session_save.rotate_log_if_large", wraps=session_save.rotate_log_if_large
        ) as spy:
            session_save.main()

        spy.assert_called_once_with(big)
        assert (log_dir / "sessions.log.1").exists()
        assert "SESSION_END" in big.read_text(encoding="utf-8")
