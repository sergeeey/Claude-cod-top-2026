"""Regression tests for ideas borrowed from competitors on 2026-11-01 (Pareto selection).

Each test pins one borrowed idea and its source, so it cannot silently disappear:
  - experiment-design: independent unit declared (own EstimandOps rule, pseudoreplication)
  - boyko-goal-expansion-100: low-diversity warning (jwynia brainstorming: spread, not count)
  - boyko-knowledge-audit: source existence is not support (Nature-Paper claim-source-verification)
  - boyko-leverage-map: actual metric vs declared goal (bayramannakov leverage-finder Phase 1.6)
  - boyko-method: reproduce-first (matt-riley systematic-debugging)
"""

import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "skills" / "extensions"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dx():
    return load(
        "design_experiments", EXT / "experiment-design" / "scripts" / "design_experiments.py"
    )


@pytest.fixture(scope="module")
def gv():
    return load(
        "validate_output", EXT / "boyko-goal-expansion-100" / "scripts" / "validate_output.py"
    )


def test_seeds_without_declared_unit_warn(dx):
    design = dx.generate_design({"num_seeds": 3})
    assert any("independent_unit not declared" in w for w in design["warnings"])


def test_declared_unit_silences_the_warning(dx):
    design = dx.generate_design({"num_seeds": 3, "independent_unit": "dataset split"})
    assert not any("independent_unit" in w for w in design["warnings"])


def test_single_seed_needs_no_unit(dx):
    design = dx.generate_design({"num_seeds": 1})
    assert not any("independent_unit" in w for w in design["warnings"])


def _card(number: int, card_type: str) -> str:
    return (
        f"## {number}. Idea {number}\n"
        f"Type: {card_type}\nEvidence: inference\nSource domains: x\nTarget gap: y\n"
        "Core mechanism:\nm\nWhy it may work:\nw\nRequired assumptions:\na\n"
        "Main obstacle:\no\nCheapest test:\nt\nFalsifier:\nf\nExpected output:\ne\n"
        "Scores:\n  relevance: 5\n  feasibility: 5\n  novelty: 5\n  expected_impact: 5\n"
        "  evidence_strength: 5\n  falsifiability: 5\n  speculation_penalty: 1\n"
        "  confidence: 0.5\nSources:\ns\n"
    )


def test_low_diversity_warning_fires(gv, tmp_path, monkeypatch):
    report = tmp_path / "report.md"
    report.write_text("".join(_card(i, "extension") for i in range(1, 6)), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validate_output.py", str(report)])
    buf = io.StringIO()
    with redirect_stdout(buf):
        gv.main()
    assert "low diversity: 1 type(s) across 5 cards" in buf.getvalue()


def test_diverse_report_has_no_diversity_warning(gv, tmp_path, monkeypatch):
    report = tmp_path / "report.md"
    types = ["extension", "cross_domain_transfer", "no_go", "hybrid", "new_hypothesis"]
    report.write_text("".join(_card(i + 1, t) for i, t in enumerate(types)), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["validate_output.py", str(report)])
    buf = io.StringIO()
    with redirect_stdout(buf):
        gv.main()
    assert "low diversity" not in buf.getvalue()


def test_knowledge_audit_source_support_rule():
    text = (EXT / "boyko-knowledge-audit" / "SKILL.md").read_text(encoding="utf-8")
    assert "источника не доказывает, что он подтверждает вывод" in text
    assert "Source support: not verified" in text
    assert (
        "| Evidence source | Source support | Confidence |" in text
    )  # column sits in the table
    assert "| Evidence source | Source support |" in text or "Source support" in text


def test_leverage_map_checks_actual_metric():
    text = (EXT / "boyko-leverage-map" / "SKILL.md").read_text(encoding="utf-8")
    assert "Фактическая метрика системы" in text
    assert "DIVERGENT" in text


def test_method_has_reproduce_first_rule():
    text = (EXT / "boyko-method" / "SKILL.md").read_text(encoding="utf-8")
    assert "Воспроизведение до вывода (reproduce-first" in text
    assert "среда, возможно, зависима" in text
