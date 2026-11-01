"""Tests for scripts/promotion_score_observer.py.

Covers the OBSERVE-only discipline this file exists to enforce: computes and
logs, never blocks/reorders, and touches ONLY its own new log file (telemetry
isolation) -- same shape as scripts/false_pass_rate.py's own test coverage,
applied to a different signal.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import promotion_score_observer as pso


def _write_graph(exp_dir: Path, priority_factors: dict | None = None) -> None:
    exp_dir.mkdir(parents=True, exist_ok=True)
    lines = [f'id: "{exp_dir.name}"', "mode: DEVELOP", "status: ACTIVE"]
    if priority_factors is not None:
        lines.append("priority_factors:")
        for k, v in priority_factors.items():
            lines.append(f"  {k}: {'null' if v is None else v}")
    (exp_dir / "graph.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


_FULL_FACTORS = {
    "expected_value": 0.8,
    "falsifiability": 0.6,
    "information_gain": 0.7,
    "evidence_independence": 0.5,
    "expected_cost": 0.2,
}


class TestComputeProposedPriority:
    def test_computes_naive_product_over_cost(self):
        result = pso.compute_proposed_priority(_FULL_FACTORS)
        assert result == 0.8 * 0.6 * 0.7 * 0.5 / 0.2

    def test_missing_factor_returns_none(self):
        incomplete = {**_FULL_FACTORS, "expected_value": None}
        assert pso.compute_proposed_priority(incomplete) is None

    def test_zero_cost_returns_none(self):
        zero_cost = {**_FULL_FACTORS, "expected_cost": 0}
        assert pso.compute_proposed_priority(zero_cost) is None

    def test_empty_factors_returns_none(self):
        assert pso.compute_proposed_priority({}) is None


class TestCollectObservations:
    def test_fully_filled_experiment_observed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", _FULL_FACTORS)
        observations = pso.collect_observations()
        assert len(observations) == 1
        assert observations[0]["experiment_id"] == "20260101-a"
        assert observations[0]["proposed_priority"] is not None
        assert observations[0]["actual_outcome"] is None  # never filled in by this script

    def test_unfilled_experiment_not_observed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "20260101-a", None)  # no priority_factors block at all
        observations = pso.collect_observations()
        assert observations == []

    def test_partially_filled_experiment_not_observed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        partial = {**_FULL_FACTORS, "expected_cost": None}
        _write_graph(tmp_path / "20260101-a", partial)
        observations = pso.collect_observations()
        assert observations == []

    def test_template_dir_excluded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        _write_graph(tmp_path / "_template", _FULL_FACTORS)
        observations = pso.collect_observations()
        assert observations == []


class TestTelemetryIsolation:
    """Never blocks/reorders anything, and touches ONLY its own new log file."""

    def test_dry_run_never_writes_log(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        log_path = tmp_path / "shadow.jsonl"
        monkeypatch.setattr(pso, "LOG_PATH", log_path)
        _write_graph(tmp_path / "20260101-a", _FULL_FACTORS)

        pso.main(["--dry-run"])

        assert not log_path.exists()

    def test_append_only_touches_its_own_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        log_path = tmp_path / "logs" / "shadow.jsonl"
        monkeypatch.setattr(pso, "LOG_PATH", log_path)
        _write_graph(tmp_path / "20260101-a", _FULL_FACTORS)

        pso.main([])

        assert log_path.exists()
        # WHY list(tmp_path.rglob) not just checking log_path: proves NOTHING
        # else under tmp_path was created/modified by this run.
        all_files = {p for p in tmp_path.rglob("*") if p.is_file()}
        expected = {tmp_path / "20260101-a" / "graph.yaml", log_path}
        assert all_files == expected

    def test_appends_without_truncating_existing_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        log_path = tmp_path / "shadow.jsonl"
        log_path.write_text('{"pre_existing": true}\n', encoding="utf-8")
        monkeypatch.setattr(pso, "LOG_PATH", log_path)
        _write_graph(tmp_path / "20260101-a", _FULL_FACTORS)

        pso.main([])

        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert json.loads(lines[0]) == {"pre_existing": True}
        assert len(lines) == 2

    def test_never_mutates_graph_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(pso, "LOG_PATH", tmp_path / "shadow.jsonl")
        _write_graph(tmp_path / "20260101-a", _FULL_FACTORS)
        graph_path = tmp_path / "20260101-a" / "graph.yaml"
        before = graph_path.read_text(encoding="utf-8")

        pso.main([])

        assert graph_path.read_text(encoding="utf-8") == before

    def test_exit_code_zero_regardless_of_observations(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pso, "EXPERIMENTS_DIR", tmp_path)
        monkeypatch.setattr(pso, "LOG_PATH", tmp_path / "shadow.jsonl")
        assert pso.main(["--dry-run"]) == 0
