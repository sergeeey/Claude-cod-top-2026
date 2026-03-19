"""Тесты для checkpoint_guard.py.

ПОЧЕМУ: checkpoint_guard предупреждает перед рискованными операциями (rebase, rm -rf,
DROP TABLE и т.д.). Тесты мокируют stdin и файловую систему — без реальных git-вызовов.
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Вспомогательная функция для мокирования stdin с JSON-данными."""
    return io.StringIO(json.dumps(data))


def make_bash_input(command: str) -> dict:
    """Создать типичные данные хука PostToolUse для Bash-команды."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": ""},
    }


class TestCheckpointGuardMain:
    """Тесты main() через мокирование stdin и файловой системы."""

    def test_skips_non_risky_command(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Команда 'ls' не является рискованной — хук молчит."""
        data = make_bash_input("ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import checkpoint_guard

        checkpoint_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: ранний return при is_risky=False — нет никакого вывода
        assert captured.out == ""
        assert captured.err == ""

    def test_warns_on_git_rebase(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """git rebase — рискованная команда, при отсутствии checkpoints выдаёт предупреждение."""
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: мокируем find_checkpoints_dir чтобы вернуть путь,
        # а latest_checkpoint_age — None (нет checkpoint-файлов).
        mock_dir = MagicMock()
        mock_dir.__str__ = lambda self: "/fake/.claude/checkpoints"

        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=None),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert "checkpoint" in captured.out.lower()
        assert "git rebase main" in captured.out

    def test_warns_on_rm_rf(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """rm -rf — рискованная команда, предупреждение при отсутствии свежих checkpoints."""
        data = make_bash_input("rm -rf dir")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        mock_dir = MagicMock()

        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=None),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert "checkpoint" in captured.out.lower()

    def test_allows_with_recent_checkpoint(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Свежий checkpoint (<10 мин) — хук молчит, операция разрешена."""
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        mock_dir = MagicMock()

        # ПОЧЕМУ: age=5 минут < порог 60 минут → хук не выдаёт предупреждение
        with (
            patch("checkpoint_guard.find_checkpoints_dir", return_value=mock_dir),
            patch("checkpoint_guard.latest_checkpoint_age", return_value=5.0),
        ):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_skips_when_no_checkpoints_dir(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Если find_checkpoints_dir возвращает None — хук молчит."""
        data = make_bash_input("git rebase main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: отсутствие .claude/checkpoints/ — значит проект не настроен,
        # хук не должен мешать работе
        with patch("checkpoint_guard.find_checkpoints_dir", return_value=None):
            import checkpoint_guard

            checkpoint_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
