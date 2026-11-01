"""Descriptions of the Boyko skills and experiment-design must be in Russian.

The description is what the user (and the router) reads when choosing a skill, so it
must match current behaviour and be in Russian. Checked for SKILL.md frontmatter,
plugin.json, and the registry entry for experiment-design.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "skills" / "extensions"
SKILLS = [
    "experiment-design",
    "boyko-goal-expansion-100",
    "boyko-knowledge-audit",
    "boyko-leverage-map",
    "boyko-method",
    "boyko-preflight",
    "pareto-leverage-scan",
    "sci-code-audit",
]
CYRILLIC = re.compile(r"[а-яА-ЯёЁ]")


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"no frontmatter in {path}"
    return yaml.safe_load(m.group(1))


def find_entry(node, name: str) -> dict | None:
    """Recursively find the registry mapping whose 'name' equals `name`."""
    if isinstance(node, dict):
        if node.get("name") == name:
            return node
        for value in node.values():
            found = find_entry(value, name)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_entry(item, name)
            if found:
                return found
    return None


@pytest.mark.parametrize("name", SKILLS)
def test_skill_md_description_is_russian(name):
    desc = frontmatter(EXT / name / "SKILL.md")["description"]
    assert CYRILLIC.search(desc), f"{name}: SKILL.md description is not Russian"


@pytest.mark.parametrize("name", SKILLS)
def test_plugin_description_is_russian(name):
    desc = json.loads((EXT / name / "plugin.json").read_text(encoding="utf-8"))["description"]
    assert CYRILLIC.search(desc), f"{name}: plugin.json description is not Russian"


def test_experiment_design_description_states_limits():
    desc = frontmatter(EXT / "experiment-design" / "SKILL.md")["description"]
    assert "не запускает" in desc
    assert "test_performed: false" in desc


def test_registry_entry_for_experiment_design_is_russian():
    registry = yaml.safe_load((ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8"))
    entry = find_entry(registry, "experiment-design")
    assert entry is not None
    assert CYRILLIC.search(entry["description"])
    assert "Не запускает" in entry["description"]


def test_sci_code_audit_registry_description_is_russian():
    # The registry description is what the router shows when choosing a skill.
    text = (ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8")
    start = text.index("  - name: sci-code-audit\n")
    end = text.index("\n  - name: ", start + 1)
    entry = text[start:end]
    desc = re.search(r'^    description: "(.*)"$', entry, re.MULTILINE).group(1)
    assert CYRILLIC.search(desc), "registry description of sci-code-audit must be Russian"
