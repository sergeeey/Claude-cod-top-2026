"""Unit tests for hooks/agent_tool_scope_guard.py.

WHY: this hook is the enforcement backstop for the memory:-field auto Write/Edit
grant (see hooks/agent_tool_scope_guard.py's own docstring) -- a bug here silently
lets a memory-bearing agent self-implement again, the exact class of failure this
hook exists to close.
"""

import io
import json

from agent_tool_scope_guard import _find_declared_tools, main


class TestFindDeclaredTools:
    def test_boyko_agent_excludes_edit_write(self):
        declared = _find_declared_tools("boyko-agent")
        assert declared is not None
        assert "Edit" not in declared
        assert "Write" not in declared
        assert "Read" in declared

    def test_builder_includes_edit_write(self):
        declared = _find_declared_tools("builder")
        assert declared is not None
        assert "Edit" in declared
        assert "Write" in declared

    def test_reviewer_excludes_edit_write(self):
        declared = _find_declared_tools("reviewer")
        assert declared is not None
        assert "Edit" not in declared
        assert "Write" not in declared

    def test_unknown_agent_returns_none(self):
        assert _find_declared_tools("totally-unknown-agent-xyz") is None

    def test_agent_paren_syntax_not_counted_as_a_tool(self):
        # boyko-agent's tools: line includes "Agent(explorer, verifier, ...)" --
        # none of those sub-agent names must leak into the declared tool set.
        declared = _find_declared_tools("boyko-agent")
        assert "explorer" not in declared
        assert "verifier" not in declared


class TestMain:
    def _call_main(self, monkeypatch, data: dict) -> dict:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        from io import StringIO

        buf = StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        main()
        return json.loads(buf.getvalue())

    def test_boyko_agent_edit_denied(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Edit", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "boyko-agent" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_boyko_agent_write_denied(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Write", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_builder_edit_allowed(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "builder", "tool_name": "Edit", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_no_agent_type_allowed(self, monkeypatch):
        # Main session, not a subagent -- must never be gated.
        result = self._call_main(monkeypatch, {"tool_name": "Edit", "tool_input": {}})
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_ungated_tool_allowed(self, monkeypatch):
        # Bash is not in GATED_TOOLS -- boyko-agent's Bash call must pass through
        # even though this is exactly the tool this hook could restrict later.
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Bash", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_unknown_agent_fails_open(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {"agent_type": "totally-unknown-agent-xyz", "tool_name": "Edit", "tool_input": {}},
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_reviewer_edit_denied(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"agent_type": "reviewer", "tool_name": "Edit", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_empty_stdin_no_crash(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        main()  # must not raise

