"""Тесты для plan_mode_guard.py.

ПОЧЕМУ: plan_mode_guard следит за количеством уникальных файлов в сессии.
При 3+ файлах — напоминание, при 5+ — жёсткое предупреждение. Тесты изолируют
логику через мокирование stdin, temp-файла трекера и has_active_plan().
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


def make_stdin(data: dict) -> io.StringIO:
    """Вспомогательная функция для мокирования stdin с JSON-данными."""
    return io.StringIO(json.dumps(data))


def make_edit_input(file_path: str, session_id: str = "test-session-001") -> dict:
    """Создать данные хука PostToolUse для Edit/Write операции."""
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path},
        "session_id": session_id,
    }


class TestPlanModeGuardMain:
    """Тесты main() через мокирование stdin и трекера файлов."""

    def test_skips_no_file_path(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Если tool_input не содержит file_path — хук молчит."""
        data = {
            "tool_name": "Edit",
            "tool_input": {},
            "session_id": "test-session-001",
        }
        monkeypatch.setattr("sys.stdin", make_stdin(data))

        import plan_mode_guard

        plan_mode_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: ранний return если file_path пустой — нечего трекать
        assert captured.out == ""

    def test_no_warning_under_3_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """2 уникальных файла за сессию — предупреждений нет."""
        session_id = "sess-under3"

        # ПОЧЕМУ: используем tmp_path для изоляции трекера между тестами.
        # Патчим tempfile.gettempdir() чтобы get_tracker_path() писал в tmp_path.
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        with patch("plan_mode_guard.has_active_plan", return_value=False):
            import plan_mode_guard

            for i in range(1, 3):  # файлы 1 и 2
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        assert "plan" not in captured.out.lower()

    def test_warns_at_3_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """3 уникальных файла — мягкое напоминание о Plan-First."""
        session_id = "sess-at3"
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        with patch("plan_mode_guard.has_active_plan", return_value=False):
            import plan_mode_guard

            for i in range(1, 4):  # файлы 1, 2, 3
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: при count==3 хук выводит JSON с "plan-mode-guard" в additionalContext
        assert "plan-mode-guard" in captured.out
        assert "3 unique files" in captured.out

    def test_stronger_warning_at_5_files(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """5 уникальных файлов — усиленное предупреждение WARNING."""
        session_id = "sess-at5"
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        with patch("plan_mode_guard.has_active_plan", return_value=False):
            import plan_mode_guard

            for i in range(1, 6):  # файлы 1..5
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        # ПОЧЕМУ: при count>=5 хук выводит "WARNING:" — более настойчивое сообщение
        assert "WARNING" in captured.out
        assert "plan-mode-guard" in captured.out

    def test_suppressed_when_plan_exists(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
    ) -> None:
        """При наличии активного плана предупреждения подавляются даже при 5+ файлах."""
        session_id = "sess-with-plan"
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

        # ПОЧЕМУ: has_active_plan() = True → хук делает ранний return после записи трекера,
        # не выдавая никаких предупреждений — агент работает по плану
        with patch("plan_mode_guard.has_active_plan", return_value=True):
            import plan_mode_guard

            for i in range(1, 6):
                data = make_edit_input(f"/project/file{i}.py", session_id)
                monkeypatch.setattr("sys.stdin", make_stdin(data))
                plan_mode_guard.main()

        captured = capsys.readouterr()
        assert captured.out == ""
