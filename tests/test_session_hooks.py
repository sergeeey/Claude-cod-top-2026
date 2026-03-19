"""Тесты для малых session-хуков: pre_compact, session_save, post_format,
read_before_edit, mcp_locality_guard.

ПОЧЕМУ: каждый хук маленький, но вместе они формируют safety net сессии.
Тесты проверяют граничные случаи без реальных subprocess/filesystem вызовов.
"""

import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path  # noqa: E402
from unittest.mock import mock_open, patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Вспомогательная функция для мокирования stdin с JSON-данными."""
    return io.StringIO(json.dumps(data))


# =============================================================================
# pre_compact.py
# =============================================================================


class TestPreCompact:
    """Тесты pre_compact.main(): обновление timestamp в activeContext.md."""

    def test_pre_compact_updates_timestamp(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Если activeContext.md найден — хук обновляет строку '## Updated:'."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text(
            "# Context\n## Updated: 2026-01-01 00:00\nSome content\n", encoding="utf-8"
        )

        # ПОЧЕМУ: patch find_project_memory чтобы не зависеть от реальной файловой системы
        with (
            patch("pre_compact.find_project_memory", return_value=ctx_file),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import pre_compact

            pre_compact.main()

        content = ctx_file.read_text(encoding="utf-8")
        # Строка должна содержать "(pre-compact)" маркер
        assert "pre-compact" in content

    def test_pre_compact_silent_when_no_context(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Если activeContext.md не найден — хук печатает fallback сообщение."""
        with (
            patch("pre_compact.find_project_memory", return_value=None),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import pre_compact

            pre_compact.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: хук всегда что-то печатает через print() — это не emit_hook_result
        assert "No project" in captured.out or "activeContext" in captured.out


# =============================================================================
# session_save.py
# =============================================================================


class TestSessionSave:
    """Тесты session_save.main(): детекция устаревшей памяти перед концом сессии."""

    def test_session_save_detects_stale_memory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Если коммит новее activeContext.md на >5 мин — выводит WARNING."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        now = time.time()
        ctx_mtime = now - 600  # activeContext обновлён 10 мин назад
        commit_time = now - 60  # последний коммит 1 мин назад

        # Устанавливаем mtime файла вручную
        os.utime(ctx_file, (ctx_mtime, ctx_mtime))

        with (
            patch("session_save.find_project_memory", return_value=ctx_file),
            patch("session_save.get_last_commit_time", return_value=commit_time),
            # Пропускаем запись в глобальный activeContext и лог
            patch("os.path.exists", return_value=False),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import session_save

            session_save.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: commit_time > ctx_mtime и разница > 300 сек → WARNING
        assert "WARNING" in captured.out

    def test_session_save_silent_when_context_fresh(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Если activeContext.md обновлён после последнего коммита — молчит."""
        ctx_file = tmp_path / "activeContext.md"
        ctx_file.write_text("# Context\n", encoding="utf-8")

        now = time.time()
        commit_time = now - 600  # коммит 10 мин назад
        ctx_mtime = now - 60  # activeContext обновлён 1 мин назад (свежее коммита)

        os.utime(ctx_file, (ctx_mtime, ctx_mtime))

        with (
            patch("session_save.find_project_memory", return_value=ctx_file),
            patch("session_save.get_last_commit_time", return_value=commit_time),
            patch("os.path.exists", return_value=False),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()),
        ):
            import session_save

            session_save.main()

        captured = capsys.readouterr()
        assert "WARNING" not in captured.out


# =============================================================================
# post_format.py
# =============================================================================


class TestPostFormat:
    """Тесты post_format.main(): авто-форматирование Python/JS файлов."""

    def test_post_format_skips_unknown_ext(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Файл .txt — не Python и не JS/TS, subprocess не вызывается."""
        data = {"tool_input": {"file_path": "foo.txt"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with (
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            import post_format

            post_format.main()

        # ПОЧЕМУ: расширение .txt не в списке (.py, .js, .ts, .jsx, .tsx) → no subprocess
        mock_run.assert_not_called()

    def test_post_format_calls_ruff_for_py(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Файл .py — вызывает ruff format."""
        data = {"tool_input": {"file_path": "/project/app.py"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with (
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            import post_format

            post_format.main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ruff" in call_args

    def test_post_format_calls_prettier_for_ts(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Файл .ts — вызывает prettier."""
        data = {"tool_input": {"file_path": "/project/app.ts"}}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        with (
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            import post_format

            post_format.main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "prettier" in call_args


# =============================================================================
# read_before_edit.py
# =============================================================================


class TestReadBeforeEdit:
    """Тесты read_before_edit.main(): напоминание читать файл перед Edit."""

    def test_read_before_edit_warns_on_edit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Tool 'Edit' с file_path — печатает напоминание в stderr."""
        data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/project/utils.py"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import read_before_edit

        with pytest.raises(SystemExit) as exc_info:
            read_before_edit.main()

        # ПОЧЕМУ: хук всегда завершается через sys.exit(0) — это нормальный выход
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "read-before-edit" in captured.err.lower()
        assert "utils.py" in captured.err

    def test_read_before_edit_skips_write(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Tool 'Write' — хук не печатает предупреждение (новый файл читать нечего)."""
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/project/new_file.py"},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import read_before_edit

        with pytest.raises(SystemExit) as exc_info:
            read_before_edit.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # ПОЧЕМУ: Write пишет новый файл — читать нечего, предупреждение не нужно
        assert captured.err == ""

    def test_read_before_edit_skips_no_file_path(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Edit без file_path — хук молчит."""
        data = {
            "tool_name": "Edit",
            "tool_input": {},
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import read_before_edit

        with pytest.raises(SystemExit) as exc_info:
            read_before_edit.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""


# =============================================================================
# mcp_locality_guard.py
# =============================================================================


class TestMcpLocalityGuard:
    """Тесты mcp_locality_guard.main(): напоминание пробовать локальный поиск перед MCP."""

    def test_mcp_locality_skips_exempt_basic_memory(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__basic-memory — exempt MCP, предупреждение не выдаётся."""
        data = {"tool_name": "mcp__basic-memory__note__create"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # ПОЧЕМУ: basic-memory в EXEMPT_MCPS → ранний return без вывода
        assert captured.err == ""

    def test_mcp_locality_skips_non_mcp_tool(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Обычный инструмент (Read, Bash) — не MCP, хук молчит."""
        data = {"tool_name": "Read"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_mcp_locality_warns_for_context7(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__context7 — не exempt, хук выдаёт напоминание в stderr."""
        data = {"tool_name": "mcp__context7__search"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # ПОЧЕМУ: context7 не в EXEMPT_MCPS → напоминание про локальный поиск
        assert "mcp-locality" in captured.err
        assert "mcp__context7__search" in captured.err

    def test_mcp_locality_skips_sequential_thinking(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__sequential-thinking — exempt, предупреждение не выдаётся."""
        data = {"tool_name": "mcp__sequential-thinking__think"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_mcp_locality_warns_for_ollama(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """mcp__ollama — не exempt, предупреждение в stderr."""
        data = {"tool_name": "mcp__ollama__generate"}
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import mcp_locality_guard

        with pytest.raises(SystemExit) as exc_info:
            mcp_locality_guard.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "mcp-locality" in captured.err
