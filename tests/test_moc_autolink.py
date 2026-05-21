"""Tests for hooks/moc_autolink.py — auto-link notes to MOC files."""

import json
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
)

import moc_autolink
from moc_autolink import MOC_MAP

# ── Helpers ───────────────────────────────────────────────────────────────────


def _run_main(stdin_data: dict, memory_root: Path, note_path: Path | None = None) -> int:
    """Run moc_autolink.main() with patched stdin and memory root.

    Returns: the sys.exit() code that main() calls.
    """
    stdin_json = json.dumps(stdin_data)
    _note_file = (
        str(note_path) if note_path else stdin_data.get("tool_input", {}).get("file_path", "")
    )
    with (
        mock.patch("sys.stdin", mock.MagicMock(read=lambda: stdin_json)),
        mock.patch("builtins.open", mock.DEFAULT),
        mock.patch("moc_autolink.Path.home", return_value=memory_root.parent),
    ):
        # Patch Path.home so memory_root resolves correctly
        with mock.patch.object(Path, "home", return_value=memory_root.parent):
            try:
                moc_autolink.main()
                return 0
            except SystemExit as exc:
                return exc.code if isinstance(exc.code, int) else 0


# ── MOC_MAP coverage ──────────────────────────────────────────────────────────


class TestMocMap:
    def test_claude_code_tag_maps_to_correct_moc(self):
        # ARRANGE / ACT / ASSERT: routing table sanity check
        assert "claude-code" in MOC_MAP
        assert "Claude-cod-top-2026 MOC" in MOC_MAP["claude-code"]

    def test_archcode_maps_to_research_moc(self):
        assert "archcode" in MOC_MAP
        assert "Research" in MOC_MAP["archcode"]

    def test_security_maps_to_security_moc(self):
        assert "security" in MOC_MAP
        assert "Security" in MOC_MAP["security"]

    def test_all_moc_values_end_with_md(self):
        # ASSERT: every entry points to a Markdown file
        for tag, moc_path in MOC_MAP.items():
            assert moc_path.endswith(".md"), f"Tag '{tag}' points to non-md: {moc_path}"


# ── main() — invalid input guards ────────────────────────────────────────────


class TestMainInvalidInput:
    def test_invalid_json_exits_0(self, tmp_path):
        # ARRANGE: stdin is not valid JSON
        with mock.patch("sys.stdin", mock.MagicMock()) as mock_stdin:
            mock_stdin.__iter__ = mock.Mock(return_value=iter([]))
            # Patch json.load to raise JSONDecodeError
            with mock.patch("json.load", side_effect=json.JSONDecodeError("err", "", 0)):
                with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                    try:
                        moc_autolink.main()
                        assert True  # didn't crash
                    except SystemExit as exc:
                        # ASSERT: graceful exit 0 on bad JSON (fail-open)
                        assert exc.code == 0

    def test_non_memory_path_exits_0(self, tmp_path):
        # ARRANGE: file_path outside ~/.claude/memory/
        outside_file = tmp_path / "some_project" / "file.py"
        outside_file.parent.mkdir(parents=True)
        outside_file.write_text("content", encoding="utf-8")

        data = {"tool_input": {"file_path": str(outside_file)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit as exc:
                    # ASSERT: non-memory path → silently exit 0
                    assert exc.code == 0

    def test_index_file_exits_0(self, tmp_path):
        # ARRANGE: writing to an index.md file should be skipped
        memory_dir = tmp_path / ".claude" / "memory"
        memory_dir.mkdir(parents=True)
        index_file = memory_dir / "index.md"
        index_file.write_text("#hooks", encoding="utf-8")

        data = {"tool_input": {"file_path": str(index_file)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit as exc:
                    assert exc.code == 0

    def test_nonexistent_note_exits_0(self, tmp_path):
        # ARRANGE: note path that does not exist on disk
        memory_dir = tmp_path / ".claude" / "memory"
        memory_dir.mkdir(parents=True)
        ghost_path = memory_dir / "ghost_note.md"  # does NOT exist

        data = {"tool_input": {"file_path": str(ghost_path)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit as exc:
                    assert exc.code == 0


# ── main() — tag routing logic ────────────────────────────────────────────────


class TestMainTagRouting:
    def test_note_with_no_tags_exits_0(self, tmp_path):
        # ARRANGE: note exists but contains no hashtags
        memory_dir = tmp_path / ".claude" / "memory"
        memory_dir.mkdir(parents=True)
        note = memory_dir / "plain_note.md"
        note.write_text("No tags in this note.", encoding="utf-8")

        data = {"tool_input": {"file_path": str(note)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit as exc:
                    # ASSERT: no tags → no routing → exit 0 silently
                    assert exc.code == 0

    def test_note_with_unknown_tag_exits_0(self, tmp_path):
        # ARRANGE: note has tags but none are in MOC_MAP
        memory_dir = tmp_path / ".claude" / "memory"
        memory_dir.mkdir(parents=True)
        note = memory_dir / "unknown_tagged.md"
        note.write_text("#completely_unknown_tag\n\nContent.", encoding="utf-8")

        data = {"tool_input": {"file_path": str(note)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit as exc:
                    assert exc.code == 0

    def test_note_with_known_tag_updates_moc(self, tmp_path):
        # ARRANGE: note with #hooks tag, and the target MOC exists
        memory_dir = tmp_path / ".claude" / "memory"
        moc_dir = memory_dir / "mocs"
        moc_dir.mkdir(parents=True)

        note = memory_dir / "my_note.md"
        note.write_text("# My Note\n\n#hooks\n\nSome content.", encoding="utf-8")

        # Create the target MOC file with a ## Recent section
        moc_file = memory_dir / MOC_MAP["hooks"]
        moc_file.parent.mkdir(parents=True, exist_ok=True)
        moc_file.write_text("# Claude-Code MOC\n\n## Recent\n\n", encoding="utf-8")

        data = {"tool_input": {"file_path": str(note)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit:
                    pass

        # ASSERT: wikilink to the note was appended in the MOC
        updated = moc_file.read_text(encoding="utf-8")
        assert "my_note" in updated or "my note" in updated.lower()

    def test_already_linked_note_not_duplicated(self, tmp_path):
        # ARRANGE: note with #hooks tag, MOC already contains the stem
        memory_dir = tmp_path / ".claude" / "memory"
        moc_dir = memory_dir / "mocs"
        moc_dir.mkdir(parents=True)

        note = memory_dir / "existing_note.md"
        note.write_text("# Existing Note\n\n#hooks\n\nContent.", encoding="utf-8")

        moc_file = memory_dir / MOC_MAP["hooks"]
        moc_file.parent.mkdir(parents=True, exist_ok=True)
        # WHY: stem already in MOC → should not add another link
        original = "# Claude-Code MOC\n\n## Recent\n\n- [[existing_note|Existing Note]]\n"
        moc_file.write_text(original, encoding="utf-8")

        data = {"tool_input": {"file_path": str(note)}}

        with mock.patch("json.load", return_value=data):
            with mock.patch("moc_autolink.Path.home", return_value=tmp_path):
                try:
                    moc_autolink.main()
                except SystemExit:
                    pass

        # ASSERT: content is unchanged (no duplicate link added)
        after = moc_file.read_text(encoding="utf-8")
        assert after.count("existing_note") == 1
