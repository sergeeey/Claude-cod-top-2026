"""Tests for small session hooks: pre_compact, session_save, post_format,
read_before_edit, mcp_locality_guard.

WHY: each hook is small, but together they form the session safety net.
Tests verify edge cases without real subprocess/filesystem calls.
"""

import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path  # noqa: E402
from unittest.mock import mock_open, patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Helper function to mock stdin with JSON data."""
    return io.StringIO(json.dumps(data))


# =============================================================================
# pre_compact.py
# =============================================================================


class TestPreCompact:
    """Tests for pre_compact.main(): updating the timestamp in activeContext.md."""

    def test_pre_compact_updates_timestamp(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """If activeContext.md is found — hook updates the '## Updated:' line."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text(
            "# Context\n## Updated: 2026-01-01 00:00\nSome content\n", encoding="utf-8"
        )

        # WHY: patch find_project_memory to avoid depending on the real filesystem
        with (
            patch("pre_compact.find_project_memory", return_value=ctx_file),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import pre_compact

            pre_compact.main()

        content = ctx_file.read_text(encoding="utf-8")
        # The line should contain the "(pre-compact)" marker
        assert "pre-compact" in content

    def test_pre_compact_silent_when_no_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """If activeContext.md is not found — hook prints a fallback message."""
        with (
            patch("pre_compact.find_project_memory", return_value=None),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import pre_compact

            pre_compact.main()

        captured = capsys.readouterr()
        # WHY: hook always prints something via print() — this is not emit_hook_result
        assert "No project" in captured.out or "activeContext" in captured.out


# =============================================================================
# session_save.py
# =============================================================================


class TestSessionSave:
    """Tests for session_save.main(): detecting stale memory before session end."""

    def test_session_save_detects_stale_memory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """If commit is newer than activeContext.md by >5 min — prints WARNING."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        now = time.time()
        ctx_mtime = now - 600  # activeContext updated 10 min ago
        commit_time = now - 60  # last commit 1 min ago

        # Set file mtime manually
        os.utime(ctx_file, (ctx_mtime, ctx_mtime))

        with (
            patch("session_save.find_project_memory", return_value=ctx_file),
            patch("session_save.get_last_commit_time", return_value=commit_time),
            # Skip writing to global activeContext and log
            patch("os.path.exists", return_value=False),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import session_save

            session_save.main()

        captured = capsys.readouterr()
        # WHY: commit_time > ctx_mtime and difference > 300 s → WARNING
        assert "WARNING" in captured.out

    def test_session_save_silent_when_context_fresh(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """If activeContext.md was updated after the last commit — stays silent."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        now = time.time()
        commit_time = now - 600  # commit 10 min ago
        ctx_mtime = now - 60  # activeContext updated 1 min ago (fresher than commit)

        os.utime(ctx_file, (ctx_mtime, ctx_mtime))

        with (
            patch("session_save.find_project_memory", return_value=ctx_file),
            patch("session_save.get_last_commit_time", return_value=commit_time),
            patch("os.path.exists", return_value=False),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import session_save

            session_save.main()

        captured = capsys.readouterr()
        assert "WARNING" not in captured.out


# =============================================================================
# post_format.py
# =============================================================================


class TestPostFormat:
    """Tests for post_format.main(): auto-formatting Python/JS files."""

    def test_post_format_skips_unknown_ext(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """File .txt — not Python and not JS/TS, subprocess is not called."""
        data = {"tool_input": {"file_path": "foo.txt"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with (
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            import post_format

            post_format.main()

        # WHY: extension .txt is not in the list (.py, .js, .ts, .jsx, .tsx) → no subprocess
        mock_run.assert_not_called()

    def test_post_format_calls_ruff_for_py(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """File .py — calls ruff format."""
        data = {"tool_input": {"file_path": "/project/app.py"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with (
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            import post_format

            post_format.main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ruff" in call_args

    def test_post_format_calls_prettier_for_ts(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """File .ts — calls prettier."""
        data = {"tool_input": {"file_path": "/project/app.ts"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with (
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            import post_format

            post_format.main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "prettier" in call_args


# =============================================================================
# read_before_edit.py
# =============================================================================


class TestReadBeforeEdit:
    """Tests for read_before_edit.main(): reminder to read the file before Edit."""

    def test_read_before_edit_warns_on_edit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Tool 'Edit' with file_path — prints a reminder to stderr."""
        data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/project/utils.py"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import read_before_edit

        with pytest.raises(SystemExit) as exc_info:
            read_before_edit.main()

        # WHY: hook always exits via sys.exit(0) — this is normal exit
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "read-before-edit" in captured.err.lower()
        assert "utils.py" in captured.err

    def test_read_before_edit_skips_write(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Tool 'Write' — hook does not print a warning (nothing to read for a new file)."""
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/project/new_file.py"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import read_before_edit

        with pytest.raises(SystemExit) as exc_info:
            read_before_edit.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # WHY: Write creates a new file — nothing to read, no warning needed
        assert captured.err == ""

    def test_read_before_edit_skips_no_file_path(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Edit without file_path — hook stays silent."""
        data = {
            "tool_name": "Edit",
            "tool_input": {},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import read_before_edit

        with pytest.raises(SystemExit) as exc_info:
            read_before_edit.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""


# =============================================================================
# mcp_locality_guard.py
# =============================================================================


class TestMcpLocalityGuard:
    """Tests for mcp_locality_guard.main(): reminder to try local search before MCP."""

    def test_mcp_locality_skips_exempt_basic_memory(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__basic-memory — exempt MCP, warning is not emitted."""
        data = {"tool_name": "mcp__basic-memory__note__create"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # WHY: basic-memory is in EXEMPT_MCPS → early return without output
        assert captured.err == ""

    def test_mcp_locality_skips_non_mcp_tool(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Regular tool (Read, Bash) — not MCP, hook stays silent."""
        data = {"tool_name": "Read"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_mcp_locality_warns_for_context7(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__context7 — not exempt, hook emits a reminder to stderr."""
        data = {"tool_name": "mcp__context7__search"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # WHY: context7 is not in EXEMPT_MCPS → reminder about local search
        assert "mcp-locality" in captured.err
        assert "mcp__context7__search" in captured.err

    def test_mcp_locality_skips_sequential_thinking(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__sequential-thinking — exempt, warning is not emitted."""
        data = {"tool_name": "mcp__sequential-thinking__think"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_mcp_locality_warns_for_ollama(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__ollama — not exempt, warning in stderr."""
        data = {"tool_name": "mcp__ollama__generate"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "mcp-locality" in captured.err


# =============================================================================
# session_save.py — Raw → Wiki pipeline
# =============================================================================


class TestRawToWiki:
    """Tests for process_raw_to_wiki() in session_save.py."""

    def test_basic_note_converted_to_wiki(self, tmp_path: Path) -> None:
        """A raw note with H1 and tags becomes a structured wiki entry."""
        import session_save

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "my_note.md").write_text(
            "# My Idea\n\nThis is the content. #architecture #raw\n",
            encoding="utf-8",
        )

        count = session_save.process_raw_to_wiki(raw_dir, wiki_dir)

        assert count == 1
        wiki_files = list(wiki_dir.glob("*.md"))
        assert len(wiki_files) == 1
        content = wiki_files[0].read_text(encoding="utf-8")
        assert "# My Idea" in content
        assert "**Tags:** architecture" in content
        assert "**Source:** raw/my_note.md" in content
        # #raw tag must be stripped from body
        assert "#raw" not in content

    def test_original_moved_to_processed(self, tmp_path: Path) -> None:
        """After processing, original file is moved to raw/processed/."""
        import session_save

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "note.md").write_text("# Note\nContent.\n", encoding="utf-8")

        session_save.process_raw_to_wiki(raw_dir, wiki_dir)

        assert not (raw_dir / "note.md").exists()
        assert (raw_dir / "processed" / "note.md").exists()

    def test_no_raw_dir_returns_zero(self, tmp_path: Path) -> None:
        """If raw/ does not exist, returns 0 without error."""
        import session_save

        count = session_save.process_raw_to_wiki(tmp_path / "raw", tmp_path / "wiki")
        assert count == 0

    def test_empty_raw_dir_returns_zero(self, tmp_path: Path) -> None:
        """If raw/ exists but is empty, returns 0."""
        import session_save

        (tmp_path / "raw").mkdir()
        count = session_save.process_raw_to_wiki(tmp_path / "raw", tmp_path / "wiki")
        assert count == 0

    def test_title_from_filename_when_no_h1(self, tmp_path: Path) -> None:
        """If no H1 heading, title is derived from filename."""
        import session_save

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "some_concept.md").write_text(
            "Just plain text without a heading.\n", encoding="utf-8"
        )

        session_save.process_raw_to_wiki(raw_dir, wiki_dir)

        content = list(wiki_dir.glob("*.md"))[0].read_text(encoding="utf-8")
        assert "# Some Concept" in content

    def test_no_tag_duplication_in_wiki(self, tmp_path: Path) -> None:
        """Tags appear in frontmatter and body is preserved."""
        import session_save

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        (raw_dir / "tagged.md").write_text(
            "# Tagged Note\n\nBody text. #python #hooks\n", encoding="utf-8"
        )

        session_save.process_raw_to_wiki(raw_dir, wiki_dir)

        content = list(wiki_dir.glob("*.md"))[0].read_text(encoding="utf-8")
        assert "python" in content
        assert "hooks" in content

    def test_multiple_notes_all_processed(self, tmp_path: Path) -> None:
        """All .md files in raw/ are processed in one call."""
        import session_save

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        for i in range(3):
            (raw_dir / f"note_{i}.md").write_text(f"# Note {i}\nContent.\n", encoding="utf-8")

        count = session_save.process_raw_to_wiki(raw_dir, wiki_dir)

        assert count == 3
        assert len(list(wiki_dir.glob("*.md"))) == 3

    def test_collision_gets_suffix(self, tmp_path: Path) -> None:
        """Two notes with same stem on same day get _2 suffix."""
        from datetime import UTC, datetime

        import session_save

        raw_dir = tmp_path / "raw"
        wiki_dir = tmp_path / "wiki"
        raw_dir.mkdir()
        wiki_dir.mkdir()
        (raw_dir / "note_a.md").write_text("# Note A\nFirst.\n", encoding="utf-8")

        # Pre-create a wiki file with today's date prefix to force collision
        date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
        (wiki_dir / f"{date_prefix}_note_a.md").write_text("existing", encoding="utf-8")

        session_save.process_raw_to_wiki(raw_dir, wiki_dir)

        wiki_files = [f.name for f in wiki_dir.glob("*.md")]
        assert any("_2" in name for name in wiki_files)

    def test_extract_tags_excludes_raw(self) -> None:
        """_extract_tags strips #raw from the returned list."""
        import session_save

        tags = session_save._extract_tags("Some text #raw #python #hooks")
        assert "raw" not in tags
        assert "python" in tags
        assert "hooks" in tags
