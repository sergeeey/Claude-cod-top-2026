"""Тесты для memory_guard.py.

ПОЧЕМУ: memory_guard напоминает обновить activeContext.md после git commit.
Тесты мокируют stdin, файловую систему и время — без реальных git-операций.
"""

import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Вспомогательная функция для мокирования stdin с JSON-данными."""
    return io.StringIO(json.dumps(data))


def make_commit_input(command: str = "git commit -m 'feat: x'", response_stdout: str = "") -> dict:
    """Создать типичные данные хука PostToolUse для git commit."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": response_stdout},
    }


class TestMemoryGuardMain:
    """Тесты main() через мокирование stdin и файловой системы."""

    def test_skips_non_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Команда 'ls' — не git commit, хук молчит."""
        data = make_commit_input(command="ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import memory_guard

        memory_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: ранний return если "git commit" не в команде
        assert captured.out == ""
        assert captured.err == ""

    def test_skips_failed_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Провалившийся коммит ('nothing to commit') — хук молчит."""
        data = make_commit_input(response_stdout="nothing to commit, working tree clean")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import memory_guard

        memory_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: is_failed_commit() возвращает True → ранний return
        assert captured.out == ""

    def test_warns_when_no_active_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Успешный коммит без activeContext.md — предупреждение о создании файла."""
        data = make_commit_input(response_stdout="[feature/x abc1234] feat: done")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: find_project_memory() = None означает, что проект не имеет
        # .claude/memory/activeContext.md — хук напоминает его создать
        with patch("memory_guard.find_project_memory", return_value=None):
            import memory_guard

            memory_guard.main()

        captured = capsys.readouterr()
        assert "activeContext" in captured.out

    def test_warns_on_stale_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """activeContext.md старше 5 минут после коммита — предупреждение UPDATE REQUIRED."""
        data = make_commit_input(response_stdout="[feature/x abc1234] feat: done")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: создаём mock Path с st_mtime = 10 минут назад
        mock_path = MagicMock(spec=Path)
        mock_stat = MagicMock()
        mock_stat.st_mtime = time.time() - 600  # 10 минут назад
        mock_path.stat.return_value = mock_stat

        with patch("memory_guard.find_project_memory", return_value=mock_path):
            import memory_guard

            memory_guard.main()

        captured = capsys.readouterr()
        assert "UPDATE REQUIRED" in captured.out

    def test_silent_on_fresh_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """activeContext.md обновлён 2 минуты назад — хук молчит."""
        data = make_commit_input(response_stdout="[feature/x abc1234] feat: done")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: age = 2 мин < порог 5 мин → хук не выдаёт предупреждение
        mock_path = MagicMock(spec=Path)
        mock_stat = MagicMock()
        mock_stat.st_mtime = time.time() - 120  # 2 минуты назад
        mock_path.stat.return_value = mock_stat

        with patch("memory_guard.find_project_memory", return_value=mock_path):
            import memory_guard

            memory_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""
