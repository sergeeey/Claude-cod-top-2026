"""Regression test for scripts/redact.py's main() — the actual PreToolUse
stdin-to-stdout wiring, not just the pure redact()/clean() functions.

WHY this file exists: tests/test_redact.py only ever exercised redact(),
clean(), should_exclude() as pure functions. Nothing tested main()'s actual
stdin/stdout contract with Claude Code. A live behavioral probe against a
real Claude Code session (2026-07-01) proved the ORIGINAL main() — which
printed json.dumps(clean(data)) as a bare top-level object — never redacted
anything reaching the downstream MCP tool: a fake email and fake token
written through mcp__obsidian-vault__write_note came back completely raw.
This test pins the fixed behavior (hookSpecificOutput.updatedInput) so that
regression can never again reach production silently.
"""

import io
import json
from unittest import mock

import redact


def _run_main(tool_input: dict, extra_envelope: dict | None = None) -> tuple[int, str]:
    """Run redact.main() with a Claude Code PreToolUse-shaped stdin envelope."""
    stdin_data = {
        "tool_name": "mcp__obsidian-vault__write_note",
        "tool_input": tool_input,
        "session_id": "test-session",
        **(extra_envelope or {}),
    }
    captured_stdout = io.StringIO()
    exit_code = None
    with mock.patch("sys.stdin", io.StringIO(json.dumps(stdin_data))):
        with mock.patch("sys.stdout", captured_stdout):
            try:
                redact.main()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 0
    return exit_code, captured_stdout.getvalue()


class TestRedactMutationReachesUpdatedInput:
    """The exact scenario from the live probe: fake email + fake token."""

    def test_email_is_redacted_in_updated_input(self):
        exit_code, stdout = _run_main({"content": "contact: audit.redact.probe@example.com"})
        assert exit_code == 0
        output = json.loads(stdout)
        updated = output["hookSpecificOutput"]["updatedInput"]
        assert "[REDACTED:EMAIL]" in updated["content"]
        assert "audit.redact.probe@example.com" not in updated["content"]

    def test_secret_assignment_is_redacted_in_updated_input(self):
        exit_code, stdout = _run_main({"content": "token: sk-TESTMUTATIONPROBEAAAAAAAAAAAAAAAA"})
        assert exit_code == 0
        output = json.loads(stdout)
        updated = output["hookSpecificOutput"]["updatedInput"]
        assert "sk-TESTMUTATIONPROBEAAAAAAAAAAAAAAAA" not in updated["content"]
        assert "[REDACTED" in updated["content"]

    def test_clean_content_passes_through_unchanged(self):
        exit_code, stdout = _run_main({"content": "no secrets here"})
        assert exit_code == 0
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["updatedInput"]["content"] == "no secrets here"


class TestOutputSchemaShape:
    """Pin the exact envelope shape — the bug was entirely about this shape."""

    def test_uses_hook_specific_output_not_bare_tool_input(self):
        _, stdout = _run_main({"content": "irrelevant"})
        output = json.loads(stdout)
        assert "hookSpecificOutput" in output
        assert "tool_input" not in output  # the broken legacy shape

    def test_updated_input_does_not_include_envelope_noise(self):
        """The original bug: redact.py dumped the WHOLE envelope (session_id,
        tool_name, etc.) back out. updatedInput must contain ONLY the
        tool_input payload, not the surrounding envelope."""
        _, stdout = _run_main(
            {"content": "irrelevant"}, extra_envelope={"hook_event_name": "PreToolUse"}
        )
        output = json.loads(stdout)
        updated = output["hookSpecificOutput"]["updatedInput"]
        assert "session_id" not in updated
        assert "tool_name" not in updated
        assert "hook_event_name" not in updated
        assert updated == {"content": "irrelevant"}

    def test_permission_decision_is_allow(self):
        """redact.py never blocks -- it only sanitizes and allows."""
        _, stdout = _run_main({"content": "clean"})
        output = json.loads(stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestMalformedInput:
    def test_invalid_json_fails_open_with_no_output(self):
        """No structured tool_input -> nothing to redact -> allow silently
        rather than print non-JSON to a channel Claude Code expects JSON on."""
        captured_stdout = io.StringIO()
        exit_code = None
        with mock.patch("sys.stdin", io.StringIO("not valid json {{{")):
            with mock.patch("sys.stdout", captured_stdout):
                try:
                    redact.main()
                except SystemExit as exc:
                    exit_code = exc.code if isinstance(exc.code, int) else 0
        assert exit_code == 0
        assert captured_stdout.getvalue() == ""


class TestNestedToolInput:
    def test_nested_dict_and_list_values_are_redacted(self):
        exit_code, stdout = _run_main(
            {
                "notes": [
                    {"body": "email me at leaked.probe@example.com"},
                    {"body": "no pii"},
                ]
            }
        )
        assert exit_code == 0
        output = json.loads(stdout)
        notes = output["hookSpecificOutput"]["updatedInput"]["notes"]
        assert "[REDACTED:EMAIL]" in notes[0]["body"]
        assert notes[1]["body"] == "no pii"
