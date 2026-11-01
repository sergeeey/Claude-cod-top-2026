"""Contract tests for boyko-novelty-assessment (Skill Audit 2.1 new series №1, P0/P1 fixes, 2026-11-01)."""

import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "extensions" / "boyko-novelty-assessment"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
PLUGIN = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))


def _frontmatter() -> str:
    m = re.match(r"^---\n(.*?)\n---", SKILL, re.DOTALL)
    assert m
    return m.group(1)


def test_name_and_descriptions_are_russian_and_prefixed():
    assert re.search(r"^name: boyko-novelty-assessment$", _frontmatter(), re.MULTILINE)
    assert re.search(r"[А-Яа-яЁё]", _frontmatter())
    assert re.search(r"[А-Яа-яЁё]", PLUGIN["description"])
    assert PLUGIN["name"] == "boyko-novelty-assessment"


def test_no_numeric_transfer_of_screening_rates():
    assert "13%→3%" not in SKILL
    assert "13% miss rate" not in SKILL
    assert "no exact rate is transferred" in SKILL


def test_novelty_claim_is_frozen_before_search():
    assert "### Step 1.4: Frozen novelty claim (before any search)" in SKILL
    assert "non_novel_if:" in SKILL
    assert "Freeze this block" in SKILL


def test_novel_is_bounded_not_a_fact():
    assert "NO_MATERIAL_OVERLAP_FOUND_WITHIN_AUDITED_BOUNDARY" in SKILL
    assert "not an established fact" in SKILL


def test_chase_complete_does_not_mean_neighbourhood_exhausted():
    assert "this means the planned calls finished, not that the citation neighbourhood is exhausted" in SKILL


def test_relative_recall_one_is_only_a_diagnostic_and_full_text_is_required():
    assert "relative_recall = 1.0 only says the known benchmark set was returned" in SKILL
    assert "read the full text of the 3–7 closest candidates" in SKILL
