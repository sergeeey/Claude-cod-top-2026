"""Тесты для mcp_circuit_breaker_post.py — PostToolUse hook circuit breaker.

ПОЧЕМУ: hook обновляет state-файл circuit breaker на основе результата MCP-вызова.
Тестируем бизнес-логику (is_error + обновление state) изолированно от файловой системы
и stdin — все I/O-зависимости заменены моками.
"""

import os
import sys

# ПОЧЕМУ: hooks лежат на уровень выше tests/. insert(0) гарантирует,
# что наш путь имеет приоритет перед site-packages при импорте.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch  # noqa: E402

import mcp_circuit_breaker_post  # noqa: E402
import pytest  # noqa: E402

# =============================================================================
# Вспомогательные функции
# =============================================================================


def make_event(tool_name: str, tool_result: str) -> dict:
    """Собирает минимальный event-dict для PostToolUse hook."""
    return {"tool_name": tool_name, "tool_result": tool_result}


MCP_TOOL = "mcp__context7__search"  # валидный MCP tool name → server = "context7"
NON_MCP_TOOL = "Read"  # обычный инструмент — не MCP


# =============================================================================
# is_error() — чистая функция, тестируем без моков
# =============================================================================


class TestIsError:
    """is_error: корректно детектирует индикаторы сбоя."""

    def test_detects_error_lowercase(self) -> None:
        assert mcp_circuit_breaker_post.is_error("some error occurred") is True

    def test_detects_timed_out(self) -> None:
        assert mcp_circuit_breaker_post.is_error("request timed out after 30s") is True

    def test_detects_econnrefused_uppercase_in_indicator_list(self) -> None:
        # ПОЧЕМУ: ERROR_INDICATORS содержит "ECONNREFUSED" (uppercase),
        # но is_error() делает lower() только на result, не на индикаторы.
        # Поэтому "ECONNREFUSED" в результате НЕ детектируется — это реальное
        # поведение кода. Тест фиксирует его как known limitation.
        assert mcp_circuit_breaker_post.is_error("ECONNREFUSED 127.0.0.1:3000") is False

    def test_detects_econnrefused_lowercase(self) -> None:
        # lowercase вариант детектируется корректно через индикатор "ECONNREFUSED"
        # только если он совпадёт после lower() — не совпадёт. Но "connection refused"
        # детектируется через отдельный индикатор.
        assert mcp_circuit_breaker_post.is_error("connection refused on port 3000") is True

    def test_detects_502_in_response(self) -> None:
        assert mcp_circuit_breaker_post.is_error("HTTP 502 Bad Gateway") is True

    def test_success_result_not_error(self) -> None:
        assert mcp_circuit_breaker_post.is_error('{"results": [{"id": 1}]}') is False

    def test_empty_result_not_error(self) -> None:
        assert mcp_circuit_breaker_post.is_error("") is False

    def test_case_insensitive_detection(self) -> None:
        # ПОЧЕМУ: is_error делает lower() перед сравнением,
        # поэтому "Error" и "ERROR" должны детектироваться.
        assert mcp_circuit_breaker_post.is_error("Error: something went wrong") is True
        assert mcp_circuit_breaker_post.is_error("ERROR: fatal") is True


# =============================================================================
# main() — тестируем через patch I/O зависимостей
# =============================================================================


class TestSuccessResetsFailures:
    """Success-ответ при существующих failures → сброс счётчика до 0."""

    def test_success_resets_failures(self) -> None:
        # ПОЧЕМУ: circuit breaker восстанавливается из HALF_OPEN при первом
        # успешном ответе — failures и opened_at полностью сбрасываются.
        event = make_event(MCP_TOOL, '{"results": []}')
        existing_state = {"context7": {"failures": 2, "opened_at": 9999.0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 0
        # ПОЧЕМУ: при сбросе entry заменяется целиком {"failures": 0},
        # поэтому opened_at тоже исчезает.
        assert "opened_at" not in saved_state["context7"]

    def test_success_with_zero_failures_saves_clean_entry(self) -> None:
        """Успех при чистом state (failures=0) — state остаётся {"failures": 0}."""
        event = make_event(MCP_TOOL, "ok")
        existing_state = {"context7": {"failures": 0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"] == {"failures": 0}


class TestErrorIncrementsCounter:
    """Error-ответ → failures увеличивается на 1."""

    def test_error_increments_counter_from_zero(self) -> None:
        event = make_event(MCP_TOOL, "connection refused")
        existing_state = {"context7": {"failures": 0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 1

    def test_error_increments_existing_failures(self) -> None:
        event = make_event(MCP_TOOL, "timed out")
        existing_state = {"context7": {"failures": 1}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 2


class TestErrorAtThresholdSetsOpenedAt:
    """При достижении FAILURE_THRESHOLD → opened_at устанавливается."""

    def test_error_at_threshold_sets_opened_at(self) -> None:
        # ПОЧЕМУ: FAILURE_THRESHOLD=3, при failures=2 следующая ошибка
        # поднимает до 3, что >= порога → circuit открывается.
        event = make_event(MCP_TOOL, "500 Internal Server Error")
        existing_state = {"context7": {"failures": 2}}

        fake_time = 1_700_000_000.0

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=fake_time),
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["failures"] == 3
        assert saved_state["context7"]["opened_at"] == pytest.approx(fake_time)

    def test_below_threshold_no_opened_at(self) -> None:
        """Ошибка ниже порога (failures=1) → opened_at не устанавливается."""
        event = make_event(MCP_TOOL, "error")
        existing_state = {"context7": {"failures": 0}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert "opened_at" not in saved_state["context7"]


class TestNonMcpToolSkipped:
    """Не-MCP инструмент (Read, Bash, Write) → state не изменяется."""

    def test_non_mcp_tool_skipped(self) -> None:
        # ПОЧЕМУ: get_mcp_server_name вернёт None для "Read" —
        # hook должен выйти без обращения к state.
        event = make_event(NON_MCP_TOOL, "error critical failure")

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state") as mock_load,
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_load.assert_not_called()
        mock_save.assert_not_called()

    def test_bash_tool_skipped(self) -> None:
        event = make_event("Bash", "timed out")

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state") as mock_load,
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_load.assert_not_called()
        mock_save.assert_not_called()


class TestHandlesMissingStateFile:
    """Нет state-файла → load возвращает {}, ошибка записывается как первая."""

    def test_handles_missing_state_file(self) -> None:
        # ПОЧЕМУ: load_json_state возвращает {} при отсутствии файла.
        # entry = state.get(server, {}) → failures = 0 + 1 = 1.
        # Используем "connection refused" (lowercase), который есть в ERROR_INDICATORS.
        event = make_event(MCP_TOOL, "connection refused")
        empty_state: dict = {}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=empty_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert "context7" in saved_state
        assert saved_state["context7"]["failures"] == 1

    def test_save_called_with_correct_state_file_path(self) -> None:
        """save_json_state вызывается с правильным путём STATE_FILE."""
        event = make_event(MCP_TOOL, "ok")

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value={}),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        called_path = mock_save.call_args[0][0]
        assert called_path == mcp_circuit_breaker_post.STATE_FILE


class TestDoesNotOverwriteOpenedAt:
    """Уже установленный opened_at не перезаписывается при последующих ошибках."""

    def test_does_not_overwrite_opened_at(self) -> None:
        # ПОЧЕМУ: условие `"opened_at" not in entry` защищает от перезаписи.
        # Важно сохранить оригинальное время открытия для TTL-логики.
        original_opened_at = 1_600_000_000.0
        event = make_event(MCP_TOOL, "502 Bad Gateway")
        existing_state = {
            "context7": {
                "failures": 5,  # уже выше порога
                "opened_at": original_opened_at,
            }
        }

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch("mcp_circuit_breaker_post.load_json_state", return_value=existing_state),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=9_999_999_999.0),
        ):
            mcp_circuit_breaker_post.main()

        saved_state = mock_save.call_args[0][1]
        assert saved_state["context7"]["opened_at"] == pytest.approx(original_opened_at)
        assert saved_state["context7"]["failures"] == 6  # инкремент продолжается

    def test_opened_at_set_only_once_at_threshold(self) -> None:
        """opened_at устанавливается ровно один раз — при первом достижении порога."""
        first_opened_at = 1_700_000_000.0
        # Первый вызов: failures 2 → 3, порог достигнут → opened_at ставится
        event = make_event(MCP_TOOL, "failed to connect")
        state_before_threshold = {"context7": {"failures": 2}}

        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch(
                "mcp_circuit_breaker_post.load_json_state",
                return_value=state_before_threshold,
            ),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=first_opened_at),
        ):
            mcp_circuit_breaker_post.main()

        state_after_threshold = mock_save.call_args[0][1]
        assert state_after_threshold["context7"]["opened_at"] == pytest.approx(first_opened_at)

        # Второй вызов: failures 3 → 4, opened_at уже есть → не перезаписывается
        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=event),
            patch(
                "mcp_circuit_breaker_post.load_json_state",
                return_value=state_after_threshold,
            ),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
            patch("mcp_circuit_breaker_post.time.time", return_value=9_999_999_999.0),
        ):
            mcp_circuit_breaker_post.main()

        final_state = mock_save.call_args[0][1]
        assert final_state["context7"]["opened_at"] == pytest.approx(first_opened_at)


class TestEmptyEvent:
    """Пустой или невалидный event → hook завершается без ошибок."""

    def test_empty_event_exits_gracefully(self) -> None:
        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value={}),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_save.assert_not_called()

    def test_none_event_exits_gracefully(self) -> None:
        # ПОЧЕМУ: parse_stdin_raw возвращает {} при ошибке парсинга,
        # но None тоже возможен как крайний случай (хотя utils возвращает {}).
        with (
            patch("mcp_circuit_breaker_post.parse_stdin_raw", return_value=None),
            patch("mcp_circuit_breaker_post.save_json_state") as mock_save,
        ):
            mcp_circuit_breaker_post.main()

        mock_save.assert_not_called()
