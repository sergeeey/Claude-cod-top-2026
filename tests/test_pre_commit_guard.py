"""Тесты для pre_commit_guard.py.

ПОЧЕМУ: pre_commit_guard — security-критичный хук. Блокирует коммиты в main/master
и пуш в публичный репозиторий. Тесты гарантируют, что критические проверки работают
через мокирование stdin и run_git, без реальных git-операций.
"""

import io
import json
import os
import sys

# ПОЧЕМУ: hooks лежат на уровень выше tests/. insert(0) гарантирует приоритет
# перед site-packages при импорте.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Вспомогательная функция для мокирования stdin с JSON-данными."""
    return io.StringIO(json.dumps(data))


def make_bash_input(command: str) -> dict:
    """Создать типичные данные хука для Bash-команды."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class TestPreCommitGuardMain:
    """Тесты main() через мокирование stdin и run_git."""

    def test_skips_non_git_commit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Команда 'ls' — не git commit, хук должен выйти без вывода."""
        data = make_bash_input("ls -la")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        pre_commit_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: хук делает ранний return — никакого вывода на stdout/stderr
        assert captured.out == ""
        assert captured.err == ""

    def test_blocks_commit_to_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Коммит в main должен блокировать выполнение с exit(2)."""
        data = make_bash_input('git commit -m "feat: some change"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: mock run_git возвращает "main" для rev-parse --abbrev-ref HEAD
        with patch("pre_commit_guard.run_git", return_value="main"):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 2

    def test_blocks_commit_to_master(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Коммит в master должен блокировать выполнение с exit(2)."""
        data = make_bash_input('git commit -m "fix: hotfix"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with patch("pre_commit_guard.run_git", return_value="master"):
            import pre_commit_guard

            with pytest.raises(SystemExit) as exc_info:
                pre_commit_guard.main()

        assert exc_info.value.code == 2

    def test_allows_commit_to_feature(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Коммит в feature-ветку разрешён — хук не вызывает sys.exit(2)."""
        data = make_bash_input('git commit -m "feat: voice input"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        # ПОЧЕМУ: run_git вызывается 3 раза: rev-parse, diff --cached --name-only, diff --cached
        # Возвращаем feature-ветку и пустые диффы — никаких предупреждений о ветке
        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/voice-input"
            return ""

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            # Не должен бросить SystemExit(2)
            pre_commit_guard.main()

        # Проверяем, что блокировки не было (нет exit с кодом 2)
        # Тест пройдёт если main() завершится без исключения

    def test_detects_sensitive_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Staged .env и credentials.json должны генерировать предупреждение."""
        data = make_bash_input('git commit -m "feat: add config"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return ".env\ncredentials.json"
            return ""  # diff --cached пустой

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        # emit_hook_result пишет JSON в stdout с additionalContext
        assert "sensitive" in captured.out.lower() or "WARNING" in captured.out

    def test_detects_debug_statements(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Добавленная строка с print() в diff должна генерировать предупреждение."""
        data = make_bash_input('git commit -m "feat: logging"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/test"
            if "--name-only" in args:
                return "app.py"
            # diff --cached содержит добавленный print()
            return "+    print(foo)\n+    result = compute()"

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        assert "print(" in captured.out or "Debug" in captured.out or "debug" in captured.out

    def test_ignores_removed_debug(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Удалённые строки с print() (начинаются с '-') не должны вызывать предупреждение."""
        data = make_bash_input('git commit -m "refactor: clean up"')
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        def mock_run_git(args: list, **kwargs) -> str:
            if "rev-parse" in args:
                return "feature/clean"
            if "--name-only" in args:
                return "app.py"
            # ПОЧЕМУ: строка начинается с '-' — это удалённая строка, хук её игнорирует
            return "-    print(foo)\n+    logger.debug('foo')"

        with patch("pre_commit_guard.run_git", side_effect=mock_run_git):
            import pre_commit_guard

            pre_commit_guard.main()

        captured = capsys.readouterr()
        # Предупреждение о debug statements НЕ должно содержать "print("
        # (logger.debug не входит в debug_patterns)
        output_data = json.loads(captured.out) if captured.out.strip() else {}
        context = output_data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "print(" not in context

    def test_blocks_push_to_public_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """git push public main должен блокироваться с exit(2)."""
        data = make_bash_input("git push public main")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        with pytest.raises(SystemExit) as exc_info:
            pre_commit_guard.main()

        assert exc_info.value.code == 2

    def test_allows_push_feature_to_public(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """git push public feature/x разрешён — только main/master блокируются."""
        data = make_bash_input("git push public feature/voice-input")
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import pre_commit_guard

        # Не должен бросить SystemExit(2)
        pre_commit_guard.main()

        captured = capsys.readouterr()
        assert captured.err == ""
