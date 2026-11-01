"""Contract tests for sci-code-audit (Skill Audit 2.1 №8, P0/P1 fixes, 2026-11-01)."""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = (REPO / "skills" / "extensions" / "sci-code-audit" / "SKILL.md").read_text(encoding="utf-8")
REGISTRY = (REPO / "skills" / "registry.yaml").read_text(encoding="utf-8")


def _entry() -> str:
    start = REGISTRY.index("  - name: sci-code-audit\n")
    end = REGISTRY.index("\n  - name: ", start + 1)
    return REGISTRY[start:end]


def test_sealed_ground_truth_is_not_tracked():
    # P0: the sealed answer key must not be readable by agents working in the repo.
    tracked = subprocess.run(
        ["git", "ls-files", "benchmarks/sci-code-audit/_sealed_ground_truth.md"],
        cwd=REPO, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    ).stdout.strip()
    assert tracked == ""
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "benchmarks/sci-code-audit/_sealed_ground_truth.md" in ignore


def test_registry_maturity_is_dogfooded_with_a_citable_artifact():
    entry = _entry()
    assert "maturity: dogfooded" in entry
    m = re.search(r'maturity_evidence: "([^ ]+) -- ', entry)
    assert m, "maturity_evidence must begin with a repo-relative path"
    assert (REPO / m.group(1)).is_file()


def test_registry_entry_does_not_carry_the_retired_validated_marker():
    assert "[VALIDATED:" not in _entry()
    assert "[VALIDATED:" not in SKILL


def test_overall_verdict_is_vector_based_and_unverified_is_not_pass():
    assert "## Overall Verdict — векторный" in SKILL
    for vector in ("implementation_integrity", "numerical_integrity", "data_provenance",
                   "statistical_validity", "claim_alignment", "reproducibility"):
        assert vector in SKILL, vector
    assert "`UNVERIFIED` никогда не считается PASS" in SKILL
    assert "`STOP` при FAIL в `claim_alignment` или `data_provenance`" in SKILL


def test_metrics_are_reported_separately():
    assert "**Known-Defect Recall**" in SKILL
    assert "**Novel Verified Findings**" in SKILL
    assert "Результаты benchmark сообщать по обеим метрикам раздельно." in SKILL
