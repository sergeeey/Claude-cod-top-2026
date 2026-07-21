"""Tests for scripts/false_pass_rate.py against a real temp git repository.

Control: a PASS verdict on a commit that NO later fix touches stays clean.
Mutation: a PASS verdict on a commit whose files a later "fix:" commit touches IS caught
(adversarially proven -- the whole point of this script is catching exactly this).
Bootstrap: fewer than MIN_RECORDS_FOR_RATE evaluable records reports INSUFFICIENT_DATA,
never a misleading 0.0%.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import false_pass_rate  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo: Path, filename: str, content: str, message: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-m", message)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    monkeypatch.setattr(false_pass_rate, "ROOT", repo)
    return repo


def _write_log(log_path: Path, records: list[dict]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# --------------------------------------------------------------------------- control (clean)
def test_pass_with_no_later_fix_is_not_a_false_pass(temp_repo, tmp_path):
    sha = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py")
    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(
        log_path,
        [{"verdict": "LGTM", "git_head": sha, "files": ["a.py"], "agent": "reviewer"}],
    )
    result = false_pass_rate.compute(log_path=log_path)
    assert result["status"] == "INSUFFICIENT_DATA"  # 1 record < MIN_RECORDS_FOR_RATE
    assert result["false_passes"] == 0


# --------------------------------------------------------------------------- mutation (caught)
def test_pass_followed_by_matching_fix_commit_is_a_false_pass(temp_repo, tmp_path):
    sha = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py")
    _commit(temp_repo, "a.py", "x = 2\n", "fix: correct off-by-one in a.py")

    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(
        log_path,
        [{"verdict": "LGTM", "git_head": sha, "files": ["a.py"], "agent": "reviewer"}],
    )
    evaluated = false_pass_rate.evaluate_record(
        {"verdict": "LGTM", "git_head": sha, "files": ["a.py"], "agent": "reviewer"},
        window_days=30,
    )
    assert evaluated["evaluated"] is True
    assert evaluated["false_pass"] is True
    assert evaluated["matched_subject"].startswith("fix:")


def test_fix_commit_touching_different_file_does_not_false_positive(temp_repo):
    sha = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py")
    _commit(temp_repo, "b.py", "y = 1\n", "fix: unrelated bug in b.py")

    evaluated = false_pass_rate.evaluate_record(
        {"verdict": "LGTM", "git_head": sha, "files": ["a.py"], "agent": "reviewer"},
        window_days=30,
    )
    assert evaluated["evaluated"] is True
    assert evaluated["false_pass"] is False


def test_non_fix_commit_touching_same_file_does_not_false_positive(temp_repo):
    sha = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py")
    _commit(temp_repo, "a.py", "x = 1\ny = 2\n", "feat: extend a.py with y")

    evaluated = false_pass_rate.evaluate_record(
        {"verdict": "LGTM", "git_head": sha, "files": ["a.py"], "agent": "reviewer"},
        window_days=30,
    )
    assert evaluated["evaluated"] is True
    assert evaluated["false_pass"] is False


# --------------------------------------------------------------------------- rate aggregation
def test_measured_rate_once_enough_records(temp_repo, tmp_path):
    """5 PASS records, 2 of which are genuinely followed by a matching fix -- rate must be
    exactly 2/5, and status must flip from INSUFFICIENT_DATA to MEASURED."""
    records = []
    for i in range(5):
        sha = _commit(temp_repo, f"f{i}.py", "x = 1\n", f"feat: add f{i}.py")
        records.append(
            {"verdict": "LGTM", "git_head": sha, "files": [f"f{i}.py"], "agent": "reviewer"}
        )
        if i < 2:  # first two get a matching fix; last three stay clean
            _commit(temp_repo, f"f{i}.py", "x = 2\n", f"fix: bug in f{i}.py")

    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(log_path, records)

    result = false_pass_rate.compute(log_path=log_path)
    assert result["status"] == "MEASURED"
    assert result["evaluable_records"] == 5
    assert result["false_passes"] == 2
    assert result["false_pass_rate"] == pytest.approx(0.4)


def test_missing_git_head_is_marked_unevaluable(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(
        log_path,
        [{"verdict": "PASS", "git_head": None, "files": [], "agent": "security-guard"}],
    )
    result = false_pass_rate.compute(log_path=log_path)
    assert result["evaluable_records"] == 0
    assert result["pass_class_records"] == 1


def test_fail_class_verdicts_are_excluded_from_pass_denominator(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(
        log_path,
        [
            {"verdict": "NEEDS_WORK", "git_head": "abc", "files": ["x.py"], "agent": "reviewer"},
            {"verdict": "BLOCK", "git_head": "def", "files": ["y.py"], "agent": "security-guard"},
        ],
    )
    result = false_pass_rate.compute(log_path=log_path)
    assert result["pass_class_records"] == 0


def test_empty_log_reports_insufficient_data_not_zero(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    result = false_pass_rate.compute(log_path=log_path)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["false_pass_rate"] is None


def test_corrupt_lines_are_skipped_not_fatal(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    log_path.write_text(
        '{"verdict": "LGTM", "git_head": null, "files": []}\nnot valid json\n\n',
        encoding="utf-8",
    )
    records = false_pass_rate.load_records(log_path)
    assert len(records) == 1


def test_cli_json_mode_runs(temp_repo, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(false_pass_rate, "LOG_PATH", tmp_path / "no_such_file.jsonl")
    rc = false_pass_rate.main(["--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "INSUFFICIENT_DATA"
