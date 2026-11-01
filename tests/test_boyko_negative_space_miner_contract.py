"""Contract tests for boyko-negative-space-miner (Skill Audit 2.1 №9, P0/P1 fixes, 2026-11-01)."""

import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "extensions" / "boyko-negative-space-miner"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
PLUGIN = json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))


def test_plugin_name_matches_folder_without_claude_prefix():
    assert PLUGIN["name"] == "boyko-negative-space-miner"


def test_plugin_description_is_russian():
    assert re.search(r"[А-Яа-яЁё]", PLUGIN["description"])


def test_selection_audit_gate_exists():
    # P0: visible negative space is not the file drawer.
    assert "## Этап 2b — Аудит отбора публикаций" in SKILL
    assert "`SELECTION_SUSPECT`" in SKILL
    assert "winner's curse" in SKILL


def test_validation_holdout_and_freeze_before_validation():
    assert "замораживаются ДО открытия валидационного корпуса" in SKILL
    assert "Корпус, по которому вывелась гипотеза, для проверки не используется" in SKILL


def test_conflict_labels_are_multi_axis_not_forced_one_hot():
    assert "ровно одна метка" not in SKILL
    assert "несколько осей на строку" in SKILL
    assert "`primary_explanation`" in SKILL


def test_decline_effect_compares_alternatives_not_year_alone():
    assert "Одного тренда по году мало" in SKILL
    assert "`стандартную ошибку`" in SKILL


def test_named_dispute_is_a_rival_frame_not_privileged():
    assert "ПЕРВИЧЕН для Этапа 2/3" not in SKILL
    assert "ОБЯЗАТЕЛЬНЫЙ КОНКУРИРУЮЩИЙ КАРКАС" in SKILL
