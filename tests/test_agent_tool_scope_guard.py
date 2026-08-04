"""Unit tests for hooks/agent_tool_scope_guard.py.

WHY: this hook is the enforcement backstop for the memory:-field auto Write/Edit
grant (see hooks/agent_tool_scope_guard.py's own docstring) -- a bug here silently
lets a memory-bearing agent self-implement again, the exact class of failure this
hook exists to close.
"""

import io
import json

from agent_tool_scope_guard import _bash_looks_like_write, _find_declared_tools, main


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


class TestBashLooksLikeWrite:
    """Direct tests for the pattern detector, isolated from agent-scope logic --
    catches a regex/substring regression without needing a full main() call."""

    def test_redirect_variants(self):
        assert _bash_looks_like_write("echo hi > file.txt")
        assert _bash_looks_like_write("echo hi >> file.txt")
        assert _bash_looks_like_write("cmd 1> out.log")
        assert _bash_looks_like_write("cmd 2> err.log")

    def test_tee_cp_mv_sed(self):
        assert _bash_looks_like_write("git log | tee out.txt")
        assert _bash_looks_like_write("cp a.txt b.txt")
        assert _bash_looks_like_write("mv a.txt b.txt")
        assert _bash_looks_like_write("sed -i 's/x/y/' file.txt")

    def test_plain_read_only_commands_do_not_match(self):
        # Negative control -- the whole point of the conditional gate is that
        # ordinary read-only Bash (exactly what boyko-agent needs for its real
        # job) must never trip this.
        assert not _bash_looks_like_write("git log --oneline -5")
        assert not _bash_looks_like_write("git status --short")
        assert not _bash_looks_like_write("gh pr checks 251")
        assert not _bash_looks_like_write("grep -rn pattern file.py")
        assert not _bash_looks_like_write("ls -la")
        assert not _bash_looks_like_write("git diff --stat")


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

    def test_bash_with_no_command_allowed(self, monkeypatch):
        # Empty tool_input (no command field) must not crash or false-positive.
        result = self._call_main(
            monkeypatch, {"agent_type": "boyko-agent", "tool_name": "Bash", "tool_input": {}}
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_readonly_command_allowed_for_readonly_agent(self, monkeypatch):
        # THE critical negative control: boyko-agent's real, legitimate use of
        # Bash (git/gh checks) must still pass through untouched.
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "boyko-agent",
                "tool_name": "Bash",
                "tool_input": {"command": "git log --oneline -20"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_bash_redirect_denied_for_readonly_agent(self, monkeypatch):
        # The gap this whole change closes: echo/redirect from an agent with no
        # declared Write/Edit must now be denied, not silently pass through.
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "boyko-agent",
                "tool_name": "Bash",
                "tool_input": {"command": "echo findings > report.md"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "Write/Edit" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_bash_tee_denied_for_readonly_agent(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "reviewer",
                "tool_name": "Bash",
                "tool_input": {"command": "git log | tee /tmp/out.txt"},
            },
        )
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_bash_write_pattern_allowed_for_agent_with_write(self, monkeypatch):
        # An agent that DOES declare Write/Edit (e.g. builder) must not be
        # blocked from Bash-based file writes -- the gate is about Write/Edit
        # capability, not about banning redirects universally.
        result = self._call_main(
            monkeypatch,
            {
                "agent_type": "builder",
                "tool_name": "Bash",
                "tool_input": {"command": "echo done > status.txt"},
            },
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
