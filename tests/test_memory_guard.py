"""Unit tests for hooks/memory_guard.py."""

from __future__ import annotations

import io
import json
import os
import sys
import time

import memory_guard


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        memory_guard.main()
    finally:
        sys.stdin = old_stdin


class TestMemoryGuard:
    def test_non_commit_skipped(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _run_main_with_stdin({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert capsys.readouterr().out == ""

    def test_no_project_memory_skips_with_context(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _run_main_with_stdin(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m x"},
                "tool_response": {"stdout": "[ok]"},
            }
        )
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "no .claude/memory/activeContext.md found" in parsed["hookSpecificOutput"]["additionalContext"]

    def test_warns_after_commit_when_memory_is_stale(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text("x", encoding="utf-8")
        # Make it stale (>5 minutes)
        stale = time.time() - (6 * 60)
        os.utime(ctx, (stale, stale))
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m x"},
                "tool_response": {"stdout": "[ok]"},
            }
        )

        out = capsys.readouterr().out
        parsed = json.loads(out)
        msg = parsed["hookSpecificOutput"]["additionalContext"]
        assert "activeContext.md is" in msg
        assert "UPDATE REQUIRED" in msg

    def test_allows_with_recent_memory_update(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text("x", encoding="utf-8")
        # Fresh (<5 minutes)
        fresh = time.time()
        os.utime(ctx, (fresh, fresh))
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit -m x"},
                "tool_result": {"stdout": "[ok]"},
            }
        )
        assert capsys.readouterr().out == ""

    def test_handles_invalid_json(self, capsys):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("not json")
            memory_guard.main()
        finally:
            sys.stdin = old_stdin
        assert capsys.readouterr().out == ""

