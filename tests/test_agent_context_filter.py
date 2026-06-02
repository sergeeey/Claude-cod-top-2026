"""Tests for agent_context_filter.py — Context Asymmetry enforcement.

Verifies adversarial agents (skeptic, skeptic-auditor, reviewer) are flagged
when spawned, while regular agents pass through silently.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from agent_context_filter import _emit, _extract_subagent


class TestExtractSubagent:
    def test_extracts_subagent_type_field(self) -> None:
        tool_input = {"subagent_type": "skeptic", "prompt": "red-team this"}
        assert _extract_subagent(tool_input) == "skeptic"

    def test_returns_empty_when_no_subagent_field(self) -> None:
        tool_input = {"prompt": "do something"}
        assert _extract_subagent(tool_input) == ""

    def test_returns_empty_for_empty_input(self) -> None:
        assert _extract_subagent({}) == ""


class TestEmit:
    def test_emit_writes_json_to_stdout(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _emit({"continue": True})
        out = buf.getvalue().strip()
        parsed = json.loads(out)
        assert parsed == {"continue": True}

    def test_emit_handles_additional_context(self) -> None:
        buf = io.StringIO()
        payload = {"continue": True, "additionalContext": "warning text"}
        with patch("sys.stdout", buf):
            _emit(payload)
        parsed = json.loads(buf.getvalue())
        assert parsed["additionalContext"] == "warning text"
