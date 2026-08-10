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

import hypothesis_router  # noqa: E402
from hypothesis_router import (  # noqa: E402
    extract_hypothesis_metadata,
    extract_kill_criterion,
    get_target_directory,
    increment_summary_stats,
    update_hypothesis_tracker,
)


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


# ── update_hypothesis_tracker() and its helpers ─────────────────────────────
#
# WHY these classes exist: every test above that touches update_hypothesis_tracker
# mocks it wholesale via unittest.mock.patch, so its own body -- and everything
# it calls (extract_hypothesis_metadata, extract_kill_criterion,
# increment_summary_stats) -- never actually executed. TRACKER_PATH is
# monkeypatched to a tmp_path file so these run against real file I/O without
# touching the real ~/.claude/memory/knowledge/research/hypotheses/Hypothesis
# Tracker.md.

SAMPLE_TRACKER = """# Hypothesis Tracker

## Active

## Portfolio Analytics

- Total hypotheses: 3
- NOT STARTED: 1

---
*Last updated: 2026-01-01*
"""


class TestExtractKillCriterion:
    def test_finds_english_kill_criterion(self):
        content = "Some intro.\n\nKill criterion: the effect vanishes under noise.\n\nMore."
        assert "the effect vanishes" in extract_kill_criterion(content)

    def test_finds_russian_falsification_marker(self):
        content = "Текст.\n\nКритерий фальсификации: эффект пропадает при шуме.\n\nЕщё."
        assert "эффект пропадает" in extract_kill_criterion(content)

    def test_truncates_to_100_chars(self):
        long_reason = "x" * 200
        content = f"Kill criterion: {long_reason}"
        result = extract_kill_criterion(content)
        assert len(result) <= 100

    def test_returns_not_specified_when_absent(self):
        assert extract_kill_criterion("No criterion mentioned here.") == "Not specified"


class TestExtractHypothesisMetadata:
    def test_uses_frontmatter_title_when_present(self):
        fm = {"title": "My Hypothesis", "status": "active"}
        meta = extract_hypothesis_metadata(fm, "# Fallback Title\n")
        assert meta["title"] == "My Hypothesis"

    def test_falls_back_to_first_heading(self):
        meta = extract_hypothesis_metadata({}, "# Heading From Body\nSome text.")
        assert meta["title"] == "Heading From Body"

    def test_falls_back_to_untitled_when_no_heading(self):
        meta = extract_hypothesis_metadata({}, "no heading at all")
        assert meta["title"] == "Untitled Hypothesis"

    def test_score_prefers_discovery_score_over_confidence(self):
        fm = {"discovery_score": "8", "confidence": "5"}
        meta = extract_hypothesis_metadata(fm, "")
        assert meta["score"] == "8"

    def test_status_defaults_to_not_started_and_uppercases(self):
        meta = extract_hypothesis_metadata({"status": "active"}, "")
        assert meta["status"] == "ACTIVE"
        meta2 = extract_hypothesis_metadata({}, "")
        assert meta2["status"] == "NOT STARTED"

    def test_domain_joins_first_three_tags(self):
        fm = {"tags": ["a", "b", "c", "d", "e"]}
        meta = extract_hypothesis_metadata(fm, "")
        assert meta["domain"] == "a, b, c"


class TestIncrementSummaryStats:
    def test_increments_total_hypotheses_count(self):
        result = increment_summary_stats(SAMPLE_TRACKER)
        assert "- Total hypotheses: 4" in result

    def test_increments_not_started_count(self):
        result = increment_summary_stats(SAMPLE_TRACKER)
        assert "- NOT STARTED: 2" in result

    def test_updates_last_updated_timestamp(self):
        result = increment_summary_stats(SAMPLE_TRACKER)
        assert "Auto-updated by hypothesis_router" in result
        assert "*Last updated: 2026-01-01*" not in result

    def test_appends_timestamp_when_absent(self):
        no_ts = "# Tracker\n\n- Total hypotheses: 1\n- NOT STARTED: 1\n"
        result = increment_summary_stats(no_ts)
        assert "Auto-updated by hypothesis_router" in result

    def test_missing_total_hypotheses_line_is_a_noop_for_that_field(self):
        content = "# Tracker\n\nNo stats here.\n"
        result = increment_summary_stats(content)
        assert "Total hypotheses" not in result


class TestGetTargetDirectory:
    def test_hypothesis_maps_to_hypotheses_dir(self):
        assert get_target_directory("hypothesis").name == "hypotheses"

    def test_analysis_maps_to_analysis_dir(self):
        assert get_target_directory("analysis").name == "analysis"

    def test_experiment_maps_to_experiments_dir(self):
        assert get_target_directory("experiment").name == "experiments"

    def test_unknown_type_defaults_to_hypotheses_dir(self):
        assert get_target_directory("something-else").name == "hypotheses"


class TestUpdateHypothesisTracker:
    def test_creates_entry_and_updates_stats(self, tmp_path, monkeypatch, capsys):
        tracker = tmp_path / "Hypothesis Tracker.md"
        tracker.write_text(SAMPLE_TRACKER, encoding="utf-8")
        monkeypatch.setattr(hypothesis_router, "TRACKER_PATH", tracker)

        metadata = {
            "title": "New Idea",
            "score": "7",
            "status": "NOT STARTED",
            "date": "2026-08-04",
            "domain": "hooks",
            "kill_criterion": "fails if X",
        }
        update_hypothesis_tracker(metadata, "new-idea.md")

        content = tracker.read_text(encoding="utf-8")
        assert "[[new-idea]]" in content
        assert "fails if X" in content
        assert "- Total hypotheses: 4" in content
        out = capsys.readouterr().out
        assert "Added 'new-idea.md'" in out

    def test_entry_inserted_before_portfolio_analytics(self, tmp_path, monkeypatch):
        tracker = tmp_path / "Hypothesis Tracker.md"
        tracker.write_text(SAMPLE_TRACKER, encoding="utf-8")
        monkeypatch.setattr(hypothesis_router, "TRACKER_PATH", tracker)

        metadata = {
            "title": "X",
            "score": "5",
            "status": "NOT STARTED",
            "date": "2026-08-04",
            "domain": "",
            "kill_criterion": "Not specified",
        }
        update_hypothesis_tracker(metadata, "x.md")

        content = tracker.read_text(encoding="utf-8")
        assert content.index("[[x]]") < content.index("## Portfolio Analytics")

    def test_missing_tracker_file_prints_and_returns(self, tmp_path, monkeypatch, capsys):
        missing = tmp_path / "does-not-exist.md"
        monkeypatch.setattr(hypothesis_router, "TRACKER_PATH", missing)

        update_hypothesis_tracker({"title": "X"}, "x.md")  # must not raise

        assert "Tracker not found" in capsys.readouterr().out

    def test_missing_insertion_marker_prints_and_returns(self, tmp_path, monkeypatch, capsys):
        tracker = tmp_path / "Hypothesis Tracker.md"
        tracker.write_text("# Tracker\n\nNo marker here.\n", encoding="utf-8")
        monkeypatch.setattr(hypothesis_router, "TRACKER_PATH", tracker)

        update_hypothesis_tracker({"title": "X"}, "x.md")  # must not raise

        assert "Insertion marker not found" in capsys.readouterr().out
