"""Unit tests for hooks/pre_compact.py."""

from __future__ import annotations

import os

import pre_compact


class TestFindActiveContext:
    def test_find_active_context_found(self, tmp_path, monkeypatch):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text("x", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        assert pre_compact.find_active_context() == ctx

    def test_find_active_context_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert pre_compact.find_active_context() is None


class TestPreCompactMain:
    def test_updates_timestamp_line_and_writes_log(self, tmp_path, monkeypatch, capsys):
        ctx = tmp_path / ".claude" / "memory" / "activeContext.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text("## Updated: 2000-01-01 00:00\nother\n", encoding="utf-8")

        # Redirect "~/.claude/logs" into tmp.
        logs_dir = tmp_path / ".claude" / "logs"

        def fake_expanduser(path: str) -> str:
            if path == "~/.claude/logs":
                return str(logs_dir)
            return os.path.expanduser(path)

        monkeypatch.setattr(pre_compact.os.path, "expanduser", fake_expanduser)
        monkeypatch.chdir(tmp_path)

        pre_compact.main()

        updated = ctx.read_text(encoding="utf-8")
        assert "(pre-compact)" in updated
        assert updated.startswith("## Updated:")

        log_path = logs_dir / "sessions.log"
        assert log_path.exists()
        assert "COMPACT" in log_path.read_text(encoding="utf-8")

        # Also prints a user-visible line.
        assert "Updated" in capsys.readouterr().out

    def test_no_active_context_still_logs(self, tmp_path, monkeypatch, capsys):
        logs_dir = tmp_path / ".claude" / "logs"

        monkeypatch.setattr(
            pre_compact.os.path, "expanduser", lambda p: str(logs_dir) if p == "~/.claude/logs" else p
        )
        monkeypatch.chdir(tmp_path)

        pre_compact.main()

        assert (logs_dir / "sessions.log").exists()
        assert "No project activeContext.md found" in capsys.readouterr().out

