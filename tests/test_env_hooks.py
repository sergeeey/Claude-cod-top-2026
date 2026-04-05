"""Tests for env-related hooks: direnv_loader, env_reload."""

import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def _stdin(data: dict):
    return io.StringIO(json.dumps(data))


# ── direnv_loader ─────────────────────────────────────────────────────────────


class TestDirenvLoader:
    def test_no_cwd_silent(self, monkeypatch, tmp_path):
        import direnv_loader

        monkeypatch.setattr("sys.stdin", _stdin({}))
        direnv_loader.main()  # no cwd → early return, no crash

    def test_unsafe_path_ignored(self, monkeypatch, tmp_path):
        import direnv_loader

        monkeypatch.setattr("sys.stdin", _stdin({"cwd": "/etc/passwd/../../../root"}))
        with patch("direnv_loader.is_safe_path", return_value=False):
            direnv_loader.main()  # unsafe → early return

    def test_no_env_file_var_silent(self, monkeypatch, tmp_path):
        import direnv_loader

        monkeypatch.setattr("sys.stdin", _stdin({"cwd": str(tmp_path)}))
        monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
        with patch("direnv_loader.is_safe_path", return_value=True):
            direnv_loader.main()  # no CLAUDE_ENV_FILE → early return

    def test_loads_env_file(self, monkeypatch, tmp_path):
        import direnv_loader

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        env_file = project_dir / ".env"
        env_file.write_text("MY_KEY=my_value\nANOTHER=123\n")

        output_file = tmp_path / "claude_env"
        output_file.write_text("")

        monkeypatch.setattr("sys.stdin", _stdin({"cwd": str(project_dir)}))
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(output_file))
        with patch("direnv_loader.is_safe_path", return_value=True):
            direnv_loader.main()

    def test_no_env_in_dir_silent(self, monkeypatch, tmp_path):
        import direnv_loader

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output_file = tmp_path / "claude_env"
        output_file.write_text("")

        monkeypatch.setattr("sys.stdin", _stdin({"cwd": str(empty_dir)}))
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(output_file))
        with patch("direnv_loader.is_safe_path", return_value=True):
            direnv_loader.main()  # no .env in dir → nothing written, no crash

    def test_invalid_json_no_crash(self, monkeypatch, tmp_path):
        import direnv_loader

        monkeypatch.setattr("sys.stdin", io.StringIO("bad json"))
        direnv_loader.main()

    def test_new_cwd_key(self, monkeypatch, tmp_path):
        """Accepts 'new_cwd' as alternative to 'cwd'."""
        import direnv_loader

        monkeypatch.setattr("sys.stdin", _stdin({"new_cwd": str(tmp_path)}))
        monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
        with patch("direnv_loader.is_safe_path", return_value=True):
            direnv_loader.main()


# ── env_reload ────────────────────────────────────────────────────────────────


class TestEnvReload:
    def test_no_file_path_silent(self, monkeypatch, tmp_path):
        import env_reload

        monkeypatch.setattr("sys.stdin", _stdin({}))
        env_reload.main()

    def test_non_env_file_ignored(self, monkeypatch, tmp_path):
        import env_reload

        monkeypatch.setattr("sys.stdin", _stdin({"file_path": "/project/main.py"}))
        env_reload.main()  # .py file → not an env file → early return

    def test_env_local_triggers(self, monkeypatch, tmp_path):
        import env_reload

        env_file = tmp_path / ".env.local"
        env_file.write_text("KEY=val\n")
        output_file = tmp_path / "claude_env"
        output_file.write_text("")

        monkeypatch.setattr("sys.stdin", _stdin({"file_path": str(env_file)}))
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(output_file))
        with patch("env_reload.is_safe_path", return_value=True):
            env_reload.main()

    def test_envrc_triggers(self, monkeypatch, tmp_path):
        import env_reload

        env_file = tmp_path / ".envrc"
        env_file.write_text("export FOO=bar\n")
        output_file = tmp_path / "claude_env"
        output_file.write_text("")

        monkeypatch.setattr("sys.stdin", _stdin({"file_path": str(env_file)}))
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(output_file))
        with patch("env_reload.is_safe_path", return_value=True):
            env_reload.main()

    def test_unsafe_path_ignored(self, monkeypatch, tmp_path):
        import env_reload

        monkeypatch.setattr("sys.stdin", _stdin({"file_path": "/etc/../root/.env"}))
        with patch("env_reload.is_safe_path", return_value=False):
            env_reload.main()

    def test_no_claude_env_file_var(self, monkeypatch, tmp_path):
        import env_reload

        env_file = tmp_path / ".env"
        env_file.write_text("K=V\n")
        monkeypatch.setattr("sys.stdin", _stdin({"file_path": str(env_file)}))
        monkeypatch.delenv("CLAUDE_ENV_FILE", raising=False)
        with patch("env_reload.is_safe_path", return_value=True):
            env_reload.main()  # no CLAUDE_ENV_FILE → early return

    def test_file_not_exist_silent(self, monkeypatch, tmp_path):
        import env_reload

        monkeypatch.setattr("sys.stdin", _stdin({"file_path": str(tmp_path / ".env")}))
        monkeypatch.setenv("CLAUDE_ENV_FILE", str(tmp_path / "out"))
        with patch("env_reload.is_safe_path", return_value=True):
            env_reload.main()  # file doesn't exist → early return

    def test_invalid_json_no_crash(self, monkeypatch):
        import env_reload

        monkeypatch.setattr("sys.stdin", io.StringIO("{{bad"))
        env_reload.main()
