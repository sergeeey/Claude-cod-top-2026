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

    def test_wikilinks_added_when_tags_overlap(self, tmp_path: Path) -> None:
        """_build_wiki_entry adds [[Related]] section when wiki has matching tags."""
        import session_save

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        # Existing wiki entry with shared tag
        (wiki_dir / "existing-note.md").write_text(
            "# Existing Note\n**Tags:** python, hooks\n\nBody.", encoding="utf-8"
        )

        entry = session_save._build_wiki_entry(
            title="New Note",
            tags=["python", "security"],
            source="raw/new-note.md",
            content="# New Note\nSome content. #python #security",
            wiki_dir=wiki_dir,
        )

        assert "## Related" in entry
        assert "[[Existing Note]]" in entry

    def test_wikilinks_absent_when_no_tag_overlap(self, tmp_path: Path) -> None:
        """No Related section when no tag overlap with existing wiki."""
        import session_save

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        (wiki_dir / "other-note.md").write_text("**Tags:** rust, cargo\n\nBody.", encoding="utf-8")

        entry = session_save._build_wiki_entry(
            title="Python Note",
            tags=["python"],
            source="raw/python-note.md",
            content="Python content.",
            wiki_dir=wiki_dir,
        )

        assert "## Related" not in entry

    def test_wikilinks_absent_without_wiki_dir(self) -> None:
        """wiki_dir=None → no Related section (backward compat)."""
        import session_save

        entry = session_save._build_wiki_entry(
            title="Note",
            tags=["python"],
            source="raw/note.md",
            content="Content.",
            wiki_dir=None,
        )

        assert "## Related" not in entry


# =============================================================================
# syntax_guard.py
# =============================================================================


class TestSyntaxGuard:
    """syntax_guard: block Write/Edit on Python syntax errors."""

    def _run(self, monkeypatch, data: dict, capsys) -> dict | None:
        import syntax_guard

        monkeypatch.setattr("sys.stdin", make_stdin(data))
        try:
            syntax_guard.main()
        except SystemExit:
            pass
        out = capsys.readouterr().out.strip()
        return __import__("json").loads(out) if out else None

    def test_valid_python_allowed(self, monkeypatch, capsys, tmp_path):
        result = self._run(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "foo.py", "new_content": "def f():\n    return 1\n"},
            },
            capsys,
        )
        assert result is None  # no block output

    def test_invalid_python_blocked(self, monkeypatch, capsys, tmp_path):
        result = self._run(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "foo.py", "new_content": "def f(:\n    pass\n"},
            },
            capsys,
        )
        assert result is not None
        assert result.get("decision") == "block"
        assert "SyntaxError" in result.get("reason", "")

    def test_edit_new_string_validated(self, monkeypatch, capsys):
        result = self._run(
            monkeypatch,
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "bar.py", "new_string": "x = (1 +\n"},
            },
            capsys,
        )
        assert result is not None
        assert result.get("decision") == "block"

    def test_non_py_file_skipped(self, monkeypatch, capsys):
        result = self._run(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "readme.md", "new_content": "# Hello"},
            },
            capsys,
        )
        assert result is None

    def test_non_write_tool_skipped(self, monkeypatch, capsys):
        result = self._run(
            monkeypatch,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "python bad.py"},
            },
            capsys,
        )
        assert result is None

    def test_empty_content_skipped(self, monkeypatch, capsys):
        result = self._run(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "foo.py", "new_content": ""},
            },
            capsys,
        )
        assert result is None


# =============================================================================
# knowledge_librarian.py
# =============================================================================


class TestKnowledgeLibrarian:
    """knowledge_librarian: inject relevant pre-task context at SessionStart."""

    def _run(
        self,
        monkeypatch,
        tmp_path,
        focus: str,
        wiki_notes: dict | None = None,
        patterns: str = "",
        playbook: str = "",
    ) -> str:
        import knowledge_librarian

        # Set up project activeContext with given focus
        mem_dir = tmp_path / ".claude" / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "activeContext.md").write_text(
            f"# Context\n\n## Current Focus\n{focus}\n\n## Other\nstuff",
            encoding="utf-8",
        )

        # Wiki entries
        wiki_dir = tmp_path / ".claude" / "memory" / "wiki"
        if wiki_notes:
            wiki_dir.mkdir(parents=True, exist_ok=True)
            for name, content in wiki_notes.items():
                (wiki_dir / name).write_text(content, encoding="utf-8")

        # Patterns
        if patterns:
            (mem_dir / "patterns.md").write_text(patterns, encoding="utf-8")

        # Playbook
        if playbook:
            (mem_dir / "playbook.md").write_text(playbook, encoding="utf-8")

        monkeypatch.setattr("sys.stdin", make_stdin({}))
        monkeypatch.setattr(knowledge_librarian, "WIKI_DIR", wiki_dir)
        monkeypatch.setattr(knowledge_librarian, "WIKI_INDEX", wiki_dir / "index.md")
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", mem_dir / "patterns.md")
        monkeypatch.setattr(knowledge_librarian, "PLAYBOOK_PATH", mem_dir / "playbook.md")
        monkeypatch.setattr(
            "knowledge_librarian.find_project_memory",
            lambda: mem_dir / "activeContext.md",
        )

        import io, json as _json
        from unittest.mock import patch as _patch

        out_buf = io.StringIO()
        with _patch("sys.stdout", out_buf):
            try:
                knowledge_librarian.main()
            except SystemExit:
                pass
        return out_buf.getvalue().strip()

    def test_relevant_wiki_injected(self, monkeypatch, tmp_path):
        out = self._run(
            monkeypatch,
            tmp_path,
            focus="Refactor authentication hooks",
            wiki_notes={"auth-patterns.md": "**Tags:** auth, hooks\n\nContent."},
        )
        assert "Auth Patterns" in out or "auth" in out.lower()

    def test_avoid_pattern_injected(self, monkeypatch, tmp_path):
        out = self._run(
            monkeypatch,
            tmp_path,
            focus="Fix auth session bug",
            patterns="## Bugs\n- [AVOID] auth: never store tokens in localStorage [×2]\n",
        )
        assert "localStorage" in out or "AVOID" in out

    def test_playbook_best_approach_injected(self, monkeypatch, tmp_path):
        out = self._run(
            monkeypatch,
            tmp_path,
            focus="Write new feature",
            playbook="# ACE Playbook\n\n### search-first\n- helpful: 5\n- harmful: 1\n",
        )
        assert "search-first" in out

    def test_empty_focus_exits_silently(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, focus="")
        assert out == ""

    def test_no_wiki_no_patterns_exits_silently(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, focus="Some rare unique xyz task")
        assert out == ""


# =============================================================================
# update_wiki_index (session_save.py)
# =============================================================================


class TestUpdateWikiIndex:
    """Tests for update_wiki_index() — the Karpathy navigation map generator."""

    def _make_wiki_entry(self, wiki_dir: Path, name: str, title: str, tags: list[str]) -> None:
        tags_str = ", ".join(tags) if tags else "—"
        content = (
            f"# {title}\n\n"
            f"**Date:** 2026-04-12  \n"
            f"**Source:** raw/{name}.md  \n"
            f"**Tags:** {tags_str}  \n\n"
            f"---\n\nSome content here.\n"
        )
        (wiki_dir / f"2026-04-12_{name}.md").write_text(content, encoding="utf-8")

    def test_creates_index_md(self, tmp_path):
        from hooks.session_save import update_wiki_index

        self._make_wiki_entry(tmp_path, "lesson1", "Lesson One", ["research", "ml"])
        update_wiki_index(tmp_path)
        assert (tmp_path / "index.md").exists()

    def test_index_contains_title(self, tmp_path):
        from hooks.session_save import update_wiki_index

        self._make_wiki_entry(tmp_path, "lesson1", "AUC Red Flags", ["research"])
        update_wiki_index(tmp_path)
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "AUC Red Flags" in content

    def test_index_groups_by_topic(self, tmp_path):
        from hooks.session_save import update_wiki_index

        self._make_wiki_entry(tmp_path, "a", "Note A", ["python"])
        self._make_wiki_entry(tmp_path, "b", "Note B", ["python"])
        self._make_wiki_entry(tmp_path, "c", "Note C", ["research"])
        update_wiki_index(tmp_path)
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "### python (2)" in content
        assert "### research (1)" in content

    def test_index_not_included_in_itself(self, tmp_path):
        from hooks.session_save import update_wiki_index

        self._make_wiki_entry(tmp_path, "note1", "My Note", ["tag"])
        update_wiki_index(tmp_path)
        # Run twice — index.md should not appear as an entry
        update_wiki_index(tmp_path)
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert content.count("Knowledge Base Index") == 1  # header only, not listed

    def test_empty_wiki_dir_no_crash(self, tmp_path):
        from hooks.session_save import update_wiki_index

        update_wiki_index(tmp_path)  # no files → no error, no index
        assert not (tmp_path / "index.md").exists()

    def test_missing_wiki_dir_no_crash(self, tmp_path):
        from hooks.session_save import update_wiki_index

        update_wiki_index(tmp_path / "nonexistent")  # should not raise

    def test_recent_section_shows_7_max(self, tmp_path):
        from hooks.session_save import update_wiki_index

        for i in range(10):
            self._make_wiki_entry(tmp_path, f"note{i}", f"Note {i}", ["tag"])
        update_wiki_index(tmp_path)
        content = (tmp_path / "index.md").read_text(encoding="utf-8")
        # Count entries in Recent section (lines starting with "- [[")
        recent_section = content.split("## By Topic")[0]
        recent_lines = [l for l in recent_section.splitlines() if l.startswith("- [[")]
        assert len(recent_lines) <= 7


class TestKnowledgeLibrarianIndex:
    """Tests for index.md integration in knowledge_librarian."""

    def _run(self, monkeypatch, tmp_path, focus="", wiki_entries=None, index_content=None):
        import sys
        import io

        sys.path.insert(0, str(tmp_path.parent.parent / "hooks"))
        from hooks import knowledge_librarian

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        if wiki_entries:
            for name, content in wiki_entries.items():
                (wiki_dir / name).write_text(content, encoding="utf-8")

        if index_content:
            (wiki_dir / "index.md").write_text(index_content, encoding="utf-8")

        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text(f"## Current Focus\n{focus}\n", encoding="utf-8")

        monkeypatch.setattr(knowledge_librarian, "WIKI_DIR", wiki_dir)
        monkeypatch.setattr(knowledge_librarian, "WIKI_INDEX", wiki_dir / "index.md")
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", tmp_path / "patterns.md")
        monkeypatch.setattr(knowledge_librarian, "PLAYBOOK_PATH", tmp_path / "playbook.md")
        monkeypatch.setattr("hooks.knowledge_librarian.find_project_memory", lambda: ctx_file)
        monkeypatch.setattr("hooks.knowledge_librarian.cogniml_client.advise", lambda *a, **k: None)

        output = []
        monkeypatch.setattr(
            "hooks.knowledge_librarian.emit_hook_result", lambda ev, msg: output.append(msg)
        )
        monkeypatch.setattr("sys.stdin", make_stdin({}))
        knowledge_librarian.main()
        return output[0] if output else ""

    def test_index_topics_injected(self, monkeypatch, tmp_path):
        index = "# Knowledge Base Index\n## By Topic\n\n### research (3)\n- [[Note]]\n"
        out = self._run(monkeypatch, tmp_path, focus="baseline experiment", index_content=index)
        assert "research(3)" in out

    def test_index_fast_path_matches_keyword(self, monkeypatch, tmp_path):
        index = "# KB Index\n## Recent\n- [[AUC Red Flags]] — research, ml\n## By Topic\n\n### research (1)\n- [[AUC Red Flags]]\n"
        out = self._run(monkeypatch, tmp_path, focus="AUC baseline research", index_content=index)
        assert "AUC Red Flags" in out


# =============================================================================
# prompt_wiki_inject.py — UserPromptSubmit hook
# =============================================================================


class TestPromptWikiInject:
    """prompt_wiki_inject: inject relevant wiki before each user prompt."""

    def _run(self, monkeypatch, tmp_path, prompt="", index_content=None, wiki_files=None):
        from hooks import prompt_wiki_inject

        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()

        if index_content:
            (wiki_dir / "index.md").write_text(index_content, encoding="utf-8")

        if wiki_files:
            for name, content in wiki_files.items():
                (wiki_dir / name).write_text(content, encoding="utf-8")

        monkeypatch.setattr(prompt_wiki_inject, "WIKI_DIR", wiki_dir)
        monkeypatch.setattr(prompt_wiki_inject, "WIKI_INDEX", wiki_dir / "index.md")
        monkeypatch.setattr("sys.stdin", make_stdin({"prompt": prompt}))

        output = []
        monkeypatch.setattr(
            "hooks.prompt_wiki_inject.emit_hook_result", lambda ev, msg: output.append(msg)
        )
        prompt_wiki_inject.main()
        return output[0] if output else ""

    def test_short_prompt_exits_silently(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, prompt="ok")
        assert out == ""

    def test_no_index_exits_silently(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, prompt="how does session save work?")
        assert out == ""

    def test_matching_keyword_injects_title(self, monkeypatch, tmp_path):
        index = "# Index\n## Recent\n- [[AUC Red Flags]] — research, ml\n"
        wiki = {"2026-01-01_auc_red_flags.md": "# AUC Red Flags\n\nContent about AUC metrics.\n"}
        out = self._run(
            monkeypatch,
            tmp_path,
            prompt="what are the AUC issues we found?",
            index_content=index,
            wiki_files=wiki,
        )
        assert "AUC Red Flags" in out
        assert "Relevant wiki articles" in out

    def test_no_matching_keyword_exits_silently(self, monkeypatch, tmp_path):
        index = "# Index\n## Recent\n- [[AUC Red Flags]] — research, ml\n"
        out = self._run(
            monkeypatch,
            tmp_path,
            prompt="what is the weather today?",
            index_content=index,
        )
        assert out == ""

    def test_recursion_guard_env_var(self, monkeypatch, tmp_path):
        """CLAUDE_INVOKED_BY set → module-level sys.exit(0) fires at import time.
        We verify this by checking the guard constant is present in the source.
        """
        import inspect
        from hooks import prompt_wiki_inject

        source = inspect.getsource(prompt_wiki_inject)
        assert "CLAUDE_INVOKED_BY" in source


# =============================================================================
# wiki_reminder.py — Stop hook decision detector
# =============================================================================


class TestWikiReminder:
    """wiki_reminder: detect decision keywords and nudge to save to wiki."""

    def _run(self, monkeypatch, tmp_path, transcript_lines=None, debounce_ok=True):
        import json as _json
        from hooks import wiki_reminder

        monkeypatch.setattr(wiki_reminder, "DEBOUNCE_FILE", tmp_path / "debounce.txt")

        # Build fake transcript JSONL
        transcript = tmp_path / "transcript.jsonl"
        lines = transcript_lines or []
        transcript.write_text("\n".join(_json.dumps(line) for line in lines), encoding="utf-8")

        hook_input = {
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        if not debounce_ok:
            # Write a fresh debounce timestamp
            (tmp_path / "debounce.txt").write_text(str(__import__("time").time()), encoding="utf-8")

        monkeypatch.setattr("sys.stdin", make_stdin(hook_input))

        import io as _io
        import sys as _sys

        buf = _io.StringIO()
        monkeypatch.setattr(_sys, "stdout", buf)
        wiki_reminder.main()
        return buf.getvalue().strip()

    def _make_turn(self, role: str, text: str) -> dict:
        return {"message": {"role": role, "content": text}}

    def test_no_decision_keywords_silent(self, monkeypatch, tmp_path):
        turns = [self._make_turn("assistant", "Here is the weather forecast for today.")]
        out = self._run(monkeypatch, tmp_path, transcript_lines=turns)
        assert out == ""

    def test_two_decision_keywords_fires(self, monkeypatch, tmp_path):
        text = "I decided to chose asyncpg instead of SQLAlchemy because of performance."
        turns = [self._make_turn("assistant", text)]
        out = self._run(monkeypatch, tmp_path, transcript_lines=turns)
        assert "wiki-reminder" in out
        assert "systemMessage" in out

    def test_debounce_suppresses_repeat(self, monkeypatch, tmp_path):
        text = "I decided to chose asyncpg instead of SQLAlchemy because of performance."
        turns = [self._make_turn("assistant", text)]
        out = self._run(monkeypatch, tmp_path, transcript_lines=turns, debounce_ok=False)
        assert out == ""

    def test_stop_hook_active_exits(self, monkeypatch, tmp_path):
        from hooks import wiki_reminder

        monkeypatch.setattr(wiki_reminder, "DEBOUNCE_FILE", tmp_path / "debounce.txt")
        hook_input = {"stop_hook_active": True, "transcript_path": ""}
        monkeypatch.setattr("sys.stdin", make_stdin(hook_input))
        import io as _io, sys as _sys

        buf = _io.StringIO()
        monkeypatch.setattr(_sys, "stdout", buf)
        wiki_reminder.main()
        assert buf.getvalue().strip() == ""

    def test_recursion_guard_in_source(self, monkeypatch, tmp_path):
        import inspect
        from hooks import wiki_reminder

        source = inspect.getsource(wiki_reminder)
        assert "CLAUDE_INVOKED_BY" in source


# =============================================================================
# session_save.py — contradiction detector + category assignment
# =============================================================================


class TestAssignCategory:
    """_assign_category: auto-categorise wiki entry by tag clusters."""

    def test_research_tags(self):
        from hooks.session_save import _assign_category

        assert _assign_category(["research", "ml", "auc"]) == "research"

    def test_hooks_tags(self):
        from hooks.session_save import _assign_category

        assert _assign_category(["hook", "sessionstart", "posttooluse"]) == "hooks"

    def test_patterns_tags(self):
        from hooks.session_save import _assign_category

        assert _assign_category(["pattern", "lesson", "avoid"]) == "patterns"

    def test_no_tags_returns_general(self):
        from hooks.session_save import _assign_category

        assert _assign_category([]) == "general"

    def test_unrecognised_tags_returns_general(self):
        from hooks.session_save import _assign_category

        assert _assign_category(["unicorn", "rainbow", "xyz"]) == "general"

    def test_majority_wins(self):
        from hooks.session_save import _assign_category

        # 2 obsidian vs 1 research → obsidian wins
        assert _assign_category(["obsidian", "vault", "research"]) == "obsidian"


class TestDetectContradictions:
    """_detect_contradictions: flag opposing [REPEAT]/[AVOID] entries on same tags."""

    def _make_wiki_entry(self, wiki_dir: Path, name: str, tags: list[str], body: str) -> None:
        tags_str = ", ".join(tags)
        content = f"# {name}\n\n**Tags:** {tags_str}  \n\n---\n\n{body}\n"
        (wiki_dir / f"{name.lower().replace(' ', '_')}.md").write_text(content, encoding="utf-8")

    def test_no_tags_returns_empty(self, tmp_path):
        from hooks.session_save import _detect_contradictions

        result = _detect_contradictions("prefer this approach", [], tmp_path, "new.md")
        assert result == []

    def test_no_directives_in_new_returns_empty(self, tmp_path):
        from hooks.session_save import _detect_contradictions

        self._make_wiki_entry(tmp_path, "Old Note", ["python"], "[AVOID] this")
        result = _detect_contradictions("this is a neutral note", ["python"], tmp_path, "new.md")
        assert result == []

    def test_affirm_vs_negate_detected(self, tmp_path):
        from hooks.session_save import _detect_contradictions

        self._make_wiki_entry(tmp_path, "Old Note", ["python"], "[AVOID] use this library")
        result = _detect_contradictions(
            "[REPEAT] prefer this approach", ["python"], tmp_path, "new.md"
        )
        assert len(result) == 1
        assert "Old Note" in result[0]

    def test_no_tag_overlap_no_conflict(self, tmp_path):
        from hooks.session_save import _detect_contradictions

        self._make_wiki_entry(tmp_path, "Old Note", ["java"], "[AVOID] this")
        result = _detect_contradictions("[REPEAT] prefer this", ["python"], tmp_path, "new.md")
        assert result == []

    def test_exclude_source_skipped(self, tmp_path):
        from hooks.session_save import _detect_contradictions

        self._make_wiki_entry(tmp_path, "Same Note", ["python"], "[AVOID] this")
        result = _detect_contradictions(
            "[REPEAT] prefer this", ["python"], tmp_path, "same_note.md"
        )
        assert result == []


class TestBuildWikiEntryCategory:
    """_build_wiki_entry: category and contradictions in output."""

    def test_category_in_header(self, tmp_path):
        from hooks.session_save import _build_wiki_entry

        entry = _build_wiki_entry("Test", ["research", "ml"], "raw/test.md", "Body text")
        assert "**Category:** research" in entry

    def test_general_category_when_no_tags(self, tmp_path):
        from hooks.session_save import _build_wiki_entry

        entry = _build_wiki_entry("Test", [], "raw/test.md", "Body text")
        assert "**Category:** general" in entry

    def test_contradiction_section_added(self, tmp_path):
        from hooks.session_save import _build_wiki_entry, _assign_category

        # Create an existing wiki entry that will conflict
        tags_str = "python, patterns"
        existing = "# Old Advice\n\n**Tags:** python, patterns  \n\n---\n\n[AVOID] this approach\n"
        (tmp_path / "old_advice.md").write_text(existing, encoding="utf-8")

        entry = _build_wiki_entry(
            title="New Advice",
            tags=["python", "patterns"],
            source="new_advice.md",
            content="[REPEAT] prefer this approach",
            wiki_dir=tmp_path,
        )
        assert "⚠️ Potential Contradictions" in entry
        assert "Old Advice" in entry

    def test_no_contradiction_when_no_opposing_directives(self, tmp_path):
        from hooks.session_save import _build_wiki_entry

        existing = "# Neutral Note\n\n**Tags:** python  \n\n---\n\nsome neutral content\n"
        (tmp_path / "neutral.md").write_text(existing, encoding="utf-8")
        entry = _build_wiki_entry(
            title="New Note",
            tags=["python"],
            source="new.md",
            content="some other neutral content",
            wiki_dir=tmp_path,
        )
        assert "⚠️" not in entry


# =============================================================================
# scripts/inbox_review.py
# =============================================================================


class TestInboxReview:
    """inbox_review: weekly processing of inbox/ with rich cross-linking."""

    def test_empty_inbox_returns_zero(self, tmp_path, monkeypatch):
        import scripts.inbox_review as ir

        monkeypatch.setattr(ir, "INBOX_DIR", tmp_path / "inbox")
        monkeypatch.setattr(ir, "WIKI_DIR", tmp_path / "wiki")
        (tmp_path / "inbox").mkdir()
        result = ir.process_inbox(dry_run=True)
        assert result == 0

    def test_missing_inbox_returns_zero(self, tmp_path, monkeypatch, capsys):
        import scripts.inbox_review as ir

        monkeypatch.setattr(ir, "INBOX_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(ir, "WIKI_DIR", tmp_path / "wiki")
        result = ir.process_inbox(dry_run=False)
        assert result == 0

    def test_processes_inbox_file(self, tmp_path, monkeypatch):
        import scripts.inbox_review as ir

        inbox = tmp_path / "inbox"
        wiki = tmp_path / "wiki"
        inbox.mkdir()
        wiki.mkdir()
        monkeypatch.setattr(ir, "INBOX_DIR", inbox)
        monkeypatch.setattr(ir, "WIKI_DIR", wiki)
        monkeypatch.setattr(ir, "PROCESSED_DIR", inbox / "processed")

        (inbox / "idea.md").write_text("# My Idea\n\nSome thought. #research\n", encoding="utf-8")
        count = ir.process_inbox(dry_run=False)
        assert count == 1
        wiki_files = list(wiki.glob("*.md"))
        assert len(wiki_files) == 1
        assert not (inbox / "idea.md").exists()  # moved to processed/

    def test_dry_run_does_not_write(self, tmp_path, monkeypatch):
        import scripts.inbox_review as ir

        inbox = tmp_path / "inbox"
        wiki = tmp_path / "wiki"
        inbox.mkdir()
        wiki.mkdir()
        monkeypatch.setattr(ir, "INBOX_DIR", inbox)
        monkeypatch.setattr(ir, "WIKI_DIR", wiki)
        (inbox / "idea.md").write_text("# Test\n\nContent. #hooks\n", encoding="utf-8")
        ir.process_inbox(dry_run=True)
        assert (inbox / "idea.md").exists()  # NOT moved in dry run
        assert list(wiki.glob("*.md")) == []  # nothing written

    def test_output_has_category_and_weaved(self, tmp_path, monkeypatch):
        import scripts.inbox_review as ir

        inbox = tmp_path / "inbox"
        wiki = tmp_path / "wiki"
        inbox.mkdir()
        wiki.mkdir()
        monkeypatch.setattr(ir, "INBOX_DIR", inbox)
        monkeypatch.setattr(ir, "WIKI_DIR", wiki)
        monkeypatch.setattr(ir, "PROCESSED_DIR", inbox / "processed")

        (inbox / "note.md").write_text(
            "# Hook Note\n\nAbout sessions. #hook #session\n", encoding="utf-8"
        )
        ir.process_inbox(dry_run=False)
        content = list(wiki.glob("*.md"))[0].read_text(encoding="utf-8")
        assert "**Category:** hooks" in content
        assert "**Weaved:**" in content
