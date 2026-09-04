"""Tests for hooks/post_commit_memory.py — auto-logging commits to activeContext.md."""

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

from unittest.mock import patch

from post_commit_memory import (
    _ACTIVE_LOG_CAP,
    _archive_commit,
    _trim_active_log,
    extract_decision,
    find_decisions_file,
    log_decision,
    main,
)


def make_stdin(data: dict):
    return io.StringIO(json.dumps(data))


class TestFindDecisionsFileResolution:
    """Regression (memory-retrieval-repair-tz.md PR-6b precondition): before
    retiring the legacy repo-root `memory/{activeContext.md,decisions.md}`
    directory, docs/memory-architecture.md's own stated precondition is
    that find_decisions_file() actually resolves to `.claude/memory/`, not
    the legacy root -- from BOTH the repo root and a nested cwd. No prior
    test exercised the REAL resolution logic (existing tests in this file
    mock find_decisions_file() itself, not its actual walk-upward
    behavior)."""

    def test_resolves_to_dotclaude_memory_from_repo_root(self, tmp_path, monkeypatch):
        # WHY the target lives under _auto/ here, matching this repo's own
        # real layout (find_decisions_file() checks _auto/decisions.md
        # FIRST): placing it directly at the cwd level means the very
        # first find_file_upward() check succeeds without ever climbing
        # past tmp_path -- keeping this test hermetic against whatever
        # real ~/.claude/ happens to contain on the machine running it.
        auto_dir = tmp_path / ".claude" / "memory" / "_auto"
        auto_dir.mkdir(parents=True)
        decisions = auto_dir / "decisions.md"
        decisions.write_text("# Decisions\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        found = find_decisions_file()
        assert found == decisions

    def test_resolves_to_dotclaude_memory_from_nested_cwd(self, tmp_path, monkeypatch):
        # WHY still hermetic despite climbing (unlike the repo-root test
        # above, this one DOES need find_file_upward() to walk upward):
        # the target sits at tmp_path itself, strictly above the nested
        # cwd but strictly below tmp_path's real filesystem parent -- the
        # walk finds it before ever climbing out of the tmp tree.
        auto_dir = tmp_path / ".claude" / "memory" / "_auto"
        auto_dir.mkdir(parents=True)
        decisions = auto_dir / "decisions.md"
        decisions.write_text("# Decisions\n", encoding="utf-8")
        nested = tmp_path / "hooks" / "lib"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        found = find_decisions_file()
        assert found == decisions

    def test_prefers_auto_subfolder_over_legacy_direct_path(self, tmp_path, monkeypatch):
        """WHY _auto/decisions.md wins when both exist (find_decisions_file()'s
        own WHY comment): the global vault uses the _auto/ subfolder; a
        project vault without _auto/ falls back to the direct path. Both
        existing at once should prefer _auto/, not silently pick either."""
        memory_dir = tmp_path / ".claude" / "memory"
        (memory_dir / "_auto").mkdir(parents=True)
        auto_decisions = memory_dir / "_auto" / "decisions.md"
        auto_decisions.write_text("# Auto Decisions\n", encoding="utf-8")
        direct_decisions = memory_dir / "decisions.md"
        direct_decisions.write_text("# Direct Decisions\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        found = find_decisions_file()
        assert found == auto_decisions

    def test_does_not_resolve_to_legacy_root_memory_dir(self, tmp_path, monkeypatch):
        """The legacy repo-root `memory/decisions.md` (no `.claude/` prefix)
        must NEVER be what find_decisions_file() returns -- confirming it is
        safe to retire that directory entirely.

        WHY this asserts `found != legacy_decisions` rather than
        `found is None` (real risk, caught before this test would have
        been flaky elsewhere): find_file_upward() has no tmp_path boundary
        -- if neither target exists anywhere under tmp_path, it keeps
        climbing into the REAL filesystem above it, and a real
        ~/.claude/memory/(_auto/)decisions.md on the machine running this
        test would make a strict `is None` assertion fail for a reason
        unrelated to this test's actual claim. The claim under test is
        narrower and machine-independent: the legacy bare path is never
        selected, whatever else may or may not be found above tmp_path."""
        legacy_memory = tmp_path / "memory"
        legacy_memory.mkdir()
        legacy_decisions = legacy_memory / "decisions.md"
        legacy_decisions.write_text("# Legacy\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        found = find_decisions_file()
        assert found != legacy_decisions


# === extract_decision (already partially tested in test_hooks.py, add edge cases) ===


class TestExtractDecision:
    def test_arch_prefix(self):
        assert extract_decision("arch: use PostgreSQL") == ("arch", "use PostgreSQL")

    def test_conventional_plus_arch(self):
        assert extract_decision("feat: arch: new DB schema") == ("arch", "new DB schema")

    def test_security_prefix(self):
        assert extract_decision("security: enable MFA") == ("security", "enable MFA")

    def test_no_decision_prefix(self):
        assert extract_decision("feat: add button") is None

    def test_pattern_prefix(self):
        assert extract_decision("pattern: retry with backoff") == ("pattern", "retry with backoff")


# === log_decision ===


class TestLogDecision:
    def test_no_decision_returns_none(self):
        assert log_decision("abc1234", "feat: add button") is None

    def test_decision_no_file_returns_message(self):
        with patch("post_commit_memory.find_decisions_file", return_value=None):
            result = log_decision("abc1234", "arch: use Redis")
        assert "no decisions.md found" in result
        assert "arch" in result

    def test_decision_writes_to_file(self, tmp_path):
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Decisions\n", encoding="utf-8")

        with patch("post_commit_memory.find_decisions_file", return_value=decisions_file):
            result = log_decision("abc1234", "arch: use Redis for caching")

        assert "Auto-recorded" in result
        content = decisions_file.read_text(encoding="utf-8")
        assert "use Redis for caching" in content
        assert "`abc1234`" in content

    def test_decision_uses_atomic_write_text(self, tmp_path):
        """WHY: a plain write_text() read-modify-write can lose an update
        when two hook invocations write decisions.md close together. This
        pins that log_decision() goes through the atomic helper, not a raw
        write_text() call."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Decisions\n", encoding="utf-8")

        with (
            patch("post_commit_memory.find_decisions_file", return_value=decisions_file),
            patch("post_commit_memory.atomic_write_text") as mock_atomic,
        ):
            log_decision("abc1234", "arch: use Redis for caching")

        mock_atomic.assert_called_once()
        called_path, called_content = mock_atomic.call_args[0]
        assert called_path == decisions_file
        assert "use Redis for caching" in called_content


# === _archive_commit / _trim_active_log (docs/memory-architecture.md history/ target) ===


class TestArchiveCommit:
    def test_creates_new_daily_archive_with_header(self, tmp_path):
        from datetime import datetime

        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")
        now = datetime(2026, 8, 22, 14, 30)

        _archive_commit(ctx_file, "- [2026-08-22 14:30] `abc1234`: feat: thing\n", now)

        archive = tmp_path / "history" / "commits-20260822.md"
        assert archive.exists()
        content = archive.read_text(encoding="utf-8")
        assert content.startswith("# Commit log — 2026-08-22\n")
        assert "`abc1234`: feat: thing" in content

    def test_appends_to_existing_daily_archive(self, tmp_path):
        from datetime import datetime

        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")
        now = datetime(2026, 8, 22, 9, 0)

        _archive_commit(ctx_file, "- [09:00] `first111`: first\n", now)
        _archive_commit(ctx_file, "- [09:05] `second22`: second\n", now)

        archive = tmp_path / "history" / "commits-20260822.md"
        content = archive.read_text(encoding="utf-8")
        assert "`first111`" in content
        assert "`second22`" in content
        # WHY only one header: the second call must append, not overwrite
        assert content.count("# Commit log") == 1

    def test_different_days_get_different_archive_files(self, tmp_path):
        from datetime import datetime

        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        _archive_commit(ctx_file, "- entry day 1\n", datetime(2026, 8, 21, 23, 0))
        _archive_commit(ctx_file, "- entry day 2\n", datetime(2026, 8, 22, 0, 5))

        history_dir = tmp_path / "history"
        assert (history_dir / "commits-20260821.md").exists()
        assert (history_dir / "commits-20260822.md").exists()

    def test_nothing_lost_even_if_active_context_write_never_happens(self, tmp_path):
        """WHY this matters: _archive_commit runs BEFORE the activeContext.md
        write in main() specifically so a crash in between never loses the
        commit record -- simulate that ordering directly here."""
        from datetime import datetime

        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        _archive_commit(
            ctx_file, "- [12:00] `onlyarch1`: only archived\n", datetime(2026, 8, 22, 12, 0)
        )

        # activeContext.md itself was never touched by this call
        assert ctx_file.read_text(encoding="utf-8") == "# Context\n"
        # but the permanent record exists regardless
        assert "onlyarch1" in (tmp_path / "history" / "commits-20260822.md").read_text(
            encoding="utf-8"
        )


class TestTrimActiveLog:
    def _lines(self, *entries: str) -> list[str]:
        return ["## Auto-commit log", *entries, "", "## Next section"]

    def test_under_cap_keeps_everything(self):
        lines = self._lines("- [1] `a`: one", "- [2] `b`: two")
        result = _trim_active_log(lines, header_idx=0, cap=5)
        assert result == lines

    def test_over_cap_drops_oldest(self):
        entries = [f"- [{i}] `sha{i}`: msg{i}" for i in range(5)]
        lines = self._lines(*entries)
        result = _trim_active_log(lines, header_idx=0, cap=3)
        # newest-first ordering: keep the first 3, drop the last 2
        assert entries[0] in result
        assert entries[1] in result
        assert entries[2] in result
        assert entries[3] not in result
        assert entries[4] not in result

    def test_preserves_content_after_the_entry_run(self):
        entries = [f"- [{i}] `sha{i}`: msg{i}" for i in range(5)]
        lines = self._lines(*entries)
        result = _trim_active_log(lines, header_idx=0, cap=2)
        assert "## Next section" in result

    def test_summarized_marker_lines_count_as_entries(self):
        lines = self._lines(
            "- [1] `a`: one",
            "[summarized] [summarized] - [2] `b`: two",
            "- [3] `c`: three",
        )
        result = _trim_active_log(lines, header_idx=0, cap=1)
        assert "- [1] `a`: one" in result
        assert not any("`b`" in line for line in result)
        assert not any("`c`" in line for line in result)

    def test_default_cap_constant_is_positive(self):
        assert _ACTIVE_LOG_CAP > 0


# === main() ===


class TestMain:
    def test_skips_non_commit(self, monkeypatch):
        data = {"tool_input": {"command": "ls -la"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        # Should return without output
        main()

    def test_skips_failed_commit(self, monkeypatch):
        data = {
            "tool_input": {"command": "git commit -m 'test'"},
            "tool_response": {"stdout": "nothing to commit"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        main()

    def test_skips_empty_commit_hash(self, monkeypatch):
        data = {
            "tool_input": {"command": "git commit -m 'test'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))
        with patch("post_commit_memory.run_git", return_value=""):
            main()

    def test_warns_when_no_active_context(self, monkeypatch, capsys):
        data = {
            "tool_input": {"command": "git commit -m 'test'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "abc1234"
            if "--format=%s" in args:
                return "feat: something"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=None),
        ):
            main()

        output = capsys.readouterr().out
        assert "no activeContext.md found" in output

    def test_creates_new_section_in_active_context(self, monkeypatch, capsys, tmp_path):
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Active Context\n\nSome content\n", encoding="utf-8")

        data = {
            "tool_input": {"command": "git commit -m 'feat: add feature'"},
            "tool_response": {"stdout": "1 file changed, 5 insertions"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "def5678"
            if "--format=%s" in args:
                return "feat: add feature"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
        ):
            main()

        content = ctx_file.read_text(encoding="utf-8")
        assert "## Auto-commit log" in content
        assert "`def5678`" in content
        assert "feat: add feature" in content

        output = capsys.readouterr().out
        assert "Auto-logged commit def5678" in output

    def test_main_uses_atomic_write_text(self, monkeypatch, capsys, tmp_path):
        """WHY: same lost-update risk as decisions.md — pins that main()'s
        activeContext.md write goes through the atomic helper.

        WHY 2 calls, not 1 (updated 2026-08-22): main() now also archives
        the commit to history/commits-<date>.md via the same atomic helper,
        before touching activeContext.md -- see _archive_commit's own WHY.
        This test now checks the activeContext.md-specific call among both,
        rather than assuming there is only one call total."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Active Context\n\nSome content\n", encoding="utf-8")

        data = {
            "tool_input": {"command": "git commit -m 'feat: add feature'"},
            "tool_response": {"stdout": "1 file changed, 5 insertions"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "def5678"
            if "--format=%s" in args:
                return "feat: add feature"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
            patch("post_commit_memory.atomic_write_text") as mock_atomic,
        ):
            main()

        assert mock_atomic.call_count == 2
        active_context_calls = [c for c in mock_atomic.call_args_list if c[0][0] == ctx_file]
        assert len(active_context_calls) == 1
        assert "def5678" in active_context_calls[0][0][1]

    def test_appends_to_existing_section(self, monkeypatch, capsys, tmp_path):
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text(
            "# Active Context\n\n## Auto-commit log\n- [2026-03-18] `old123`: old commit\n",
            encoding="utf-8",
        )

        data = {
            "tool_input": {"command": "git commit -m 'fix: bug'"},
            "tool_response": {"stdout": "2 files changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "new456"
            if "--format=%s" in args:
                return "fix: bug"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
        ):
            main()

        content = ctx_file.read_text(encoding="utf-8")
        assert "`new456`" in content
        assert "`old123`" in content
        # New entry should be inserted after header, before old
        lines = content.split("\n")
        new_idx = next(i for i, line in enumerate(lines) if "new456" in line)
        old_idx = next(i for i, line in enumerate(lines) if "old123" in line)
        assert new_idx < old_idx

    def test_decision_message_appended(self, monkeypatch, capsys, tmp_path):
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        data = {
            "tool_input": {"command": "git commit -m 'arch: switch to Redis'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "arch789"
            if "--format=%s" in args:
                return "arch: switch to Redis"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch(
                "post_commit_memory.log_decision",
                return_value="Auto-recorded [arch] decision to decisions.md",
            ),
        ):
            main()

        output = capsys.readouterr().out
        assert "Auto-recorded [arch]" in output

    def test_empty_stdin_exits_gracefully(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        main()  # Should not raise

    def test_main_writes_daily_archive_alongside_active_context(self, monkeypatch, tmp_path):
        """WHY: main() must ALSO write history/commits-<date>.md, not just
        activeContext.md -- this is what makes trimming the active view safe."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Active Context\n\n## Auto-commit log\n", encoding="utf-8")

        data = {
            "tool_input": {"command": "git commit -m 'feat: add feature'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "arch1ved"
            if "--format=%s" in args:
                return "feat: add feature"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
        ):
            main()

        archives = list((tmp_path / "history").glob("commits-*.md"))
        assert len(archives) == 1
        assert "arch1ved" in archives[0].read_text(encoding="utf-8")

    def test_main_caps_active_log_but_archive_keeps_full_history(self, monkeypatch, tmp_path):
        """WHY: the whole point of the history/ archive is that trimming the
        active view never loses anything -- assert both halves of that claim
        in one test, not just that trimming happens."""
        pre_existing = "\n".join(
            f"- [old-{i}] `sha{i}`: old commit {i}" for i in range(_ACTIVE_LOG_CAP + 5)
        )
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text(
            f"# Active Context\n\n## Auto-commit log\n{pre_existing}\n", encoding="utf-8"
        )

        data = {
            "tool_input": {"command": "git commit -m 'fix: newest'"},
            "tool_response": {"stdout": "1 file changed"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_git(args, **kwargs):
            if "--format=%h" in args:
                return "newest1"
            if "--format=%s" in args:
                return "fix: newest"
            return ""

        with (
            patch("post_commit_memory.run_git", side_effect=mock_git),
            patch("post_commit_memory.find_project_memory", return_value=ctx_file),
            patch("post_commit_memory.log_decision", return_value=None),
        ):
            main()

        active_content = ctx_file.read_text(encoding="utf-8")
        # newest entry is present, active view is capped (not all 6+ old ones survive)
        assert "`newest1`" in active_content
        assert active_content.count("- [old-") < _ACTIVE_LOG_CAP + 5
        # the archive still has the newest entry too (nothing skipped it)
        archives = list((tmp_path / "history").glob("commits-*.md"))
        assert len(archives) == 1
        assert "`newest1`" in archives[0].read_text(encoding="utf-8")
