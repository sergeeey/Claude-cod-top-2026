"""Unit tests for hooks/keyword_router.py — prompt routing and power modes.

WHY: keyword_router is the entry point for every user prompt. If routing
is broken, users lose skill suggestions and power modes silently.
"""

import io
import json

import pytest
from keyword_router import (
    PowerMode,
    find_power_mode,
    find_skill,
    is_informational,
    main,
    resolve_alias,
)

# === is_informational ===


class TestIsInformational:
    def test_what_is_prefix(self):
        assert is_informational("what is TDD") is True

    def test_how_does_prefix(self):
        assert is_informational("how does security work") is True

    def test_russian_chto_takoe(self):
        assert is_informational("что такое security audit") is True

    def test_russian_kak_rabotaet(self):
        assert is_informational("как работает memory system") is True

    def test_task_prompt_not_informational(self):
        assert is_informational("do TDD now") is False

    def test_empty_prompt(self):
        assert is_informational("") is False

    def test_security_keyword_alone(self):
        assert is_informational("security audit this code") is False

    def test_mixed_case_prefix(self):
        # WHY: is_informational lowercases before comparison
        assert is_informational("What Is TDD") is True


# === resolve_alias ===


class TestResolveAlias:
    def test_ulw_resolves_to_ultrawork(self):
        assert resolve_alias("ulw") == "ultrawork"

    def test_avto_resolves_to_autopilot(self):
        assert resolve_alias("авто") == "autopilot"

    def test_bystro_resolves_to_quick(self):
        assert resolve_alias("быстро") == "quick"

    def test_canonical_unchanged(self):
        assert resolve_alias("ralph") == "ralph"

    def test_unknown_token_unchanged(self):
        assert resolve_alias("unknown_mode") == "unknown_mode"


# === find_power_mode ===


class TestFindPowerMode:
    def test_ralph_detected(self):
        mode = find_power_mode("ralph fix this bug")
        assert mode is not None
        assert mode.name == "Persistent"

    def test_autopilot_detected(self):
        mode = find_power_mode("autopilot deploy everything")
        assert mode is not None
        assert mode.name == "Full Autonomy"

    def test_ultrawork_detected(self):
        mode = find_power_mode("ultrawork on all files")
        assert mode is not None
        assert mode.name == "Max Parallelism"

    def test_deep_detected(self):
        mode = find_power_mode("deep analysis of this module")
        assert mode is not None
        assert mode.name == "Deep Analysis"

    def test_quick_detected(self):
        mode = find_power_mode("quick fix the typo")
        assert mode is not None
        assert mode.name == "Speed"

    def test_alias_ulw_detected(self):
        mode = find_power_mode("ulw fix all tests")
        assert mode is not None
        assert mode.name == "Max Parallelism"

    def test_alias_avto_detected(self):
        mode = find_power_mode("авто execute plan")
        assert mode is not None
        assert mode.name == "Full Autonomy"

    def test_no_power_mode(self):
        assert find_power_mode("do TDD on auth module") is None

    def test_case_insensitive_canonical(self):
        # WHY: prompt is lowercased before lookup
        mode = find_power_mode("RALPH fix everything")
        assert mode is not None
        assert mode.name == "Persistent"

    def test_returns_powermode_dataclass(self):
        mode = find_power_mode("ralph go")
        assert isinstance(mode, PowerMode)
        assert isinstance(mode.instruction, str)
        assert len(mode.instruction) > 0


# === find_skill ===


class TestFindSkill:
    def test_tdd_keyword(self):
        assert find_skill("let's do TDD on this") == "tdd-workflow"

    def test_test_keyword(self):
        assert find_skill("write test for auth") == "tdd-workflow"

    def test_security_keyword(self):
        assert find_skill("security audit this code") == "security-audit"

    def test_audit_keyword(self):
        assert find_skill("audit the payment module") == "security-audit"

    def test_design_keyword(self):
        assert find_skill("design the new API") == "brainstorming"

    def test_alternatives_keyword(self):
        assert find_skill("what are the alternatives") == "brainstorming"

    def test_explain_keyword(self):
        assert find_skill("explain how hooks work") == "mentor-mode"

    def test_worktree_keyword(self):
        assert find_skill("create a worktree for this") == "git-worktrees"

    def test_research_keyword(self):
        assert find_skill("research trending AI tools") == "last30days"

    def test_corpus_keyword(self):
        assert find_skill("analyze this corpus of papers") == "research-corpus"

    def test_russian_phrase_corpus(self):
        assert find_skill("анализ корпуса данных") == "research-corpus"

    def test_russian_razberis(self):
        assert find_skill("разбери статьи по теме") == "research-corpus"

    def test_analyze_papers_phrase(self):
        assert find_skill("analyze papers on this topic") == "research-corpus"

    def test_no_match_returns_none(self):
        assert find_skill("hello world") is None

    def test_no_match_greeting(self):
        assert find_skill("good morning") is None


# === main() — integration via stdin ===


class TestMain:
    def _run_main(self, monkeypatch, data: dict) -> tuple[str, int]:
        """Helper: feed data as stdin to main(), capture stdout + exit code."""
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        exit_code = 0
        try:
            main()
        except SystemExit as e:
            exit_code = e.code or 0
        return exit_code

    def test_invalid_json_exits_silently(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("not json {{{"))
        with pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        assert out == ""

    def test_empty_prompt_exits_silently(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": ""})))
        with pytest.raises(SystemExit):
            main()
        assert capsys.readouterr().out == ""

    def test_power_mode_emits_info(self, monkeypatch, capsys):
        # WHY: "ralph" triggers power mode; prompt has no skill keywords → 1 line output
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": "ralph deploy this"})))
        with pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        first_line = out.strip().split("\n")[0]
        parsed = json.loads(first_line)
        assert parsed["result"] == "info"
        assert "Persistent" in parsed["message"]

    def test_informational_no_skill_suggestion(self, monkeypatch, capsys):
        # WHY: "what is TDD" → guard fires, no suggestion emitted
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"prompt": "what is TDD"})))
        with pytest.raises(SystemExit):
            main()
        assert capsys.readouterr().out == ""

    def test_skill_suggestion_emitted(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "sys.stdin", io.StringIO(json.dumps({"prompt": "security audit this module"}))
        )
        with pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        parsed = json.loads(out.strip())
        assert "security-audit" in parsed["message"]

    def test_power_mode_and_skill_both_emitted(self, monkeypatch, capsys):
        # WHY: power modes are additive — ralph + security should emit both
        monkeypatch.setattr(
            "sys.stdin", io.StringIO(json.dumps({"prompt": "ralph security audit everything"}))
        )
        with pytest.raises(SystemExit):
            main()
        lines = [ln for ln in capsys.readouterr().out.strip().split("\n") if ln]
        assert len(lines) == 2
        messages = [json.loads(ln)["message"] for ln in lines]
        assert any("Persistent" in m for m in messages)
        assert any("security-audit" in m for m in messages)

    def test_no_match_silent(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "sys.stdin", io.StringIO(json.dumps({"prompt": "hello, how are you today"}))
        )
        with pytest.raises(SystemExit):
            main()
        assert capsys.readouterr().out == ""

    def test_missing_prompt_key(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"other_key": "value"})))
        with pytest.raises(SystemExit):
            main()
        assert capsys.readouterr().out == ""
