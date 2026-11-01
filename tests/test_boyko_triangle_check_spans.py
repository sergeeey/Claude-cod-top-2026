"""Tests for skills/extensions/boyko-triangle-audit/scripts/check_spans.py (audit №11, 2026-11-01).

Rules pinned: verbatim source_span (Kalaris ara-rigor-reviewer, read 2026-11-01), and the
independent-check vertex must not reuse the computation method.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extensions"
    / "boyko-triangle-audit"
    / "scripts"
    / "check_spans.py"
)


@pytest.fixture(scope="module")
def cs():
    spec = importlib.util.spec_from_file_location("check_spans", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    path = tmp_path / "decision.md"
    path.write_text("Rationale: regex composition rejected on held-out set.\n", encoding="utf-8")
    return path


def rec(vertex, method, span, artifact="decision.md", claim="C1"):
    return {
        "claim_id": claim,
        "vertex": vertex,
        "artifact": artifact,
        "source_span": span,
        "method_id": method,
        "supports": "regex composition fails held-out",
    }


def test_verbatim_span_passes(cs, artifact, tmp_path):
    records = [rec("Вычисления", "m-calc", "regex composition rejected on held-out set.")]
    assert cs.check(records, tmp_path) == []


def test_paraphrase_is_rejected(cs, artifact, tmp_path):
    records = [rec("Вычисления", "m-calc", "the regex approach failed on test data")]
    findings = cs.check(records, tmp_path)
    assert any("not a verbatim substring" in f for f in findings)


def test_missing_artifact_is_a_finding(cs, tmp_path):
    findings = cs.check([rec("Вычисления", "m-calc", "x", artifact="nope.md")], tmp_path)
    assert any("artifact not found" in f for f in findings)


def test_independent_check_must_use_other_method(cs, artifact, tmp_path):
    records = [
        rec("Вычисления", "m-regex", "regex composition rejected on held-out set."),
        rec("Независимая проверка", "m-regex", "regex composition rejected on held-out set."),
    ]
    findings = cs.check(records, tmp_path)
    assert any("a repeat, not an independent check" in f for f in findings)


def test_independent_check_with_other_method_passes(cs, artifact, tmp_path):
    records = [
        rec("Вычисления", "m-regex", "regex composition rejected on held-out set."),
        rec("Независимая проверка", "m-shadow", "regex composition rejected on held-out set."),
    ]
    assert cs.check(records, tmp_path) == []


def test_missing_fields_are_reported(cs, tmp_path):
    findings = cs.check([{"claim_id": "C1", "vertex": "Теория"}], tmp_path)
    assert any("missing or empty" in f for f in findings)


def test_main_exit_codes(cs, artifact, tmp_path, monkeypatch, capsys):
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps([rec("Вычисления", "m-calc", "regex composition rejected on held-out set.")]),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["check_spans.py", str(good), "--root", str(tmp_path)])
    assert cs.main() == 0

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([rec("Вычисления", "m-calc", "invented quote")]), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["check_spans.py", str(bad), "--root", str(tmp_path)])
    assert cs.main() == 1
    assert "FINDINGS" in capsys.readouterr().out
