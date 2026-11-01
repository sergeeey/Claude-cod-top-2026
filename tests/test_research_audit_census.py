"""Census gate for research-audit: every experiment directory must be listed in experiments/INDEX.md.

Found 2026-11-01: four directories were absent from the index, and the earlier audit wrongly
reported that all were present. An index is a compressed view; it is not evidence that nothing is missing.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"


def _experiment_dirs():
    return sorted(
        p.name for p in EXPERIMENTS.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )


def test_every_experiment_directory_is_indexed():
    index = (EXPERIMENTS / "INDEX.md").read_text(encoding="utf-8")
    missing = [name for name in _experiment_dirs() if f"| {name} |" not in index]
    assert missing == [], f"experiment directories missing from experiments/INDEX.md: {missing}"


def test_census_counts_match_the_filesystem():
    # Guards against a silently shrinking census (e.g. a glob that drops real directories).
    assert len(_experiment_dirs()) >= 14


def test_research_audit_skill_states_the_census_gate():
    skill = (ROOT / "skills" / "extensions" / "research-audit" / "SKILL.md").read_text(encoding="utf-8")
    assert "Census gate" in skill
    assert "UNINDEXED" in skill and "INDEX_ONLY" in skill
    assert "Отсутствие записи в индексе не означает отсутствие эксперимента" in skill
    assert "читает ВСЕ артефакты" not in skill
