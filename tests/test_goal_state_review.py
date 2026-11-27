"""Review findings on goal_state.py (2026-11-27): each test encodes one finding."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("goal_state", ROOT / "scripts" / "goal_state.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)

BASE = "# M\n\n## Цель\nShip it.\n\n## DoD\n1. Tests pass.\n2. Installed.\n\n## Ограничения\nNo live.\n"


def _init(tmp_path, text):
    c, s = tmp_path / "C.md", tmp_path / "S.json"
    c.write_text(text, encoding="utf-8")
    return c, s, gs.main(["init", "--contract", str(c), "--state", str(s)])


def test_duplicate_protected_heading_is_refused_at_init(tmp_path):
    _, _, rc = _init(tmp_path, BASE + "\n## DoD\n1. Other.\n")
    assert rc == 1


def test_second_dod_heading_added_later_is_drift(tmp_path):
    c, s, rc = _init(tmp_path, BASE)
    assert rc == 0
    rewritten = BASE.replace("1. Tests pass.\n2. Installed.", "1. Anything.")
    original_dod = "\n## DoD\n1. Tests pass.\n2. Installed.\n"
    c.write_text(rewritten + original_dod, encoding="utf-8")
    assert gs.main(["check", "--contract", str(c), "--state", str(s)]) == 1


def test_contract_without_countable_dod_is_refused(tmp_path):
    _, _, rc = _init(tmp_path, "# M\n\n## Цель\nShip it.\n\n## Ограничения\nNo live.\n")
    assert rc == 1


def test_bullet_and_paren_dod_items_are_counted(tmp_path):
    text = BASE.replace("1. Tests pass.\n2. Installed.", "- [ ] Tests pass.\n2) Installed.")
    c, s, rc = _init(tmp_path, text)
    assert rc == 0
    assert gs.load(s)["dod_count"] == 2


def test_heading_case_does_not_unprotect_dod(tmp_path):
    c, s, rc = _init(tmp_path, BASE.replace("## DoD", "## Dod"))
    assert rc == 0
    assert gs.load(s)["dod_count"] == 2


def test_empty_evidence_is_refused(tmp_path):
    c, s, rc = _init(tmp_path, BASE)
    args = [
        "decide",
        "--contract",
        str(c),
        "--state",
        str(s),
        "--verdict",
        "CONTINUE",
        "--evidence",
        "  ",
        "--next",
        "x",
    ]
    assert gs.main(args) == 1
