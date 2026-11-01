"""Pareto borrowings and description upkeep for four Boyko skills (audits №6–№9, 2026-11-01).

- boyko-specialist: citation-graph walk and retraction check (AcademicForge, read 2026-11-01)
- boyko-scientific-consortium: record dissent, 'search-incomplete' status (K-Dense, read 2026-11-01)
- descriptions and plugin.json names/language for the four skills changed in those audits
"""

import json
import re
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parent.parent / "skills" / "extensions"
CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")
SKILLS = [
    "boyko-specialist",
    "boyko-scientific-consortium",
    "boyko-project-radar",
    "boyko-ripple",
]


def read(name: str) -> str:
    return (EXT / name / "SKILL.md").read_text(encoding="utf-8")


def description(name: str) -> str:
    text = read(name)
    m = re.search(r"^description:(.*?)(?=^[a-z_-]+:)", text, re.MULTILINE | re.DOTALL)
    assert m, f"no description block in {name}"
    return m.group(1)


def test_specialist_citation_graph_and_retraction_check():
    text = read("boyko-specialist")
    assert "Граф цитирования (v1.4" in text
    assert "update-to" in text
    assert "Дедупликация кандидатов по DOI" in text


def test_consortium_dissent_and_search_incomplete():
    text = read("boyko-scientific-consortium")
    assert "Несогласие, воздержавшиеся и отрицательные свидетельства" in text
    assert "`search-incomplete`" in text


@pytest.mark.parametrize("name", SKILLS)
def test_plugin_name_matches_folder_and_is_russian(name):
    plugin = json.loads((EXT / name / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == name
    assert CYRILLIC.search(plugin["description"]), f"{name}: plugin description not Russian"


@pytest.mark.parametrize("name", SKILLS)
def test_skill_description_is_russian(name):
    assert CYRILLIC.search(description(name)), f"{name}: SKILL description not Russian"


def test_descriptions_reflect_changed_behaviour():
    assert "identity" not in description("boyko-specialist")  # no English leftovers
    assert "Проверяет личность, вклад и применимость" in description("boyko-specialist")
    assert "identification gate" in description("boyko-scientific-consortium")
    assert "HEAD-статус" in description("boyko-project-radar")
    assert "проверкой устойчивости порядка" in description("boyko-ripple")
