"""Unit tests for hooks/checkpoint_guard.py."""

from __future__ import annotations

import io
import json
import os
import sys
import time

import checkpoint_guard


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        checkpoint_guard.main()
    finally:
        sys.stdin = old_stdin


class TestCheckpointGuard:
    def test_non_risky_command_skipped(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)
        _run_main_with_stdin({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert capsys.readouterr().out == ""

    def test_handles_no_checkpoints_dir_graceful(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)
        _run_main_with_stdin({"tool_name": "Bash", "tool_input": {"command": "git rebase -i HEAD~3"}})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        msg = parsed["hookSpecificOutput"]["additionalContext"]
        assert "no checkpoints found" in msg

    def test_warns_without_checkpoint(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".claude" / "checkpoints").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin({"tool_name": "Bash", "tool_input": {"command": "git rebase -i HEAD~3"}})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        msg = parsed["hookSpecificOutput"]["additionalContext"]
        assert "Risky operation detected" in msg
        assert "no checkpoints found" in msg

    def test_allows_with_recent_checkpoint(self, tmp_path, monkeypatch, capsys):
        checkpoints = tmp_path / ".claude" / "checkpoints"
        checkpoints.mkdir(parents=True)
        ckpt = checkpoints / "2026-01-01_test.md"
        ckpt.write_text("x", encoding="utf-8")
        os.utime(ckpt, (time.time(), time.time()))  # now
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin({"tool_name": "Bash", "tool_input": {"command": "rm -rf build/"}})
        assert capsys.readouterr().out == ""

