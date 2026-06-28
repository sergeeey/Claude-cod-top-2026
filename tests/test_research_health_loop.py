"""Tests for hooks/research_health_loop.py."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
import research_health_loop as rhl

# ── Timer helpers ─────────────────────────────────────────────────────────────


def test_is_due_no_state_file(tmp_path, monkeypatch):
    monkeypatch.setattr(rhl, "_LAST_HEALTH_FILE", tmp_path / "last.txt")
    assert rhl._is_due(date.today()) is True


def test_is_due_fresh_record(tmp_path, monkeypatch):
    state = tmp_path / "last.txt"
    state.write_text(date.today().isoformat())
    monkeypatch.setattr(rhl, "_LAST_HEALTH_FILE", state)
    assert rhl._is_due(date.today()) is False


def test_is_due_old_record(tmp_path, monkeypatch):
    state = tmp_path / "last.txt"
    old = date.today() - timedelta(days=8)
    state.write_text(old.isoformat())
    monkeypatch.setattr(rhl, "_LAST_HEALTH_FILE", state)
    assert rhl._is_due(date.today()) is True


def test_record_health_now_creates_file(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(rhl, "_STATE_DIR", state_dir)
    monkeypatch.setattr(rhl, "_LAST_HEALTH_FILE", state_dir / "last.txt")
    today = date(2026, 6, 28)
    rhl._record_health_now(today)
    assert (state_dir / "last.txt").read_text() == "2026-06-28"


# ── Zombie detection ──────────────────────────────────────────────────────────


def test_experiment_is_closed_with_reject(tmp_path):
    exp = tmp_path / "exp1"
    exp.mkdir()
    (exp / "decision.md").write_text("## verdict\nREJECT — claim falsified")
    assert rhl._experiment_is_closed(exp) is True


def test_experiment_is_closed_with_promote(tmp_path):
    exp = tmp_path / "exp1"
    exp.mkdir()
    (exp / "decision.md").write_text("## Verdict: PROMOTE")
    assert rhl._experiment_is_closed(exp) is True


def test_experiment_not_closed_empty_decision(tmp_path):
    exp = tmp_path / "exp1"
    exp.mkdir()
    (exp / "decision.md").write_text("## work in progress")
    assert rhl._experiment_is_closed(exp) is False


def test_experiment_not_closed_no_decision_file(tmp_path):
    exp = tmp_path / "exp1"
    exp.mkdir()
    assert rhl._experiment_is_closed(exp) is False


def test_find_zombies_skips_closed(tmp_path):
    root = tmp_path
    exp_dir = root / "experiments"
    exp_dir.mkdir()

    closed = exp_dir / "exp-closed"
    closed.mkdir()
    (closed / "decision.md").write_text("REJECT")

    open_exp = exp_dir / "20240101-old-thing"
    open_exp.mkdir()
    (open_exp / "claim.md").write_text("some open claim")

    today = date(2026, 6, 28)
    # File was modified at dir creation — might be recent; let's fake it
    # by using a date far in future so mtime check doesn't fire
    # Instead, manually set mtime to >30 days ago
    import os
    import time

    old_mtime = time.time() - (31 * 86400)
    os.utime(open_exp / "claim.md", (old_mtime, old_mtime))

    zombies = rhl._find_zombies(root, today)
    assert len(zombies) == 1
    assert "20240101-old-thing" in zombies[0]


def test_find_zombies_skips_template(tmp_path):
    root = tmp_path
    exp_dir = root / "experiments"
    exp_dir.mkdir()
    tmpl = exp_dir / "_template"
    tmpl.mkdir()
    (tmpl / "claim.md").write_text("template")

    today = date(2026, 6, 28)
    zombies = rhl._find_zombies(root, today)
    assert zombies == []


def test_find_zombies_no_experiments_dir(tmp_path):
    assert rhl._find_zombies(tmp_path, date.today()) == []


def test_last_modified_days_skips_per_file_oserror(tmp_path, monkeypatch):
    """A stat() OSError on one file is skipped; scan uses remaining files."""
    import os
    import time
    from unittest.mock import MagicMock

    exp = tmp_path / "exp"
    exp.mkdir()

    good = exp / "good.md"
    good.write_text("valid file")
    old_mtime = time.time() - (31 * 86400)
    os.utime(good, (old_mtime, old_mtime))

    # Simulate a broken-symlink-like path that raises OSError on stat()
    bad = MagicMock(spec=Path)
    bad.is_file.return_value = True
    bad.stat.side_effect = OSError("mocked: permission denied")

    def mock_rglob(self, pattern):
        if self == exp:
            return iter([good, bad])
        return iter([])

    monkeypatch.setattr(Path, "rglob", mock_rglob)

    today = date(2026, 6, 28)
    days = rhl._last_modified_days(exp, today)
    # Before fix: would return 0.0 (scan aborted by bad file's OSError)
    # After fix: bad file is skipped, good file's mtime (~31d) is used
    assert days >= 30


# ── Pearl registry parsing ────────────────────────────────────────────────────


def test_parse_pearl_registry_basic(tmp_path):
    registry = tmp_path / "INDEX.md"
    registry.write_text(
        "| date | source | observation | prediction | trigger | next_check | status |\n"
        "|------|--------|-------------|------------|---------|------------|--------|\n"
        "| 2026-06-01 | exp-g22 | NCG SU(3)×U(1)_B-L | SUB-SM check | G99 | 2026-07-01 | pending |\n"
    )
    entries = rhl._parse_pearl_registry(registry)
    assert len(entries) == 1
    assert entries[0]["next_check"] == "2026-07-01"
    assert entries[0]["status"] == "pending"


def test_check_pearls_overdue(tmp_path):
    registry = tmp_path / "pearl_registry"
    registry.mkdir()
    (registry / "INDEX.md").write_text(
        "| date | source | observation | prediction | trigger | next_check | status |\n"
        "|------|--------|-------------|------------|---------|------------|--------|\n"
        "| 2026-01-01 | g10 | old pearl | pred | trig | 2026-03-01 | pending |\n"
    )
    today = date(2026, 6, 28)
    overdue, unanchored = rhl._check_pearls(tmp_path, today)
    assert len(overdue) == 1
    assert "old pearl" in overdue[0]
    assert unanchored == []


def test_check_pearls_unanchored(tmp_path):
    registry = tmp_path / "pearl_registry"
    registry.mkdir()
    (registry / "INDEX.md").write_text(
        "| date | source | observation | prediction | trigger | next_check | status |\n"
        "|------|--------|-------------|------------|---------|------------|--------|\n"
        "| 2026-06-01 | g20 | unanchored observation | pred | trig | TBD | pending |\n"
    )
    today = date(2026, 6, 28)
    overdue, unanchored = rhl._check_pearls(tmp_path, today)
    assert overdue == []
    assert len(unanchored) == 1


def test_check_pearls_future_date_not_overdue(tmp_path):
    registry = tmp_path / "pearl_registry"
    registry.mkdir()
    (registry / "INDEX.md").write_text(
        "| date | source | observation | prediction | trigger | next_check | status |\n"
        "|------|--------|-------------|------------|---------|------------|--------|\n"
        "| 2026-06-01 | g30 | future pearl | pred | trig | 2027-01-01 | pending |\n"
    )
    today = date(2026, 6, 28)
    overdue, unanchored = rhl._check_pearls(tmp_path, today)
    assert overdue == []
    assert unanchored == []


def test_check_pearls_closed_skipped(tmp_path):
    registry = tmp_path / "pearl_registry"
    registry.mkdir()
    (registry / "INDEX.md").write_text(
        "| date | source | observation | prediction | trigger | next_check | status |\n"
        "|------|--------|-------------|------------|---------|------------|--------|\n"
        "| 2026-01-01 | g5 | done pearl | pred | trig | 2026-01-01 | archived |\n"
    )
    today = date(2026, 6, 28)
    overdue, unanchored = rhl._check_pearls(tmp_path, today)
    assert overdue == []
    assert unanchored == []


def test_check_pearls_quarter_format_overdue(tmp_path):
    registry = tmp_path / "pearl_registry"
    registry.mkdir()
    (registry / "INDEX.md").write_text(
        "| date | source | observation | prediction | trigger | next_check | status |\n"
        "|------|--------|-------------|------------|---------|------------|--------|\n"
        "| 2026-01-01 | g11 | quarter pearl | pred | trig | 2026-Q1 | pending |\n"
    )
    today = date(2026, 6, 28)
    overdue, unanchored = rhl._check_pearls(tmp_path, today)
    assert len(overdue) == 1
    assert "Q1 2026" in overdue[0]


def test_check_pearls_no_registry(tmp_path):
    overdue, unanchored = rhl._check_pearls(tmp_path, date.today())
    assert overdue == []
    assert unanchored == []


# ── Message formatting ────────────────────────────────────────────────────────


def test_format_message_all_healthy():
    msg = rhl._format_message([], [], [], "my-project")
    assert msg is None


def test_format_message_with_zombies():
    msg = rhl._format_message(["exp-old (35d idle)"], [], [], "my-project")
    assert msg is not None
    assert "ZOMBIE" in msg
    assert "exp-old" in msg


def test_format_message_with_overdue_pearls():
    msg = rhl._format_message([], ["pearl A (due 2026-03-01)"], [], "my-project")
    assert msg is not None
    assert "OVERDUE" in msg
    assert "pearl A" in msg


def test_format_message_with_unanchored():
    msg = rhl._format_message([], [], ["unanchored obs"], "my-project")
    assert msg is not None
    assert "UNANCHORED" in msg
    assert "unanchored obs" in msg


def test_format_message_caps_at_5_zombies():
    zombies = [f"exp-{i} (99d idle)" for i in range(10)]
    msg = rhl._format_message(zombies, [], [], "my-project")
    assert msg is not None
    assert "and 5 more" in msg


# ── Integration: main skips when not due ─────────────────────────────────────


def test_main_skips_when_not_due(tmp_path, monkeypatch, capsys):
    state = tmp_path / "last.txt"
    state.write_text(date.today().isoformat())
    monkeypatch.setattr(rhl, "_LAST_HEALTH_FILE", state)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("{}"))

    with pytest.raises(SystemExit) as exc:
        rhl.main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == ""


def test_main_emits_when_due(tmp_path, monkeypatch, capsys):
    """When review is due and zombies exist, main() emits JSON to stdout."""
    # Timer: due (no state file)
    monkeypatch.setattr(rhl, "_LAST_HEALTH_FILE", tmp_path / "last.txt")
    monkeypatch.setattr(rhl, "_STATE_DIR", tmp_path)

    # Set up project root
    project_root = tmp_path / "myproject"
    project_root.mkdir()
    (project_root / "CLAUDE.md").write_text("# project")

    # Create zombie experiment
    import os
    import time

    exp_dir = project_root / "experiments" / "20240101-zombie"
    exp_dir.mkdir(parents=True)
    claim = exp_dir / "claim.md"
    claim.write_text("open claim")
    old_mtime = time.time() - (31 * 86400)
    os.utime(claim, (old_mtime, old_mtime))

    # Point CWD to project root so find_file_upward finds CLAUDE.md
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("{}"))

    rhl.main()

    captured = capsys.readouterr()
    assert captured.out.strip()
    payload = json.loads(captured.out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "ZOMBIE" in ctx
    assert "20240101-zombie" in ctx
