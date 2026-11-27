"""Tests for scripts/goal_state.py: explicit Decide step and goal-drift detection."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("goal_state", ROOT / "scripts" / "goal_state.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)

CONTRACT = """# Mission

## Цель
Ship the release candidate.

## DoD
1. End-to-end run passes.
2. Install and rollback verified.

## Ограничения
No live changes.

## Следующее действие
Run gates.
"""


def _setup(tmp_path):
    c = tmp_path / "CONTRACT.md"
    s = tmp_path / "state.json"
    c.write_text(CONTRACT, encoding="utf-8")
    assert gs.main(["init", "--contract", str(c), "--state", str(s)]) == 0
    return c, s


def test_init_counts_dod_and_refuses_overwrite(tmp_path):
    c, s = _setup(tmp_path)
    assert gs.load(s)["dod_count"] == 2
    assert gs.main(["init", "--contract", str(c), "--state", str(s)]) == 1


def test_unprotected_edit_is_not_drift(tmp_path):
    c, s = _setup(tmp_path)
    c.write_text(CONTRACT.replace("Run gates.", "Run the install rehearsal."), encoding="utf-8")
    assert gs.main(["check", "--contract", str(c), "--state", str(s)]) == 0


def test_goal_edit_is_drift(tmp_path):
    c, s = _setup(tmp_path)
    c.write_text(
        CONTRACT.replace("Ship the release candidate.", "Write a blog post."), encoding="utf-8"
    )
    assert gs.main(["check", "--contract", str(c), "--state", str(s)]) == 1


def test_dropping_a_dod_criterion_is_drift(tmp_path):
    c, s = _setup(tmp_path)
    c.write_text(CONTRACT.replace("2. Install and rollback verified.\n", ""), encoding="utf-8")
    assert gs.main(["check", "--contract", str(c), "--state", str(s)]) == 1


def test_done_without_every_criterion_is_refused(tmp_path):
    c, s = _setup(tmp_path)
    args = ["decide", "--contract", str(c), "--state", str(s), "--verdict", "DONE"]
    assert gs.main(args + ["--dod", "1", "--evidence", "e2e log"]) == 1
    assert gs.load(s)["decisions"] == []
    assert gs.main(args + ["--dod", "1", "--dod", "2", "--evidence", "e2e log"]) == 0


def test_decision_without_evidence_is_refused(tmp_path):
    c, s = _setup(tmp_path)
    args = [
        "decide",
        "--contract",
        str(c),
        "--state",
        str(s),
        "--verdict",
        "CONTINUE",
        "--next",
        "x",
    ]
    assert gs.main(args) == 1


def test_continue_needs_next_action_and_unknown_verdict_refused(tmp_path):
    c, s = _setup(tmp_path)
    base = ["decide", "--contract", str(c), "--state", str(s), "--evidence", "ci green"]
    assert gs.main(base + ["--verdict", "CONTINUE"]) == 1
    assert gs.main(base + ["--verdict", "MAYBE", "--next", "x"]) == 1
    assert gs.main(base + ["--verdict", "CONTINUE", "--next", "run rehearsal"]) == 0
    assert gs.load(s)["decisions"][-1]["verdict"] == "CONTINUE"


def test_decide_refused_after_goal_drift(tmp_path):
    c, s = _setup(tmp_path)
    c.write_text(CONTRACT.replace("No live changes.", "Anything goes."), encoding="utf-8")
    args = [
        "decide",
        "--contract",
        str(c),
        "--state",
        str(s),
        "--verdict",
        "CONTINUE",
        "--evidence",
        "x",
        "--next",
        "y",
    ]
    assert gs.main(args) == 1
