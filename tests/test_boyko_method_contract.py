"""Contract tests for skills/extensions/boyko-method (audit №4, 2026-11-01).

Pins the v1.5 fixes: plugin/SKILL version sync, evidence labels in the worked
example that match the skill's own criteria, the rules-loading check before the
falsification stage, and the stage contracts with the final-output block.
"""

import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "extensions" / "boyko-method"


@pytest.fixture(scope="module")
def skill_md() -> str:
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def plugin() -> dict:
    return json.loads((SKILL_DIR / "plugin.json").read_text(encoding="utf-8"))


def test_plugin_version_matches_skill_version(skill_md, plugin):
    skill_version = re.search(r'^version:\s*"([^"]+)"', skill_md, re.MULTILINE).group(1)
    assert plugin["version"] == skill_version == "1.6.0"


def test_hook_latency_example_is_not_verified(skill_md):
    row = next(line for line in skill_md.splitlines() if line.startswith("| hook_latency"))
    assert "[WEAK]" in row
    assert "[VERIFIED]" not in row


def test_plugin_trigger_example_is_not_inferred_without_chain(skill_md):
    row = next(line for line in skill_md.splitlines() if line.startswith("| plugin.json trigger"))
    assert "[WEAK]" in row
    assert "[INFERRED]" not in row


def test_example_is_marked_as_illustration(skill_md):
    assert "Пример ниже — иллюстрация, не результат проверки" in skill_md


def test_rules_loading_check_before_stage_5(skill_md):
    assert "Проверка загрузки правил" in skill_md
    assert "правила не загружены: <список>" in skill_md


def test_stage_contracts_table_present(skill_md):
    assert "## Контракты этапов (v1.5" in skill_md
    for stage in ("1 Атомизация", "2 Линзы", "3 Связи", "4 Сборка", "5 Проверка"):
        assert stage in skill_md


def test_final_output_blocking_rule(skill_md):
    assert "черновик: не прошёл блокирующие проверки" in skill_md


def test_triggers_field_kept(skill_md):
    # Regression: checking out main dropped this field from this branch's skill file.
    assert 'triggers: ["/boyko-method"' in skill_md
    assert '"построй модель проблемы"' in skill_md
    assert '"evidence-labeled analysis"' in skill_md


def test_return_section_present(skill_md):
    assert "## Возврат к предыдущим этапам (v1.6)" in skill_md
    assert "Возврат идёт к **самому раннему** затронутому этапу" in skill_md


def test_return_triggers_table_covers_stage_5_and_3_4(skill_md):
    assert "Опровергнута связь, на которой держится гипотеза" in skill_md
    assert "Degeneracy-чек" in skill_md


def test_return_limits_per_mode(skill_md):
    assert "Standard — не более 1 возврата, Deep — не более 2" in skill_md
    assert "возврат не выполнен: quick" in skill_md


def test_iteration_log_is_output_section_9(skill_md):
    assert "## 9. Журнал итераций" in skill_md
    assert "| # | Триггер | Вернулись к этапу | Отменено (id)" in skill_md
