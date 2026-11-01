"""Contract tests for boyko-construct-measurement-gate (Skill Audit 2.1 new series №2, P0/P1, 2026-11-01)."""

import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "extensions" / "boyko-construct-measurement-gate"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
PLUGIN = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))


def test_plugin_name_has_no_stale_prefix_and_description_is_russian():
    assert PLUGIN["name"] == "boyko-construct-measurement-gate"
    assert re.search(r"[А-Яа-яЁё]", PLUGIN["description"])


def test_mixed_cause_class_exists_and_binary_is_not_the_only_option():
    assert "REAL_DOMINANT" in SKILL
    assert "MEASUREMENT_DOMINANT" in SKILL
    assert "`MIXED`" in SKILL
    assert "Observed = Real signal + Measurement distortion + Noise" in SKILL


def test_discriminating_test_handles_mixed_case():
    assert "при классе MIXED — тест, который оценивает доли вклада" in SKILL


def test_channel_independence_is_multidimensional():
    for dim in ("| sensor |", "| processing |", "| labels |", "| observer |", "| data source |"):
        assert dim in SKILL, dim


def test_evidence_status_is_separate_from_impact():
    assert "`evidence_status`" in SKILL
    assert "Уровень HIGH без `evidence_status` не выводится" in SKILL


def test_benchmark_measures_downstream_adjudication_not_the_gate_verdict():
    assert "улучшает ли diagnostic packet решение независимого adjudicator" in SKILL
    assert "Прежний benchmark измерял сам вердикт gate" in SKILL
