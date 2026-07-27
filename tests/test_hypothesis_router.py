"""Tests for hooks/hypothesis_router.py.

WHY this file exists: hypothesis_router.py previously had zero test coverage
and, separately, never actually ran as an installed hook (main() expected a
plain {"file_path", "content"} dict, but nothing read the real PostToolUse
stdin envelope). Both gaps are fixed together here.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "hooks"))


class TestExtractFrontmatter:
    def test_extracts_simple_fields(self):
        from hypothesis_router import extract_frontmatter

        content = "---\ntype: hypothesis\nstatus: active\n---\n\nBody text"
        result = extract_frontmatter(content)
        assert result == {"type": "hypothesis", "status": "active"}

    def test_no_frontmatter_returns_empty(self):
        from hypothesis_router import extract_frontmatter

        assert extract_frontmatter("# Just a heading\nbody") == {}

    def test_lines_without_a_colon_are_ignored_not_raising(self):
        from hypothesis_router import extract_frontmatter

        # WHY: extract_frontmatter is a simple line-based extractor, not a
        # real YAML parser -- it only requires "key:" per line and doesn't
        # validate structure, so this checks it degrades gracefully rather
        # than raising on lines it can't classify as key: value.
        assert extract_frontmatter("---\njust some text\ntype: hypothesis\n---\n") == {
            "type": "hypothesis"
        }


class TestDetermineFileType:
    def test_explicit_hypothesis_type(self):
        from hypothesis_router import determine_file_type

        assert determine_file_type({"type": "hypothesis"}, "foo.md") == "hypothesis"

    def test_explicit_experiment_protocol_normalizes(self):
        from hypothesis_router import determine_file_type

        assert determine_file_type({"type": "experiment-protocol"}, "foo.md") == "experiment"

    def test_infers_analysis_from_filename(self):
        from hypothesis_router import determine_file_type

        assert determine_file_type({}, "Critical Review of X.md") == "analysis"

    def test_infers_experiment_from_filename(self):
        from hypothesis_router import determine_file_type

        assert determine_file_type({}, "protocol-v2.md") == "experiment"

    def test_defaults_to_hypothesis(self):
        from hypothesis_router import determine_file_type

        assert determine_file_type({}, "some-note.md") == "hypothesis"


class TestMainMemoryPathCheck:
    """Regression: str(file_path) uses backslashes on Windows, so the old
    literal ".claude/memory" substring check never matched a Windows-style
    path -- every hypothesis file on Windows was silently skipped."""

    def test_windows_style_path_is_recognized(self):
        from hypothesis_router import main

        content = "---\ntype: hypothesis\n---\n# Some Hypothesis\n"
        event = {
            "file_path": r"C:\Users\test\.claude\memory\knowledge\research\hypotheses\foo.md",
            "content": content,
        }
        with patch("hypothesis_router.update_hypothesis_tracker"):
            result = main(event)
        assert result["result"] == "success"

    def test_posix_style_path_is_recognized(self):
        from hypothesis_router import main

        content = "---\ntype: hypothesis\n---\n# Some Hypothesis\n"
        event = {
            "file_path": "/home/test/.claude/memory/knowledge/research/hypotheses/foo.md",
            "content": content,
        }
        with patch("hypothesis_router.update_hypothesis_tracker"):
            result = main(event)
        assert result["result"] == "success"

    def test_path_outside_memory_is_skipped(self):
        from hypothesis_router import main

        event = {
            "file_path": r"D:\some-project\notes\foo.md",
            "content": "---\ntype: hypothesis\n---\n",
        }
        result = main(event)
        assert result["result"] == "skip"

    def test_missing_file_path_or_content_is_skipped(self):
        from hypothesis_router import main

        assert main({})["result"] == "skip"
        assert main({"file_path": "x", "content": ""})["result"] == "skip"


class TestMainTypeRouting:
    def test_unrecognized_type_defaults_to_hypothesis(self):
        # WHY not "skip": determine_file_type() has no path that returns
        # anything other than hypothesis/analysis/experiment -- an
        # unrecognized frontmatter `type:` value falls through to its
        # filename-based inference and ultimately its "hypothesis" default,
        # so main()'s own `if file_type not in [...]: skip` branch is
        # currently unreachable. This test documents the actual behavior.
        from hypothesis_router import main

        event = {
            "file_path": r"C:\Users\test\.claude\memory\knowledge\research\notes\foo.md",
            "content": "---\ntype: reference\n---\n",
        }
        with patch("hypothesis_router.update_hypothesis_tracker") as mock_update:
            result = main(event)
        assert result["result"] == "success"
        mock_update.assert_called_once()

    def test_hypothesis_type_updates_tracker(self):
        from hypothesis_router import main

        event = {
            "file_path": r"C:\Users\test\.claude\memory\knowledge\research\hypotheses\foo.md",
            "content": "---\ntype: hypothesis\n---\n# My Hypothesis\n",
        }
        with patch("hypothesis_router.update_hypothesis_tracker") as mock_update:
            result = main(event)
        assert result["result"] == "success"
        mock_update.assert_called_once()

    def test_analysis_type_does_not_update_tracker(self):
        from hypothesis_router import main

        event = {
            "file_path": r"C:\Users\test\.claude\memory\knowledge\research\analysis\foo.md",
            "content": "---\ntype: analysis\n---\n# Some Analysis\n",
        }
        with patch("hypothesis_router.update_hypothesis_tracker") as mock_update:
            result = main(event)
        assert result["result"] == "success"
        mock_update.assert_not_called()

    def test_tracker_update_failure_is_reported_as_error(self):
        from hypothesis_router import main

        event = {
            "file_path": r"C:\Users\test\.claude\memory\knowledge\research\hypotheses\foo.md",
            "content": "---\ntype: hypothesis\n---\n# My Hypothesis\n",
        }
        with patch("hypothesis_router.update_hypothesis_tracker", side_effect=OSError("disk full")):
            result = main(event)
        assert result["result"] == "error"


class TestRealHookEntrypoint:
    """Regression: previously nothing read stdin at all in hook mode -- this
    is the entrypoint Claude Code actually invokes as a registered
    PostToolUse(Write) hook."""

    def _run(self, monkeypatch, payload: dict) -> str:
        import hypothesis_router

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            hypothesis_router._real_hook_entrypoint()
        return buf.getvalue()

    def test_non_write_tool_produces_no_output(self, monkeypatch):
        out = self._run(monkeypatch, {"tool_name": "Read", "tool_input": {}})
        assert out == ""

    def test_write_with_content_in_payload(self, monkeypatch, tmp_path):
        claim = tmp_path / ".claude" / "memory" / "knowledge" / "research" / "hypotheses" / "foo.md"
        claim.parent.mkdir(parents=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(claim),
                "content": "---\ntype: hypothesis\n---\n# X\n",
            },
        }
        with patch("hypothesis_router.update_hypothesis_tracker"):
            out = self._run(monkeypatch, payload)
        result = json.loads(out)
        assert "Processed hypothesis" in result["hookSpecificOutput"]["additionalContext"]

    def test_write_falls_back_to_reading_file_when_content_absent(self, monkeypatch, tmp_path):
        # WHY: PostToolUse events don't always carry tool_input.content --
        # the hook must be able to read the just-written file itself.
        claim = tmp_path / ".claude" / "memory" / "knowledge" / "research" / "hypotheses" / "foo.md"
        claim.parent.mkdir(parents=True)
        claim.write_text("---\ntype: hypothesis\n---\n# X\n", encoding="utf-8")
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(claim)}}
        with patch("hypothesis_router.update_hypothesis_tracker"):
            out = self._run(monkeypatch, payload)
        result = json.loads(out)
        assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_skip_result_produces_no_output(self, monkeypatch, tmp_path):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": r"D:\outside\foo.md", "content": "no frontmatter"},
        }
        out = self._run(monkeypatch, payload)
        assert out == ""

    def test_invalid_json_stdin_produces_no_output(self, monkeypatch):
        import hypothesis_router

        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            hypothesis_router._real_hook_entrypoint()
        assert buf.getvalue() == ""


class TestRecursionGuard:
    def test_recursion_guard_skips_before_reading_stdin(self, monkeypatch, tmp_path):
        """Regression: this hook had no CLAUDE_INVOKED_BY check at all, the
        documented anti-pattern in hooks/CLAUDE.md that risks an infinite
        loop when Claude Code invokes subagents. A payload that would
        otherwise produce output must be silently skipped when the guard
        env var is set."""
        import hypothesis_router

        claim = tmp_path / ".claude" / "memory" / "knowledge" / "research" / "hypotheses" / "foo.md"
        claim.parent.mkdir(parents=True)
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(claim),
                "content": "---\ntype: hypothesis\n---\n# X\n",
            },
        }
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "1")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        buf = io.StringIO()
        with patch("hypothesis_router.update_hypothesis_tracker"), patch("sys.stdout", buf):
            hypothesis_router._real_hook_entrypoint()
        assert buf.getvalue() == ""
