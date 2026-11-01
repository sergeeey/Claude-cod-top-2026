"""Contract tests for estimand-l0-gate (Skill Audit 2.1 №3, 2026-11-01).

Pins: typed contracts per question type, decision-threshold statuses instead of verbal MCID,
draft status before materialization, mixed-claim decomposition, narrow scope, and the bridge's
handling of a qualitative threshold.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills" / "extensions" / "estimand-l0-gate" / "SKILL.md").read_text(encoding="utf-8")
BRIDGE = (ROOT / "skills" / "extensions" / "estimand-bridge" / "SKILL.md").read_text(encoding="utf-8")
REGISTRY = (ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8")


def test_type_specific_contracts_exist():
    assert "**Descriptive**" in SKILL and "measurement_definition" in SKILL
    assert "**Predictive**" in SKILL and "prediction_horizon" in SKILL and "information_available_at_prediction" in SKILL
    assert "**Causal**" in SKILL and "intervention" in SKILL and "intercurrent_events" in SKILL


def test_verbal_mcid_is_not_a_filled_field():
    assert "Такой текст выглядит полным" in SKILL
    assert "ложная полнота" in SKILL


def test_decision_threshold_has_explicit_statuses():
    for status in ("QUANTIFIED", "QUALITATIVELY_DEFINED", "NOT_APPLICABLE", "UNRESOLVED"):
        assert f"`{status}`" in SKILL, status


def test_ice_is_causal_only():
    assert "только для causal" in SKILL


def test_mixed_claims_are_decomposed_before_estimand():
    assert "## Смешанные claim-ы" in SKILL
    assert "claim-decomposer" in SKILL


def test_file_is_draft_until_structure_check():
    assert "`draft_l0`" in SKILL
    assert "принимает только материализованный файл" in SKILL


def test_bridge_handles_qualitative_threshold_without_pass():
    assert "NOT_MECHANICALLY_CHECKABLE" in BRIDGE
    assert "НЕ может быть PASS по этому пункту" in BRIDGE


def test_registry_entry_exists_and_is_russian():
    m = re.search(r"  - name: estimand-l0-gate\n(.*?)\n  - name: ", REGISTRY, re.DOTALL)
    assert m, "estimand-l0-gate must be registered"
    assert re.search(r"[А-Яа-яЁё]", m.group(1))
