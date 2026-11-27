"""knowledge_librarian pattern lookups must not inject secret values into context.

Found by the N04 controlled memory lab (2026-11-27): _query_patterns and _top_avoid_patterns
returned the raw text of a lesson line, so a value written after `api_key=` reached the
additionalContext. redact_secrets already removes such values; the pattern paths did not call it.
The secret below is a fake test value written for this test, not a real credential.
"""

from __future__ import annotations

import knowledge_librarian

FAKE = "sk-TESTFAKE-0000000000000000"
LINE = f"### [2026-09-02] [AVOID×2] конфиг: в логе попал api_key={FAKE} при отладке"


def _patterns(monkeypatch, tmp_path):
    path = tmp_path / "patterns.md"
    path.write_text("## Отладка и фиксы\n" + LINE + "\n", encoding="utf-8")
    monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", path)
    return path


class TestPatternLinesAreRedacted:
    def test_query_patterns_does_not_return_secret_value(self, monkeypatch, tmp_path):
        _patterns(monkeypatch, tmp_path)
        out = knowledge_librarian._query_patterns(["конфиг"])
        assert out, "the lesson must still be surfaced"
        assert not any(FAKE in line for line in out)

    def test_top_avoid_patterns_does_not_return_secret_value(self, monkeypatch, tmp_path):
        # _top_avoid_patterns matches the literal [AVOID] tag only, not [AVOID×N]
        path = tmp_path / "patterns.md"
        path.write_text(
            "## Отладка и фиксы\n" + LINE.replace("[AVOID×2]", "[AVOID]") + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", path)
        out = knowledge_librarian._top_avoid_patterns(limit=5)
        assert out, "the lesson must still be surfaced"
        assert not any(FAKE in line for line in out)

    def test_lesson_text_without_secret_is_unchanged(self, monkeypatch, tmp_path):
        path = tmp_path / "patterns.md"
        path.write_text(
            "## Отладка и фиксы\n### [2026-09-02] [AVOID×2] кэш сессии: не кэшировать запрос\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", path)
        out = knowledge_librarian._query_patterns(["кэш"])
        assert out and "кэш сессии: не кэшировать запрос" in out[0]

    def test_lowercase_assignment_secret_is_redacted(self, monkeypatch, tmp_path):
        # redact_secrets matches only UPPER_CASE env names for assignments; a lesson that
        # writes `api_key=...` or `password=...` in lowercase must be redacted here too.
        path = tmp_path / "patterns.md"
        path.write_text(
            "## Отладка и фиксы\n"
            "### [2026-09-02] [AVOID×2] логин: в тесте стоял password=hunter2 и api_key=abc123\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", path)
        out = knowledge_librarian._query_patterns(["логин"])
        assert out, "the lesson must still be surfaced"
        text = "\n".join(out)
        assert "hunter2" not in text
        assert "abc123" not in text
