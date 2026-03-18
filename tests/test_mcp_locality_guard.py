"""Unit tests for hooks/mcp_locality_guard.py."""

from __future__ import annotations

import io
import json
import sys

import mcp_locality_guard


def _run_main_with_stdin(raw: str) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(raw)
        try:
            mcp_locality_guard.main()
        except SystemExit:
            # The hook uses sys.exit(0) as control flow.
            pass
    finally:
        sys.stdin = old_stdin


class TestMcpLocalityGuard:
    def test_invalid_json_exits_cleanly(self, capsys):
        _run_main_with_stdin("not json")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_non_mcp_tool_skipped(self, capsys):
        _run_main_with_stdin(json.dumps({"tool_name": "Read"}))
        assert capsys.readouterr().err == ""

    def test_exempt_mcp_skipped(self, capsys):
        _run_main_with_stdin(json.dumps({"tool_name": "mcp__basic-memory__write"}))
        assert capsys.readouterr().err == ""

    def test_non_exempt_mcp_warns(self, capsys):
        _run_main_with_stdin(json.dumps({"tool_name": "mcp__context7__search"}))
        err = capsys.readouterr().err
        assert "Before using mcp__context7__search" in err
        assert "Read/Grep/Glob" in err

