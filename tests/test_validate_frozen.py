"""Tests for ``validate_experiment --frozen``: freeze ordering, manifest and threshold checks."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import validate_experiment  # noqa: E402
from validate_experiment import check_frozen  # noqa: E402

EXP_ID = "20260901-demo"

CLAIM = """# claim.md — {id}
## Frozen Protocol
| Field | Value |
|---|---|
| Baseline (name, commit SHA, config hash) | base@abc123 |
| Primary metric (name, how it is computed) | recall |
| Success threshold (number and direction) | >= 0.80 |
| MCID (number, units, reason) | 0.10 absolute |
| KEEP if | recall >= 0.80 on holdout |
| REJECT if | recall < 0.70 |
| INCONCLUSIVE otherwise | 0.70 <= recall < 0.80 |
| Holdout (case IDs, labels path, sha256 of labels file) | h1..h6, labels/holdout.json |
| Power line: `n, baseline_or_sigma, alpha, power, MDE, MCID` | 6, 0.33, 0.05, 0.8, 0.5, 0.10 |
"""

DECISION = "# decision\nSuccess threshold: >= 0.80 (frozen)\nVerdict: KEEP\n"


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def _commit(root: Path, message: str, *paths: str) -> str:
    _git(root, "add", "--", *paths)
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _manifest(freeze_sha: str, labels_sha: str) -> str:
    return (
        "# Artifact Manifest\n\n## Freeze Record\n\n"
        "| Item | Value |\n|---|---|\n"
        f"| Protocol commit SHA | {freeze_sha} |\n"
        "| Protocol commit date (UTC) | 2026-09-01 |\n"
        f"| Holdout labels sha256 (must match the file at run time) | {labels_sha} |\n"
        "| Holdout case count | 6 |\n"
        "| Amendments (new experiment IDs that replaced a frozen value) | none |\n"
    )


def _setup(tmp_path: Path) -> tuple[Path, Path, str]:
    """Repo with a valid freeze, a manifest record and a labels file. Returns (exp, labels, sha)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    exp = root / "experiments" / EXP_ID
    exp.mkdir(parents=True)
    labels = root / "labels" / "holdout.json"
    labels.parent.mkdir()
    labels.write_text('{"h1": 1}', encoding="utf-8")
    labels_sha = hashlib.sha256(labels.read_bytes()).hexdigest()

    (exp / "claim.md").write_text(CLAIM.format(id=EXP_ID), encoding="utf-8")
    freeze_sha = _commit(root, f"protocol({EXP_ID}): freeze thresholds and holdout", "experiments")

    (exp / "manifest.md").write_text(_manifest(freeze_sha, labels_sha), encoding="utf-8")
    _commit(root, f"record freeze for {EXP_ID}", "experiments")

    (exp / "decision.md").write_text(DECISION, encoding="utf-8")
    _commit(root, f"result: {EXP_ID}", "experiments")
    return exp, labels, labels_sha


def _statuses(results) -> dict[str, str]:
    return {r.name: r.status for r in results}


class TestCheckFrozen:
    def test_valid_freeze_passes_every_check(self, tmp_path):
        exp, labels, _ = _setup(tmp_path)
        statuses = _statuses(check_frozen(exp, labels))
        assert set(statuses.values()) == {"pass"}, statuses

    def test_missing_section_fails(self, tmp_path):
        exp = tmp_path / EXP_ID
        exp.mkdir()
        (exp / "claim.md").write_text("# claim\nno block here\n", encoding="utf-8")
        results = check_frozen(exp, None)
        assert [r.name for r in results] == ["frozen:section"]
        assert results[0].status == "fail"

    def test_empty_threshold_fails(self, tmp_path):
        exp, labels, _ = _setup(tmp_path)
        claim = (exp / "claim.md").read_text(encoding="utf-8")
        (exp / "claim.md").write_text(claim.replace("| >= 0.80 |", "| |"), encoding="utf-8")
        statuses = _statuses(check_frozen(exp, labels))
        assert statuses["frozen:fields"] == "fail"

    def test_outside_git_fails(self, tmp_path, monkeypatch):
        # WHY: the temp dir may sit inside a git repo (here the home dir is one), so
        # simulate "git cannot answer" instead of relying on the location.
        monkeypatch.setattr(validate_experiment, "_git", lambda *args: None)
        exp = tmp_path / EXP_ID
        exp.mkdir()
        (exp / "claim.md").write_text(CLAIM.format(id=EXP_ID), encoding="utf-8")
        statuses = _statuses(check_frozen(exp, None))
        assert statuses["frozen:git"] == "fail"

    def test_threshold_changed_after_result_fails(self, tmp_path):
        exp, labels, _ = _setup(tmp_path)
        (exp / "decision.md").write_text(DECISION.replace(">= 0.80", ">= 0.70"), encoding="utf-8")
        statuses = _statuses(check_frozen(exp, labels))
        assert statuses["frozen:threshold"] == "fail"

    def test_labels_hash_mismatch_fails(self, tmp_path):
        exp, labels, _ = _setup(tmp_path)
        labels.write_text('{"h1": 0}', encoding="utf-8")
        statuses = _statuses(check_frozen(exp, labels))
        assert statuses["frozen:labels"] == "fail"

    def test_labels_not_given_warns(self, tmp_path):
        exp, _, _ = _setup(tmp_path)
        statuses = _statuses(check_frozen(exp, None))
        assert statuses["frozen:labels"] == "warn"

    def test_result_before_freeze_fails(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        _git(root, "init", "-q")
        exp = root / "experiments" / EXP_ID
        exp.mkdir(parents=True)
        (exp / "decision.md").write_text(DECISION, encoding="utf-8")
        _commit(root, "result first", "experiments")
        (exp / "claim.md").write_text(CLAIM.format(id=EXP_ID), encoding="utf-8")
        _commit(root, f"protocol({EXP_ID}): late freeze", "experiments")
        statuses = _statuses(check_frozen(exp, None))
        assert statuses["frozen:order"] == "fail"

    def test_freeze_commit_holding_results_fails(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        _git(root, "init", "-q")
        exp = root / "experiments" / EXP_ID
        exp.mkdir(parents=True)
        (exp / "claim.md").write_text(CLAIM.format(id=EXP_ID), encoding="utf-8")
        (exp / "decision.md").write_text(DECISION, encoding="utf-8")
        _commit(root, f"protocol({EXP_ID}): freeze with results", "experiments")
        statuses = _statuses(check_frozen(exp, None))
        assert statuses["frozen:clean"] == "fail"

    def test_manifest_naming_other_commit_fails(self, tmp_path):
        exp, labels, labels_sha = _setup(tmp_path)
        (exp / "manifest.md").write_text(_manifest("deadbeef" * 5, labels_sha), encoding="utf-8")
        statuses = _statuses(check_frozen(exp, labels))
        assert statuses["frozen:record"] == "fail"


class TestFrozenOnlyCli:
    def test_valid_freeze_exits_zero(self, tmp_path, monkeypatch, capsys):
        exp, labels, _ = _setup(tmp_path)
        argv = ["validate_experiment", str(exp), "--frozen-only", "--labels", str(labels)]
        monkeypatch.setattr(sys, "argv", argv)
        assert validate_experiment.main() == 0
        assert "frozen" in capsys.readouterr().out

    def test_protocol_only_pr_without_results_exits_zero(self, tmp_path, monkeypatch):
        # WHY: no decision.md exists yet, so the artifact tier would fail; --frozen-only must not.
        root = tmp_path / "repo"
        root.mkdir()
        _git(root, "init", "-q")
        exp = root / "experiments" / EXP_ID
        exp.mkdir(parents=True)
        (exp / "claim.md").write_text(CLAIM.format(id=EXP_ID), encoding="utf-8")
        _commit(root, f"protocol({EXP_ID}): freeze thresholds and holdout", "experiments")
        monkeypatch.setattr(sys, "argv", ["validate_experiment", str(exp), "--frozen-only"])
        assert validate_experiment.main() == 0

    def test_threshold_changed_exits_one(self, tmp_path, monkeypatch):
        exp, labels, _ = _setup(tmp_path)
        (exp / "decision.md").write_text(DECISION.replace(">= 0.80", ">= 0.70"), encoding="utf-8")
        argv = ["validate_experiment", str(exp), "--frozen-only", "--labels", str(labels)]
        monkeypatch.setattr(sys, "argv", argv)
        assert validate_experiment.main() == 1
