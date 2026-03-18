"""Unit tests for hooks/drift_guard.py."""

from __future__ import annotations

import io
import json
import sys

import drift_guard


def _run_main_with_stdin(payload: dict) -> None:
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        drift_guard.main()
    finally:
        sys.stdin = old_stdin


SCOPE_FENCE = """# Active Context

## Scope Fence
Goal: ship feature X
Boundary: keep scope small
Done when: tests green
NOT NOW: config, competitors, tooling
"""


class TestDriftGuard:
    def test_no_scope_fence_allows(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _run_main_with_stdin({"tool_name": "Skill", "tool_input": {"skill": "brainstorming"}})
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_empty_scope_fence_allows(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".claude" / "memory").mkdir(parents=True)
        (tmp_path / ".claude" / "memory" / "activeContext.md").write_text("", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin({"tool_name": "Skill", "tool_input": {"skill": "brainstorming"}})
        assert capsys.readouterr().out == ""

    def test_non_matching_allows(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text(SCOPE_FENCE, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin({"tool_name": "Skill", "tool_input": {"skill": "tdd-workflow"}})
        assert capsys.readouterr().out == ""

    def test_matching_not_now_keyword_warns(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text(SCOPE_FENCE, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin({"tool_name": "Skill", "tool_input": {"skill": "brainstorming", "prompt": "compare competitors"}})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        msg = parsed["hookSpecificOutput"]["additionalContext"]
        assert "Possible scope drift" in msg
        assert "competitors" in msg

    def test_multiple_not_now_keywords_catches_all(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text(SCOPE_FENCE, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin(
            {
                "tool_name": "Agent",
                "tool_input": {"name": "scope-guard", "description": "tooling + config check"},
            }
        )
        msg = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
        assert "config" in msg
        assert "tooling" in msg

    def test_agent_tool_also_checked(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text(SCOPE_FENCE, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        _run_main_with_stdin({"tool_name": "Agent", "tool_input": {"name": "competitors-analyzer"}})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

