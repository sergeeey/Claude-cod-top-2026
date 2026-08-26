"""Unit tests for scripts/build_skill_trigger_index.py.

WHY: never scan the real ~/.claude/skills directory in tests -- CI runners
don't have it, and coupling tests to a live personal catalog would make them
non-reproducible. Every test builds a synthetic fixture tree under tmp_path.
"""

import json

from build_skill_trigger_index import build_index, classify_trigger, extract_frontmatter


def _write_skill(base, name: str, frontmatter: str) -> None:
    skill_dir = base / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# {name}\n", encoding="utf-8")


# === classify_trigger ===


class TestClassifyTrigger:
    def test_slash(self):
        assert classify_trigger("/hyparb") == "slash"

    def test_colon(self):
        assert classify_trigger("skeptic:") == "colon"

    def test_hyphenated_bare(self):
        assert classify_trigger("agent-governance") == "hyphenated-bare"

    def test_phrase_english(self):
        assert classify_trigger("what are the alternatives") == "phrase"

    def test_phrase_cyrillic(self):
        assert classify_trigger("конкурирующие гипотезы") == "phrase"

    def test_bare_word(self):
        assert classify_trigger("test") == "bare"

    def test_bare_cyrillic_word(self):
        assert classify_trigger("аудит") == "bare"


# === extract_frontmatter ===


class TestExtractFrontmatter:
    def test_valid_frontmatter(self):
        text = '---\nname: foo\ntriggers: [/foo, "bar baz"]\n---\n\n# Foo\n'
        data = extract_frontmatter(text)
        assert data == {"name": "foo", "triggers": ["/foo", "bar baz"]}

    def test_malformed_yaml_returns_none(self):
        # WHY: mirrors the real ~/.claude/skills/analyst/SKILL.md bug -- a
        # stray quote inside a flow sequence breaks the YAML parser.
        text = "---\nname: analyst\ntriggers: [\"it's broken, no closing]\n---\n"
        assert extract_frontmatter(text) is None

    def test_no_frontmatter_block(self):
        assert extract_frontmatter("# Just a heading\nno frontmatter here\n") is None

    def test_frontmatter_is_not_a_mapping(self):
        text = "---\n- just\n- a\n- list\n---\n"
        assert extract_frontmatter(text) is None


# === build_index ===


class TestBuildIndex:
    def test_basic_extraction(self, tmp_path):
        _write_skill(
            tmp_path,
            "hypothesis-arbiter",
            'name: hypothesis-arbiter\ntriggers: [/hyparb, "конкурирующие гипотезы"]',
        )
        index = build_index(tmp_path)
        triggers = {(e["trigger"], e["skill"], e["kind"]) for e in index["entries"]}
        assert ("/hyparb", "hypothesis-arbiter", "slash") in triggers
        assert ("конкурирующие гипотезы", "hypothesis-arbiter", "phrase") in triggers
        assert index["_meta"]["skill_count"] == 1
        assert index["_meta"]["skipped"] == []

    def test_directory_without_skill_md_is_skipped(self, tmp_path):
        (tmp_path / "orient-workspace").mkdir()
        index = build_index(tmp_path)
        assert index["entries"] == []
        assert index["_meta"]["skill_count"] == 0
        assert "orient-workspace" not in index["_meta"]["skipped"]

    def test_malformed_frontmatter_is_skipped_not_fatal(self, tmp_path):
        _write_skill(tmp_path, "good-skill", 'name: good-skill\ntriggers: ["a working phrase"]')
        (tmp_path / "analyst").mkdir()
        (tmp_path / "analyst" / "SKILL.md").write_text(
            "---\nname: analyst\ntriggers: [\"it's broken, no closing]\n---\n", encoding="utf-8"
        )
        index = build_index(tmp_path)
        assert index["_meta"]["skill_count"] == 1
        assert index["_meta"]["skipped"] == ["analyst"]
        assert any(e["skill"] == "good-skill" for e in index["entries"])

    def test_skill_without_triggers_field_contributes_no_entries(self, tmp_path):
        _write_skill(tmp_path, "no-triggers", "name: no-triggers\ndescription: just a skill")
        index = build_index(tmp_path)
        assert index["entries"] == []
        assert index["_meta"]["skill_count"] == 0

    def test_name_falls_back_to_directory_name(self, tmp_path):
        _write_skill(tmp_path, "my-skill", "triggers: [/my-skill]")
        index = build_index(tmp_path)
        assert index["entries"][0]["skill"] == "my-skill"

    def test_output_is_json_serializable(self, tmp_path):
        _write_skill(tmp_path, "a", "name: a\ntriggers: [/a, phrase one]")
        index = build_index(tmp_path)
        json.dumps(index)  # must not raise
