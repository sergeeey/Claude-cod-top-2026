"""Regression tests for hooks/utils.py:emit_permission_decision().

WHY: a live behavioral test against a real Claude Code session (2026-07-01)
found that legacy top-level {"tool_input": ...} mutation is silently dropped
for PreToolUse hooks — the original unmodified tool_input reaches the
downstream tool regardless. Legacy top-level {"decision": "block", ...} DOES
still work (backward compat), but mutation does not. Only
hookSpecificOutput.updatedInput is proven to work. These tests pin the exact
JSON shape so a future refactor can't silently regress back to the broken
legacy mutation shape.
"""

import io
import json
from unittest import mock

from utils import emit_permission_decision


def _capture(**kwargs) -> dict:
    buf = io.StringIO()
    with mock.patch("sys.stdout", buf):
        emit_permission_decision(**kwargs)
    return json.loads(buf.getvalue())


class TestAllowWithMutation:
    def test_updated_input_is_nested_under_hook_specific_output(self):
        """The one shape a live test proved actually mutates tool_input."""
        output = _capture(decision="allow", updated_input={"query": "clean"})
        assert output == {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"query": "clean"},
            }
        }

    def test_no_bare_top_level_tool_input_key(self):
        """The legacy shape that was proven broken must never reappear."""
        output = _capture(decision="allow", updated_input={"query": "clean"})
        assert "tool_input" not in output

    def test_allow_without_updated_input_omits_the_key(self):
        """Silent allow (no mutation needed) shouldn't emit an empty updatedInput."""
        output = _capture(decision="allow")
        assert "updatedInput" not in output["hookSpecificOutput"]

    def test_updated_input_preserves_nested_structure(self):
        nested = {"query": "x", "options": {"limit": 5, "tags": ["a", "b"]}}
        output = _capture(decision="allow", updated_input=nested)
        assert output["hookSpecificOutput"]["updatedInput"] == nested


class TestDeny:
    def test_deny_uses_permission_decision_reason_not_bare_decision(self):
        """The block path that a live test proved DOES still work via legacy
        top-level {"decision": "block"} — but the modern shape is what we emit."""
        output = _capture(decision="deny", reason="Prompt injection detected: command_injection")
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "command_injection" in output["hookSpecificOutput"]["permissionDecisionReason"]
        assert "decision" not in output  # no legacy top-level key
        assert "reason" not in output  # no legacy top-level key

    def test_deny_without_reason_omits_the_key(self):
        output = _capture(decision="deny")
        assert "permissionDecisionReason" not in output["hookSpecificOutput"]


class TestAsk:
    def test_ask_decision(self):
        output = _capture(decision="ask", reason="Needs human review")
        assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
        assert output["hookSpecificOutput"]["permissionDecisionReason"] == "Needs human review"


class TestAdditionalContext:
    def test_context_included_when_provided(self):
        output = _capture(decision="allow", context="extra info for Claude")
        assert output["hookSpecificOutput"]["additionalContext"] == "extra info for Claude"

    def test_context_omitted_when_empty(self):
        output = _capture(decision="allow")
        assert "additionalContext" not in output["hookSpecificOutput"]


class TestHookEventName:
    def test_always_pretooluse(self):
        for decision in ("allow", "deny", "ask"):
            output = _capture(decision=decision)
            assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
