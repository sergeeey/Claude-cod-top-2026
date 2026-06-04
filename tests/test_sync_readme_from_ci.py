"""Tests for sync_readme_from_ci.py — README badge ↔ CI sync.

WHY: this script removes a [×3] recurring mistake (badge from local count
instead of CI). The pure logic — reading current badge values and rewriting
them — must be correct; the gh-subprocess parts are mocked.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import sync_readme_from_ci as sync  # noqa: E402

# ── _current_badge ────────────────────────────────────────────────────────────


class TestCurrentBadge:
    def test_reads_both(self):
        text = "Tests-1352-green Coverage-75%25"
        tests, cov = sync._current_badge(text)
        assert tests == 1352
        assert cov == 75

    def test_none_when_absent(self):
        tests, cov = sync._current_badge("no badges here")
        assert tests is None
        assert cov is None


# ── _ci_metrics regex ─────────────────────────────────────────────────────────


class TestCiLineRegex:
    def test_parses_actual_line(self):
        m = sync._CI_LINE.search("2026-06-04 Actual: 1352 tests, 75% coverage")
        assert m is not None
        assert int(m.group(1)) == 1352
        assert int(m.group(2)) == 75

    def test_no_match_on_unrelated(self):
        assert sync._CI_LINE.search("README: 1356 tests") is None  # 'README:' not 'Actual:'


# ── _rewrite ──────────────────────────────────────────────────────────────────


class TestRewrite:
    def test_updates_test_count_everywhere(self):
        text = "badge Tests-1352 ... 1352 tests · footer 1352"
        out = sync._rewrite(text, 1352, 1356, 75, 75)
        assert "1352" not in out
        assert out.count("1356") == 3

    def test_updates_coverage_badge_and_text(self):
        text = "Coverage-75%25 ... backed by 75% coverage"
        out = sync._rewrite(text, 0, 0, 75, 80)
        assert "Coverage-80%25" in out
        assert "80% coverage" in out
        assert "75%" not in out

    def test_noop_when_equal(self):
        text = "Tests-1352 Coverage-75%25"
        out = sync._rewrite(text, 1352, 1352, 75, 75)
        assert out == text


# ── main() with mocked CI ─────────────────────────────────────────────────────


class TestMain:
    def test_in_sync_returns_0(self, tmp_path, monkeypatch, capsys):
        readme = tmp_path / "README.md"
        readme.write_text("Tests-1352 Coverage-75%25", encoding="utf-8")
        monkeypatch.setattr(sync, "README", readme)
        monkeypatch.setattr(sync, "_latest_main_run_id", lambda: "123")
        monkeypatch.setattr(sync, "_ci_metrics", lambda _rid: (1352, 75))
        monkeypatch.setattr("sys.argv", ["sync"])
        rc = sync.main()
        assert rc == 0
        assert "already matches" in capsys.readouterr().out

    def test_check_reports_drift_exit_1(self, tmp_path, monkeypatch, capsys):
        readme = tmp_path / "README.md"
        readme.write_text("Tests-1356 Coverage-75%25", encoding="utf-8")
        monkeypatch.setattr(sync, "README", readme)
        monkeypatch.setattr(sync, "_latest_main_run_id", lambda: "123")
        monkeypatch.setattr(sync, "_ci_metrics", lambda _rid: (1352, 75))
        monkeypatch.setattr("sys.argv", ["sync", "--check"])
        rc = sync.main()
        assert rc == 1
        assert "DRIFT" in capsys.readouterr().out
        # --check must NOT modify the file
        assert "1356" in readme.read_text(encoding="utf-8")

    def test_updates_file_when_drift(self, tmp_path, monkeypatch, capsys):
        readme = tmp_path / "README.md"
        readme.write_text("Tests-1356 ... 1356 tests Coverage-75%25", encoding="utf-8")
        monkeypatch.setattr(sync, "README", readme)
        monkeypatch.setattr(sync, "_latest_main_run_id", lambda: "123")
        monkeypatch.setattr(sync, "_ci_metrics", lambda _rid: (1352, 75))
        monkeypatch.setattr("sys.argv", ["sync"])
        rc = sync.main()
        assert rc == 0
        content = readme.read_text(encoding="utf-8")
        assert "1356" not in content
        assert "1352" in content

    def test_failopen_no_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sync, "_latest_main_run_id", lambda: None)
        monkeypatch.setattr("sys.argv", ["sync"])
        # No CI run → fail-open, return 0, don't crash
        assert sync.main() == 0

    def test_failopen_no_metrics_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sync, "_latest_main_run_id", lambda: "123")
        monkeypatch.setattr(sync, "_ci_metrics", lambda _rid: None)
        monkeypatch.setattr("sys.argv", ["sync"])
        assert sync.main() == 0
