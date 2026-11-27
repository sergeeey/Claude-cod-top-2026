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

    def test_compound_lowercase_names_are_redacted(self, monkeypatch, tmp_path):
        # The narrow pass must not need a word boundary: `_` is a word character, so a
        # \b-anchored pattern misses db_password= and client_secret=.
        path = tmp_path / "patterns.md"
        path.write_text(
            "## Отладка и фиксы\n"
            "### [2026-09-02] [AVOID×2] деплой: в конфиге db_password=hunter2 и client_secret=zzz111\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", path)
        out = knowledge_librarian._query_patterns(["деплой"])
        text = "\n".join(out)
        assert out
        assert "hunter2" not in text
        assert "zzz111" not in text

    def test_quoted_value_with_space_leaves_no_tail(self, monkeypatch, tmp_path):
        path = tmp_path / "patterns.md"
        path.write_text(
            '## Отладка и фиксы\n### [2026-09-02] [AVOID×2] тест: password="hunter 2 long" в фикстуре\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(knowledge_librarian, "PATTERNS_PATH", path)
        out = knowledge_librarian._query_patterns(["тест"])
        text = "\n".join(out)
        assert out
        assert "hunter" not in text
        assert "long" not in text


class TestNarrowPassIsolated:
    """Each mechanism is tested with the other one disabled, so a pass cannot come from the
    side effect of the other component (lesson from the 2026-11-27 review)."""

    def test_narrow_pass_alone_removes_compound_lowercase_secret(self, monkeypatch):
        monkeypatch.setattr(knowledge_librarian, "redact_secrets", lambda s: s)
        out = knowledge_librarian._scrub_lesson("конфиг: db_password=hunter2 в логе")
        assert "hunter2" not in out

    def test_redact_secrets_alone_removes_uppercase_name(self, monkeypatch):
        class _Off:
            @staticmethod
            def sub(repl, text):
                return text

        monkeypatch.setattr(knowledge_librarian, "_LESSON_ASSIGNMENT_SECRET_RE", _Off())
        out = knowledge_librarian._scrub_lesson("конфиг: DB_PASSWORD=hunter2 в логе")
        assert "hunter2" not in out
