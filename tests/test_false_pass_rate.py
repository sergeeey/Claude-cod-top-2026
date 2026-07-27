"""Tests for scripts/false_pass_rate.py against a real temporary git repository.

Control: a PASS verdict on a commit that NO later fix touches, past its observation
window, is CLEAN.
Mutation: a PASS verdict on a commit whose files a later "fix:" commit touches within the
window IS caught as SUSPECTED_FALSE_PASS (adversarially proven -- the whole point).
Regression (external review, 2026-07-21): a verdict younger than its own observation window
must be PENDING, not silently counted as a confirmed clean pass; the window must be anchored
to the verdict's own `ts`, not to datetime.now(), so an old verdict's genuinely-fast fix is
not excluded just because a lot of wall-clock time has passed since today.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import false_pass_rate  # noqa: E402


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def _commit(
    repo: Path, filename: str, content: str, message: str, when: datetime | None = None
) -> tuple[str, str]:
    """Create a commit, optionally backdated. Returns (sha, iso_committer_date)."""
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", filename)
    env = None
    if when is not None:
        iso = when.isoformat()
        env = {**os.environ, "GIT_AUTHOR_DATE": iso, "GIT_COMMITTER_DATE": iso}
    _git(repo, "commit", "-m", message, env=env)
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%H%x1f%aI"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    sha, iso_date = result.stdout.split("\x1f")
    return sha, iso_date


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


NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- PENDING (new)
def test_fresh_verdict_with_no_fix_yet_is_pending_not_clean():
    """Core regression: a verdict from a moment ago, still inside its observation window,
    must NOT be silently counted as a confirmed clean pass just because no fix has
    appeared -- there hasn't been time for one to appear yet."""
    record = {
        "verdict": "LGTM",
        "git_head": "deadbeef",
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": NOW.isoformat(),  # verdict issued "right now"
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "PENDING"
    assert evaluated["evaluated"] is False


def test_verdict_past_its_window_with_no_fix_is_clean(temp_repo):
    old_ts = NOW - timedelta(days=31)
    sha, iso_date = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py", when=old_ts)
    record = {
        "verdict": "LGTM",
        "git_head": sha,
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": old_ts.isoformat(),
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "CLEAN"
    assert evaluated["evaluated"] is True
    assert evaluated["suspected_false_pass"] is False


# --------------------------------------------------------------------------- window anchoring (new)
def test_window_is_anchored_to_verdict_ts_not_now(temp_repo):
    """Regression for the exact bug the review named: an OLD verdict (90 days ago) with a
    FAST fix (5 days later, so 85 days ago in absolute terms) must still be caught -- a
    now()-anchored 30-day cutoff would have excluded it purely because today is far away."""
    verdict_ts = NOW - timedelta(days=90)
    sha, _ = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py", when=verdict_ts)
    fix_ts = verdict_ts + timedelta(days=5)
    _commit(temp_repo, "a.py", "x = 2\n", "fix: correct a.py", when=fix_ts)

    record = {
        "verdict": "LGTM",
        "git_head": sha,
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": verdict_ts.isoformat(),
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "SUSPECTED_FALSE_PASS"
    assert evaluated["suspected_false_pass"] is True


def test_fix_outside_the_verdicts_own_window_is_not_caught(temp_repo):
    """A fix 45 days after an old verdict, with a 30-day window, must NOT count -- it's
    outside the verdict's OWN window even though it's still "old" relative to today."""
    verdict_ts = NOW - timedelta(days=90)
    sha, _ = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py", when=verdict_ts)
    fix_ts = verdict_ts + timedelta(days=45)
    _commit(temp_repo, "a.py", "x = 2\n", "fix: correct a.py", when=fix_ts)

    record = {
        "verdict": "LGTM",
        "git_head": sha,
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": verdict_ts.isoformat(),
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "CLEAN"


# --------------------------------------------------------------------------- control / mutation
def test_pass_followed_by_matching_fix_commit_is_suspected_false_pass(temp_repo):
    verdict_ts = NOW - timedelta(days=10)
    sha, _ = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py", when=verdict_ts)
    _commit(
        temp_repo,
        "a.py",
        "x = 2\n",
        "fix: correct off-by-one in a.py",
        when=verdict_ts + timedelta(days=1),
    )
    record = {
        "verdict": "LGTM",
        "git_head": sha,
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": verdict_ts.isoformat(),
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "SUSPECTED_FALSE_PASS"
    assert evaluated["matched_subject"].startswith("fix:")


def test_fix_commit_touching_different_file_does_not_false_positive(temp_repo):
    verdict_ts = NOW - timedelta(days=40)
    sha, _ = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py", when=verdict_ts)
    _commit(
        temp_repo,
        "b.py",
        "y = 1\n",
        "fix: unrelated bug in b.py",
        when=verdict_ts + timedelta(days=1),
    )
    record = {
        "verdict": "LGTM",
        "git_head": sha,
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": verdict_ts.isoformat(),
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "CLEAN"


def test_non_fix_commit_touching_same_file_does_not_false_positive(temp_repo):
    verdict_ts = NOW - timedelta(days=40)
    sha, _ = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py", when=verdict_ts)
    _commit(
        temp_repo,
        "a.py",
        "x = 1\ny = 2\n",
        "feat: extend a.py with y",
        when=verdict_ts + timedelta(days=1),
    )
    record = {
        "verdict": "LGTM",
        "git_head": sha,
        "files": ["a.py"],
        "agent": "reviewer",
        "ts": verdict_ts.isoformat(),
    }
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "CLEAN"


# --------------------------------------------------------------------------- rate aggregation
def test_measured_rate_once_enough_completed_records(temp_repo, tmp_path):
    """5 PASS records, all past their window: 2 genuinely followed by a matching fix, 3
    clean. Rate must be exactly 2/5, status MEASURED."""
    records = []
    verdict_ts = NOW - timedelta(days=40)
    for i in range(5):
        sha, _ = _commit(temp_repo, f"f{i}.py", "x = 1\n", f"feat: add f{i}.py", when=verdict_ts)
        records.append(
            {
                "verdict": "LGTM",
                "git_head": sha,
                "files": [f"f{i}.py"],
                "agent": "reviewer",
                "ts": verdict_ts.isoformat(),
            }
        )
        if i < 2:
            _commit(
                temp_repo,
                f"f{i}.py",
                "x = 2\n",
                f"fix: bug in f{i}.py",
                when=verdict_ts + timedelta(days=1),
            )

    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(log_path, records)
    result = false_pass_rate.compute(log_path=log_path, now=NOW)

    assert result["status"] == "MEASURED"
    assert result["evaluable_records"] == 5
    assert result["pending_records"] == 0
    assert result["suspected_false_passes"] == 2
    assert result["suspected_false_pass_rate"] == pytest.approx(0.4)


def test_pending_records_excluded_from_denominator(tmp_path):
    """5 fresh PASS records (still pending) + no completed ones -> INSUFFICIENT_DATA, not
    a rate computed only over an empty completed set that would misleadingly show 0.0%."""
    records = [
        {
            "verdict": "LGTM",
            "git_head": "abc123",
            "files": ["x.py"],
            "agent": "reviewer",
            "ts": NOW.isoformat(),
        }
        for _ in range(5)
    ]
    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(log_path, records)
    result = false_pass_rate.compute(log_path=log_path, now=NOW)

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["pending_records"] == 5
    assert result["evaluable_records"] == 0
    assert result["suspected_false_pass_rate"] is None


def test_missing_git_head_is_unevaluable(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    _write_log(
        log_path,
        [{"verdict": "PASS", "git_head": None, "files": [], "agent": "security-guard"}],
    )
    result = false_pass_rate.compute(log_path=log_path, now=NOW)
    assert result["evaluable_records"] == 0
    assert result["pending_records"] == 0
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
    result = false_pass_rate.compute(log_path=log_path, now=NOW)
    assert result["pass_class_records"] == 0


def test_empty_log_reports_insufficient_data_not_zero(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    result = false_pass_rate.compute(log_path=log_path, now=NOW)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["suspected_false_pass_rate"] is None


def test_corrupt_lines_are_skipped_not_fatal(tmp_path):
    log_path = tmp_path / "verdict_log.jsonl"
    log_path.write_text(
        '{"verdict": "LGTM", "git_head": null, "files": []}\nnot valid json\n\n',
        encoding="utf-8",
    )
    records = false_pass_rate.load_records(log_path)
    assert len(records) == 1


def test_legacy_record_without_ts_falls_back_to_unbounded_window(temp_repo):
    """Records predating the `ts` field (older log lines) degrade to the pre-fix
    behavior: no PENDING possible (can't know if a window elapsed), immediately
    evaluable against all reachable commits with no upper date bound."""
    sha, _ = _commit(temp_repo, "a.py", "x = 1\n", "feat: add a.py")
    _commit(temp_repo, "a.py", "x = 2\n", "fix: correct a.py")
    record = {"verdict": "LGTM", "git_head": sha, "files": ["a.py"], "agent": "reviewer"}
    evaluated = false_pass_rate.evaluate_record(record, window_days=30, now=NOW)
    assert evaluated["status"] == "SUSPECTED_FALSE_PASS"


def test_cli_json_mode_runs(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(false_pass_rate, "LOG_PATH", tmp_path / "no_such_file.jsonl")
    rc = false_pass_rate.main(["--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "INSUFFICIENT_DATA"
