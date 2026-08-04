"""Tests for scripts/add_triggers.py — one-shot SKILL.md triggers: backfill.

WHY: 0% coverage before this file (scripts/add_triggers.py's own docstring
calls it a one-shot tool, but its core parsing/generation functions are pure
and cheaply testable — main() itself hardcodes a personal path and is left
untested, see TestMain below for why that's still safe to exercise).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from add_triggers import (
    extract_trigger_text,
    format_triggers,
    main,
    name_to_triggers,
    process_file,
)


class TestExtractTriggerText:
    def test_finds_english_triggers_line(self):
        text = 'description: >\n  Some desc.\n  Triggers: "/foo", "/bar", "do the thing"\n'
        assert extract_trigger_text(text) == ["/foo", "/bar", "do the thing"]

    def test_finds_russian_triggers_line(self):
        text = "Триггеры: анализ, проверь, /audit\n"
        assert extract_trigger_text(text) == ["анализ", "проверь", "/audit"]

    def test_returns_empty_list_when_no_triggers_line(self):
        assert extract_trigger_text("description: just a plain description\n") == []

    def test_drops_overlong_items(self):
        long_item = "x" * 70
        text = f"Triggers: short, {long_item}\n\n"
        result = extract_trigger_text(text)
        assert "short" in result
        assert long_item not in result

    def test_stops_at_blank_line(self):
        text = "Triggers: a, b\n\nUnrelated section: c, d\n"
        assert extract_trigger_text(text) == ["a", "b"]


class TestNameToTriggers:
    def test_includes_bare_name(self):
        assert "my-skill" in name_to_triggers("my-skill", "")

    def test_adds_slash_form_for_dashed_name(self):
        result = name_to_triggers("my-skill", "")
        assert "/my-skill" in result

    def test_no_slash_form_for_single_word_name(self):
        result = name_to_triggers("orient", "")
        assert "/orient" not in result

    def test_splits_dashed_name_into_words(self):
        result = name_to_triggers("boyko-why-ladder", "")
        assert "boyko" in result
        assert "why" in result

    def test_extracts_capitalized_keywords_from_description(self):
        result = name_to_triggers("thing", "Analyzes Contradiction patterns in text.")
        assert "Contradiction" in result

    def test_deduplicates_case_insensitively(self):
        result = name_to_triggers("skill-skill", "Skill description here.")
        lowered = [t.lower() for t in result]
        assert len(lowered) == len(set(lowered))

    def test_caps_result_at_ten_items(self):
        result = name_to_triggers(
            "a-b-c-d", "AAAA BBBB CCCC DDDD EEEE FFFF ГГГГГ ДДДДД ЕЕЕЕЕ ЖЖЖЖЖ."
        )
        assert len(result) <= 10


class TestFormatTriggers:
    def test_plain_items_unquoted(self):
        assert format_triggers(["foo", "/bar"]) == "triggers: [foo, /bar]"

    def test_items_with_spaces_are_quoted(self):
        result = format_triggers(["do the thing"])
        assert result == 'triggers: ["do the thing"]'

    def test_items_with_commas_are_quoted(self):
        result = format_triggers(["a, b"])
        assert result == 'triggers: ["a, b"]'


class TestProcessFile:
    def test_skips_file_that_already_has_triggers(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("---\nname: foo\ntriggers: [foo]\n---\nbody\n", encoding="utf-8")
        assert process_file(str(p)) == "skipped"

    def test_errors_on_missing_frontmatter(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text("# No frontmatter here\n", encoding="utf-8")
        assert process_file(str(p)) == "error"

    def test_errors_on_unreadable_file(self, tmp_path):
        missing = tmp_path / "does-not-exist.md"
        assert process_file(str(missing)) == "error"

    def test_adds_triggers_extracted_from_text(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text(
            '---\nname: foo\ndescription: >\n  Triggers: "/foo", "do thing"\n---\nbody\n',
            encoding="utf-8",
        )
        result = process_file(str(p))
        assert result == "added"
        new_text = p.read_text(encoding="utf-8")
        assert "triggers: [/foo" in new_text
        assert new_text.startswith("---")

    def test_falls_back_to_generated_triggers(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text(
            "---\nname: my-skill\ndescription: Does a Thing.\n---\nbody\n", encoding="utf-8"
        )
        result = process_file(str(p))
        assert result == "added"
        assert "triggers: [" in p.read_text(encoding="utf-8")

    def test_dry_run_does_not_write(self, tmp_path):
        p = tmp_path / "SKILL.md"
        original = "---\nname: my-skill\ndescription: Does a Thing.\n---\nbody\n"
        p.write_text(original, encoding="utf-8")
        result = process_file(str(p), dry_run=True)
        assert result == "added"
        assert p.read_text(encoding="utf-8") == original

    def test_uses_bsv_name_when_no_frontmatter_name(self, tmp_path):
        p = tmp_path / "SKILL.md"
        p.write_text(
            "---\ndescription: Does a Thing.\n---\n<!-- Скил   : bsv-name -->\nbody\n",
            encoding="utf-8",
        )
        result = process_file(str(p))
        assert result == "added"
        assert "bsv-name" in p.read_text(encoding="utf-8")


class TestMain:
    def test_runs_without_crashing_on_this_machine(self, capsys, monkeypatch):
        # WHY safe to call directly: main() globs a hardcoded personal path
        # (C:/Users/serge/.claude/skills/**/*.md) that does not exist on any
        # other machine or in CI, so this exercises the full function body
        # (glob -> filter -> loop -> summary print) against zero real files,
        # without ever touching this machine's actual ~/.claude/skills/.
        monkeypatch.setattr(sys, "argv", ["add_triggers.py"])
        main()
        out = capsys.readouterr().out
        assert "added=0 skipped=0 errors=0" in out

    def test_dry_run_flag_reflected_in_output(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["add_triggers.py", "--dry-run"])
        main()
        out = capsys.readouterr().out
        assert "[DRY RUN]" in out
