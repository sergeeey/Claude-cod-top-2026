"""Tests for hooks/goal_budget_guard.py.

WHY this file exists: goal_budget_guard.py previously had zero test coverage
and emitted a bare {"type": "info", ...} dict that isn't the Claude Code hook
protocol shape -- even if registered, the reminder would never actually reach
Claude. Both gaps are covered here.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))


def _run(monkeypatch, prompt: str) -> str:
    import goal_budget_guard

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": prompt})))
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        goal_budget_guard.main()
    return buf.getvalue()


class TestGoalBudgetGuard:
    def test_goal_without_budget_warns(self, monkeypatch):
        out = _run(monkeypatch, "/goal fix the failing tests")
        result = json.loads(out)
        assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "turn budget" in result["hookSpecificOutput"]["additionalContext"]

    def test_goal_with_stop_after_is_silent(self, monkeypatch):
        out = _run(monkeypatch, "/goal fix tests, stop after 10 turns")
        assert out == ""

    def test_goal_with_or_stop_phrase_is_silent(self, monkeypatch):
        out = _run(monkeypatch, "/goal ship it, or stop if blocked")
        assert out == ""

    def test_non_goal_prompt_is_silent(self, monkeypatch):
        out = _run(monkeypatch, "just refactor this function")
        assert out == ""

    def test_case_insensitive_goal_match(self, monkeypatch):
        out = _run(monkeypatch, "/GOAL do the thing")
        result = json.loads(out)
        assert "turn budget" in result["hookSpecificOutput"]["additionalContext"]

    def test_emits_valid_hook_protocol_shape(self, monkeypatch):
        """Regression: the old bare {"type": "info", "message": ...} dict is
        not a hookSpecificOutput envelope and would never surface to Claude."""
        out = _run(monkeypatch, "/goal fix tests")
        result = json.loads(out)
        assert "hookSpecificOutput" in result
        assert "type" not in result
