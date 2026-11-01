"""Contract tests for boyko-hypothesis-arbiter (Skill Audit 2.1 №4, P0/P1 fixes, 2026-11-01).

The skill is prose, so these tests pin the wording and the benchmark ledger rather than behaviour.
Each test names the audit defect it guards against.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skills" / "extensions" / "boyko-hypothesis-arbiter"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
LEDGER = json.loads(
    (REPO / "benchmarks" / "strong-inference" / "ledger-2026-07-23.json").read_text(encoding="utf-8")
)


def _frontmatter() -> str:
    m = re.match(r"^---\n(.*?)\n---", SKILL, re.DOTALL)
    assert m, "SKILL.md must start with frontmatter"
    return m.group(1)


# --- P0: zero survivors is not "all explanations are false" ---------------------------


def test_zero_survivors_is_candidate_set_exhausted_not_all_false():
    assert "CANDIDATE_SET_EXHAUSTED" in SKILL
    assert "все ложны" not in SKILL
    assert "НЕ значит, что все возможные объяснения ложны" in SKILL


# --- P0: one status per hypothesis with fixed precedence -------------------------------


def test_status_precedence_is_ordered_and_documented():
    section = SKILL[SKILL.index("**Статусы по итогу") :]
    killed = section.index("УБИТА")
    questionable = section.index("ПОД ВОПРОСОМ")
    survived = section.index("ВЫЖИЛА")
    assert killed < questionable < survived, "precedence must be UBITA, then POD VOPROSOM, then VYZHILA"
    assert "ровно один статус" in section


def test_single_source_cannot_be_survived():
    # The audit's conflict: a single source with Confidence >= 0.55 was both SURVIVED and QUESTIONABLE.
    section = SKILL[SKILL.index("**Статусы по итогу") :]
    assert "ИЛИ опирается на один источник (даже при Confidence ≥ 0.55)" in section
    assert "не одиночный источник" in section


def test_confidence_is_declared_as_not_a_probability():
    assert "не вероятность истинности" in SKILL


# --- P1: caps do not depend on hypothesis order ----------------------------------------


def test_strong_alternative_cap_is_two_pass_and_order_independent():
    assert "сначала вычислить raw Confidence всех гипотез" in SKILL
    assert "Порядок гипотез не влияет на результат" in SKILL


# --- P1: 4-6 is a target; minimum is two distinct mechanisms; no padding ---------------


def test_hypothesis_count_is_a_target_range_not_a_hard_minimum():
    assert "Цель **3–6 гипотез**" in SKILL
    assert "2 механистически различных" in SKILL
    assert "Минимум **4 гипотезы**" not in SKILL


def test_description_reflects_the_new_range():
    assert "3-6 конкурирующих объяснений" in _frontmatter()
    assert "4-6 конкурирующих" not in _frontmatter()


def test_frontmatter_name_matches_folder():
    assert re.search(r"^name: boyko-hypothesis-arbiter$", _frontmatter(), re.MULTILINE)


# --- P1: benchmark ledger is the machine-readable source --------------------------------


def _score(grades: dict, weight: dict) -> float:
    return sum(weight.get(g, 0) for g in grades.values())


def test_ledger_headline_totals_match_the_grades():
    main = LEDGER["main_run"]
    for arm in ("A", "B", "C"):
        grades = {task: row[arm] for task, row in main.items()}
        strict = _score(grades, {"CORRECT": 1})
        weighted = _score(grades, {"CORRECT": 1, "PARTIALLY CORRECT": 0.5})
        assert strict == LEDGER["headline_totals"]["strict"][arm], arm
        assert weighted == LEDGER["headline_totals"]["weighted"][arm], arm


def test_provenance_conflict_is_recorded_not_hidden():
    conflicts = LEDGER["provenance_conflicts"]
    assert len(conflicts) == 1
    c = conflicts[0]
    assert (c["task"], c["arm"]) == ("2", "B")
    assert c["main_run_grade"] != c["sensitivity_section_original_grade"]
    assert c["status"] == "UNRESOLVED"


def test_ledger_main_grade_matches_markdown_main_table():
    md = (REPO / "benchmarks" / "strong-inference" / "run-2026-07-23-full.md").read_text(encoding="utf-8")
    row = next(line for line in md.splitlines() if line.startswith("| 2 | negative control |"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    # cells: task, category, A, B, C
    assert cells[3] == LEDGER["main_run"]["2"]["B"]


def test_sensitivity_stability_is_consistent_with_the_ledger():
    b = LEDGER["sensitivity_shuffled_order"]["B"]
    flips = [t for t, g in b.items() if g["original"] != g["shuffled"]]
    assert sorted(flips, key=int) == ["2", "3"]
    # Task 2 counts as a flip only under the sensitivity section's own original grade.
    assert "8/10" in LEDGER["stability"]["B"]
