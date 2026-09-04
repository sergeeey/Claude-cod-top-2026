"""Tests for knowledge_librarian.py's _read_current_focus() header matching.

Cross-project incident (2026-09-04): a different project sharing this same
global hook uses suffixed `## Current Focus` headers (date-stamped, and/or
tagged with `[WS: <slug>]` per this repo's own memory-protocol.md Parallel
Workstreams convention). The original exact `line.strip() == "## Current
Focus"` check silently matched nothing, and main()'s `if not focus.strip():
sys.exit(0)` meant the hook injected NOTHING for that project's sessions --
not a degraded fallback, a complete no-op.
"""

from __future__ import annotations

from unittest.mock import patch

import knowledge_librarian


def _focus(monkeypatch, tmp_path, content: str) -> str:
    ctx_file = tmp_path / "activeContext.md"
    ctx_file.write_text(content, encoding="utf-8")
    with patch("knowledge_librarian.find_project_memory", return_value=ctx_file):
        return knowledge_librarian._read_current_focus()


class TestCurrentFocusHeaderMatching:
    def test_plain_exact_header_still_works(self, monkeypatch, tmp_path):
        result = _focus(
            monkeypatch,
            tmp_path,
            "## Current Focus\nworking on X\n## Next\nsomething else\n",
        )
        assert "working on X" in result

    def test_header_with_date_suffix(self, monkeypatch, tmp_path):
        result = _focus(
            monkeypatch,
            tmp_path,
            "## Current Focus (2026-09-04, GeoScan)\ninvestigating Y\n## Next\n",
        )
        assert "investigating Y" in result

    def test_header_with_workstream_tag(self, monkeypatch, tmp_path):
        result = _focus(
            monkeypatch,
            tmp_path,
            "## Current Focus [WS: geoscan-import]\nparsing Z\n## Next\n",
        )
        assert "parsing Z" in result

    def test_header_with_both_date_and_workstream_suffixes(self, monkeypatch, tmp_path):
        result = _focus(
            monkeypatch,
            tmp_path,
            "## Current Focus (2026-09-04, GeoScan) [WS: geoscan-import]\nfixing W\n## Next\n",
        )
        assert "fixing W" in result

    def test_similarly_named_but_different_header_is_rejected(self, monkeypatch, tmp_path):
        """'Current Focused Research' must NOT be treated as the Current Focus section."""
        result = _focus(
            monkeypatch,
            tmp_path,
            "## Current Focused Research\nunrelated content\n## Next\n",
        )
        assert result == ""

    def test_stops_at_next_level2_header(self, monkeypatch, tmp_path):
        result = _focus(
            monkeypatch,
            tmp_path,
            "## Current Focus (2026-09-04)\nline one\nline two\n## Decisions\nshould not appear\n",
        )
        assert "line one" in result
        assert "line two" in result
        assert "should not appear" not in result

    def test_no_current_focus_header_returns_empty(self, monkeypatch, tmp_path):
        result = _focus(monkeypatch, tmp_path, "## CURRENT STATE\nsomething\n")
        assert result == ""
