"""Regression tests for skills/extensions/boyko-goal-expansion-100/scripts/validate_output.py.

Each test pins one defect from the 2026-11-01 audit of this validator.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extensions"
    / "boyko-goal-expansion-100"
    / "scripts"
    / "validate_output.py"
)


@pytest.fixture(scope="module")
def v():
    spec = importlib.util.spec_from_file_location("validate_output", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID_BODY = """
Type: cross_domain_transfer
Evidence: inference
Source domains: signal processing
Target gap: sparse telemetry

Core mechanism:
Change-point detection via CUSUM on residuals of a seasonal model.

Why it may work:
Telemetry drift is piecewise-constant, which matches CUSUM's assumption.

Required assumptions:
Residuals are approximately independent after deseasonalising.

Main obstacle:
Seasonal period is unknown for new sensors.

Cheapest test:
Replay one week of archived telemetry with injected step changes.

Falsifier:
If CUSUM detects fewer than 60% of injected steps, the mechanism is rejected.

Expected output:
A detector function plus a replay report.

Scores:
  relevance: 8
  feasibility: 7
  novelty: 4
  expected_impact: 6
  evidence_strength: 5
  falsifiability: 8
  speculation_penalty: 1
  confidence: 0.6

Sources:
local file: data/telemetry-notes.md
"""


def card(body: str = VALID_BODY) -> str:
    return f"## 1. Test idea\n{body}"


def run_check(v, body: str) -> list[str]:
    cards = v.split_cards(card(body))
    critical, _ = v.check_card(*cards[0])
    return critical


def test_valid_card_passes(v):
    assert run_check(v, VALID_BODY) == []


def test_empty_falsifier_rejected(v):
    body = VALID_BODY.replace(
        "Falsifier:\nIf CUSUM detects fewer than 60% of injected steps, "
        "the mechanism is rejected.\n",
        "Falsifier:\n\n",
    )
    findings = run_check(v, body)
    assert any("'Falsifier:' is empty" in f for f in findings)


def test_template_placeholder_falsifier_rejected(v):
    body = VALID_BODY.replace(
        "If CUSUM detects fewer than 60% of injected steps, the mechanism is rejected.",
        "[Какой результат должен заставить отказаться от идеи]",
    )
    findings = run_check(v, body)
    assert any("'Falsifier:' is empty" in f for f in findings)


def test_missing_falsifiability_rejected(v):
    body = VALID_BODY.replace("  falsifiability: 8\n", "")
    assert any("missing score 'falsifiability'" in f for f in run_check(v, body))


def test_missing_speculation_penalty_rejected(v):
    body = VALID_BODY.replace("  speculation_penalty: 1\n", "")
    assert any("speculation_penalty" in f for f in run_check(v, body))


def test_missing_confidence_rejected(v):
    body = VALID_BODY.replace("  confidence: 0.6\n", "")
    assert any("missing 'confidence'" in f for f in run_check(v, body))


def test_missing_score_is_critical_not_warning(v):
    body = VALID_BODY.replace("  novelty: 4\n", "")
    cards = v.split_cards(card(body))
    critical, warnings = v.check_card(*cards[0])
    assert any("missing score 'novelty'" in f for f in critical)
    assert not any("novelty" in w for w in warnings)


def test_negative_score_rejected(v):
    body = VALID_BODY.replace("  relevance: 8\n", "  relevance: -3\n")
    assert any("relevance=-3 out of range" in f for f in run_check(v, body))


def test_placeholder_range_text_in_score_rejected(v):
    body = VALID_BODY.replace("  relevance: 8\n", "  relevance: 0-10\n")
    assert any("relevance is not a number" in f for f in run_check(v, body))


def test_out_of_range_score_rejected(v):
    body = VALID_BODY.replace("  relevance: 8\n", "  relevance: 11\n")
    assert any("relevance=11 out of range" in f for f in run_check(v, body))


def test_speculation_penalty_must_be_integer_0_to_4(v):
    body = VALID_BODY.replace("  speculation_penalty: 1\n", "  speculation_penalty: 5\n")
    assert any("speculation_penalty=5" in f for f in run_check(v, body))


def test_confidence_out_of_range_rejected(v):
    body = VALID_BODY.replace("  confidence: 0.6\n", "  confidence: 1.4\n")
    assert any("confidence=1.4 out of range" in f for f in run_check(v, body))


def test_published_adjusted_score_must_match_formula(v):
    # priority = 2.00 + 1.40 + 1.20 + 0.75 + 0.40 + 0.80 = 6.55; minus penalty 1 = 5.55
    body = VALID_BODY + "adjusted_score: 9.00\n"
    assert any("does not match formula" in f for f in run_check(v, body))


def test_correct_adjusted_score_passes(v):
    body = VALID_BODY + "adjusted_score: 5.55\n"
    assert run_check(v, body) == []


def test_empty_cheapest_test_rejected(v):
    body = VALID_BODY.replace(
        "Replay one week of archived telemetry with injected step changes.\n",
        "\n",
    )
    assert any("'Cheapest test:' is empty" in f for f in run_check(v, body))


def test_invalid_type_rejected(v):
    body = VALID_BODY.replace("Type: cross_domain_transfer", "Type: magic")
    assert any("invalid Type 'magic'" in f for f in run_check(v, body))


def test_main_exit_codes(v, tmp_path, monkeypatch, capsys):
    good = tmp_path / "good.md"
    good.write_text(card(), encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text(card(VALID_BODY.replace("  falsifiability: 8\n", "")), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["validate_output.py", str(good)])
    assert v.main() == 0

    monkeypatch.setattr("sys.argv", ["validate_output.py", str(bad)])
    assert v.main() == 1
    assert "CRITICAL" in capsys.readouterr().out
