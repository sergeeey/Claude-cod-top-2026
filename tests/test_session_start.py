"""Тесты для hooks/session_start.py.

ПОЧЕМУ: session_start.py отвечает за вывод контекста проекта при старте сессии Claude.
0% coverage → критические пути (auto_update, scope fence, project memory) не проверены.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


class TestAutoUpdateConfigRepo:
    """Тесты auto_update_config_repo(): авто-обновление config repo через git pull."""

    def test_auto_update_no_marker(self, tmp_path: pytest.TempdirFactory) -> None:
        """Если marker-файл не существует — ранний return, subprocess не вызывается.

        ПОЧЕМУ: marker = ~/.claude/.claude-code-config-repo. Если файла нет —
        конфиг установлен без --link, обновлять нечего. subprocess не должен вызываться.
        """
        import session_start

        # ПОЧЕМУ: patch Path.home() чтобы marker указывал на несуществующий tmp_path
        fake_home = tmp_path  # в tmp_path нет .claude/.claude-code-config-repo

        with (
            patch("session_start.Path") as MockPath,
            patch("subprocess.run") as mock_run,
        ):
            # Симулируем Path.home() / ".claude" / CONFIG_REPO_MARKER → не существует
            mock_marker = MagicMock()
            mock_marker.exists.return_value = False
            MockPath.home.return_value = fake_home
            # Path(str) конструктор — нужен для Path(repo_path).is_dir()
            MockPath.side_effect = lambda *args, **kw: mock_marker if args == () else MagicMock()
            # Цепочка: Path.home() / ".claude" / marker → mock_marker
            fake_home_mock = MagicMock()
            fake_home_mock.__truediv__ = lambda self, other: (
                fake_home_mock if other == ".claude" else MagicMock()
            )
            MockPath.home.return_value = fake_home_mock
            claude_dir_mock = MagicMock()
            fake_home_mock.__truediv__ = MagicMock(return_value=claude_dir_mock)
            claude_dir_mock.__truediv__ = MagicMock(return_value=mock_marker)

            session_start.auto_update_config_repo()

        # ПОЧЕМУ: marker.exists() → False → функция делает ранний return
        mock_run.assert_not_called()

    def test_auto_update_no_marker_via_real_path(self, tmp_path: "pytest.TempdirFactory") -> None:
        """Альтернативный подход: patch Path.home() возвращает tmp_path без marker файла."""
        import session_start

        with (
            patch("session_start.Path.home", return_value=tmp_path),
            patch("subprocess.run") as mock_run,
        ):
            session_start.auto_update_config_repo()

        # tmp_path не содержит .claude/.claude-code-config-repo → early return
        mock_run.assert_not_called()


class TestPrintScopeFence:
    """Тесты print_scope_fence(): вывод статуса Scope Fence при старте сессии."""

    def test_print_scope_fence_no_fence(self, capsys: pytest.CaptureFixture) -> None:
        """find_scope_fence возвращает None → печатает 'No Scope Fence'.

        ПОЧЕМУ: нет .scope-fence.md и нет activeContext.md → пользователь
        не настроил фокус сессии, нужно информировать.
        """
        import session_start

        with patch("session_start.find_scope_fence", return_value=None):
            session_start.print_scope_fence()

        captured = capsys.readouterr()
        # ПОЧЕМУ: функция явно печатает "No Scope Fence found" при fence_source is None
        assert "No Scope Fence" in captured.out

    def test_print_scope_fence_with_goal(
        self, tmp_path: "pytest.TempdirFactory", capsys: pytest.CaptureFixture
    ) -> None:
        """fence файл содержит Goal: 'Build MVP' → печатает цель.

        ПОЧЕМУ: основной happy-path — пользователь установил Scope Fence,
        Claude должен увидеть цель в начале сессии.
        """
        import session_start

        fence_file = tmp_path / ".scope-fence.md"
        fence_file.write_text(
            "## Scope Fence\nGoal: Build MVP\nNOT NOW: refactoring\n",
            encoding="utf-8",
        )

        with patch("session_start.find_scope_fence", return_value=fence_file):
            session_start.print_scope_fence()

        captured = capsys.readouterr()
        # ПОЧЕМУ: parse_scope_fence вернёт {"goal": "Build MVP", "not_now": "refactoring"}
        assert "Build MVP" in captured.out
        assert "Scope Fence active" in captured.out

    def test_print_scope_fence_not_now_printed(
        self, tmp_path: "pytest.TempdirFactory", capsys: pytest.CaptureFixture
    ) -> None:
        """Если NOT NOW задан — печатается вместе с Goal."""
        import session_start

        fence_file = tmp_path / ".scope-fence.md"
        fence_file.write_text(
            "## Scope Fence\nGoal: Ship auth feature\nNOT NOW: dashboard redesign\n",
            encoding="utf-8",
        )

        with patch("session_start.find_scope_fence", return_value=fence_file):
            session_start.print_scope_fence()

        captured = capsys.readouterr()
        assert "Ship auth feature" in captured.out
        assert "NOT NOW" in captured.out
        assert "dashboard redesign" in captured.out


class TestMain:
    """Тесты main(): полный запуск session_start с моками всех зависимостей."""

    def test_main_no_project_memory(self, capsys: pytest.CaptureFixture) -> None:
        """find_project_claude_dir возвращает None → печатает fallback сообщение.

        ПОЧЕМУ: если проект не имеет .claude/memory/ — Claude не должен падать,
        а информировать что память не найдена и продолжать.
        """
        import session_start

        with (
            patch("session_start.auto_update_config_repo"),
            patch("session_start.find_project_claude_dir", return_value=None),
            patch("session_start.print_scope_fence"),
        ):
            session_start.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: строка в session_start.py: "No project .claude/memory/ found in path hierarchy."
        assert "No project" in captured.out
        assert ".claude/memory/" in captured.out

    def test_main_with_project_memory(
        self, tmp_path: "pytest.TempdirFactory", capsys: pytest.CaptureFixture
    ) -> None:
        """Если activeContext.md существует — его содержимое выводится в stdout."""
        import session_start

        mem_dir = tmp_path / ".claude" / "memory"
        mem_dir.mkdir(parents=True)
        active = mem_dir / "activeContext.md"
        active.write_text("# Active Context\nWorking on feature X\n", encoding="utf-8")

        with (
            patch("session_start.auto_update_config_repo"),
            patch("session_start.find_project_claude_dir", return_value=mem_dir),
            patch("session_start.print_scope_fence"),
        ):
            session_start.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: функция читает и выводит содержимое activeContext.md
        assert "Working on feature X" in captured.out
        assert "PROJECT ACTIVE CONTEXT" in captured.out
