"""Tests for skills/extensions/boyko-ripple/scripts/rank_ripple.py (audit №7, 2026-11-01).

Pins the ranking rule: value * coefficient / cost, with a stability check across alternative
coefficient sets. The audit's own example (A: 6, HIGH, cost 2; B: 10, MEDIUM, cost 2) flips
to a tie under the second coefficient set, so the script must refuse to name a winner.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extensions"
    / "boyko-ripple"
    / "scripts"
    / "rank_ripple.py"
)


@pytest.fixture(scope="module")
def rr():
    spec = importlib.util.spec_from_file_location("rank_ripple", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def opp(name, value, conf, cost):
    return {"name": name, "value": value, "effect_confidence": conf, "test_cost_days": cost}


def test_default_priorities_match_audit_arithmetic(rr):
    items = [opp("A", 6, "HIGH", 2), opp("B", 10, "MEDIUM", 2)]
    result = rr.rank(items)
    assert result["priorities"] == {"A": 2.7, "B": 2.5}
    assert result["order"] == ["A", "B"]


def test_audit_example_is_unstable_under_alternative_coefficients(rr):
    items = [opp("A", 6, "HIGH", 2), opp("B", 10, "MEDIUM", 2)]
    result = rr.rank(items)
    assert result["stable"] is False
    assert result["verdict"] == "порядок неустойчив: победитель не назван"


def test_clear_gap_is_stable(rr):
    items = [opp("A", 9, "HIGH", 1), opp("B", 2, "LOW", 5)]
    result = rr.rank(items)
    assert result["stable"] is True
    assert result["verdict"] == "winner: A"


def test_tie_under_default_is_unstable(rr):
    items = [opp("A", 5, "MEDIUM", 1), opp("B", 5, "MEDIUM", 1)]
    assert rr.rank(items)["stable"] is False


@pytest.mark.parametrize(
    "bad",
    [
        [],
        "not a list",
        [{"name": "", "value": 5, "effect_confidence": "HIGH", "test_cost_days": 1}],
        [opp("A", 0, "HIGH", 1)],
        [opp("A", 11, "HIGH", 1)],
        [opp("A", True, "HIGH", 1)],
        [opp("A", 5, "CERTAIN", 1)],
        [opp("A", 5, "HIGH", 0)],
        [opp("A", 5, "HIGH", -2)],
    ],
)
def test_invalid_input_is_rejected(rr, bad):
    with pytest.raises(rr.InvalidInput):
        rr.validate(bad)


def test_main_exit_codes(rr, tmp_path, monkeypatch, capsys):
    stable = tmp_path / "stable.json"
    stable.write_text(json.dumps([opp("A", 9, "HIGH", 1), opp("B", 2, "LOW", 5)]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["rank_ripple.py", str(stable)])
    assert rr.main() == 0

    unstable = tmp_path / "unstable.json"
    unstable.write_text(
        json.dumps([opp("A", 6, "HIGH", 2), opp("B", 10, "MEDIUM", 2)]), encoding="utf-8"
    )
    monkeypatch.setattr("sys.argv", ["rank_ripple.py", str(unstable)])
    assert rr.main() == 1

    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps([opp("A", 0, "HIGH", 1)]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["rank_ripple.py", str(broken)])
    assert rr.main() == 2
    assert "ERROR" in capsys.readouterr().out
