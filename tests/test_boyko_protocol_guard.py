"""Unit tests for hooks/boyko_protocol_guard.py -- SubagentStop protocol check.

WHY: mechanically flags a boyko-agent stop whose own required Output Format
sections are missing, instead of trusting the prompt was followed.
"""

import io
import json

from boyko_protocol_guard import BOYKO_AGENT_TYPES, BRIEF_HEADER, main, missing_sections

FULL_BRIEF = """## Boyko Agent Brief

**Session goal:** test
**Pipeline:** explorer -> verifier
**Confidence:** HIGH

### Route trace
- Task Contract: x

### CTA Card
- Goal / acceptor: x
- Done when: x
- Scope limits: x
- Verifier: x

### Discriminating test
- Test: x

### Priorities
1. x

### Evidence status
- [VERIFIED] x

### Learning Proposal
none
"""


class TestMissingSections:
    def test_full_brief_has_no_missing_sections(self):
        assert missing_sections(FULL_BRIEF) == []

    def test_empty_message_reports_all_markers_missing(self):
        result = missing_sections("")
        assert len(result) == 9
        assert "### CTA Card" in result

    def test_partial_brief_reports_only_absent_markers(self):
        partial = "## Boyko Agent Brief\n\n**Session goal:** test\n**Pipeline:** x\n"
        result = missing_sections(partial)
        assert "**Confidence:**" in result
        assert "### CTA Card" in result
        assert "**Session goal:**" not in result

    def test_adjacent_opportunities_not_required(self):
        """navigator.md's own template allows omitting this section -- must
        not be in REQUIRED_MARKERS."""
        assert not any("Adjacent opportunities" in m for m in missing_sections(""))


class TestMain:
    def _call_main(self, monkeypatch, data: dict) -> dict:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        from io import StringIO
        from unittest.mock import patch

        buf = StringIO()
        with patch("sys.stdout", buf):
            try:
                main()
            except SystemExit:
                pass
        output = buf.getvalue().strip()
        return json.loads(output) if output else {}

    def test_non_boyko_message_produces_no_output(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"last_assistant_message": "VERDICT: LGTM", "session_id": "s1"}
        )
        assert result == {}

    def test_agent_type_alone_triggers_check_even_without_header(self, monkeypatch):
        """Regression pin (2026-07-18): the actual historical failure this
        hook exists to catch produced a last_assistant_message with NO
        header at all (cut off mid-tool-call before writing one) -- a
        header-only check would have silently ignored it. agent_type must
        be enough on its own to trigger the check."""
        cut_off_text = "Let me fetch the official hooks docs directly and read..."
        result = self._call_main(
            monkeypatch,
            {"agent_type": "boyko-agent", "last_assistant_message": cut_off_text, "session_id": "s1"},
        )
        output = result["hookSpecificOutput"]
        assert "NO recognizable output" in output["additionalContext"]

    def test_legacy_navigator_agent_type_also_recognized(self, monkeypatch):
        assert "navigator" in BOYKO_AGENT_TYPES
        result = self._call_main(
            monkeypatch,
            {"agent_type": "navigator", "last_assistant_message": "cut off", "session_id": "s1"},
        )
        assert result != {}

    def test_unrelated_agent_type_with_no_header_produces_no_output(self, monkeypatch):
        result = self._call_main(
            monkeypatch,
            {"agent_type": "explorer", "last_assistant_message": "found 3 files", "session_id": "s1"},
        )
        assert result == {}

    def test_complete_brief_produces_no_warning(self, monkeypatch):
        result = self._call_main(
            monkeypatch, {"last_assistant_message": FULL_BRIEF, "session_id": "s1"}
        )
        assert result == {}

    def test_incomplete_brief_warns_with_missing_sections_named(self, monkeypatch):
        incomplete = f"{BRIEF_HEADER}\n\n**Session goal:** test\nran out of budget mid-sentence"
        result = self._call_main(
            monkeypatch, {"last_assistant_message": incomplete, "session_id": "s1"}
        )
        output = result["hookSpecificOutput"]
        assert output["hookEventName"] == "SubagentStop"
        assert "CTA Card" in output["additionalContext"]
        assert "Evidence status" in output["additionalContext"]

    def test_empty_stdin_no_crash(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        try:
            main()
        except SystemExit:
            pass
