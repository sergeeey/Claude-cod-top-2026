"""Unit tests for hooks/keyword_router.py — prompt routing and power modes.

WHY: keyword_router is the entry point for every user prompt. If routing
is broken, users lose skill suggestions and power modes silently.
"""

import io
import json

import keyword_router
import pytest
from keyword_router import (
    PowerMode,
    find_power_mode,
    find_skill,
    is_informational,
    main,
    resolve_alias,
)


def _write_index(tmp_path, entries):
    path = tmp_path / "skill_trigger_index.json"
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


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
    @pytest.fixture(autouse=True)
    def _isolate_from_real_machine_index(self, monkeypatch, tmp_path):
        """Point TRIGGER_INDEX_PATH at an empty file for this class.

        WHY: find_skill() now consults the auto-index even when a KEYWORD_MAP
        entry also matches (see the 2026-09-10 fix in keyword_router.py). On
        the maintainer's own machine, the REAL personal trigger index (170+
        skills) sits at the real TRIGGER_INDEX_PATH -- letting these plain
        KEYWORD_MAP-only tests read it would make them depend on whatever
        happens to be indexed locally, and pass/fail differently here than on
        CI (which never has that personal file). TestAutoIndexFallback below
        monkeypatches its own index per test where the auto-index IS the point.
        """
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", tmp_path / "no-index-here.json")

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


# === auto-generated trigger index (find_skill fallback) ===


class TestAutoIndexFallback:
    def test_missing_index_file_falls_back_silently(self, monkeypatch, tmp_path):
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", tmp_path / "missing.json")
        assert find_skill("consortium hypothesis time") is None

    def test_corrupt_index_file_falls_back_silently(self, monkeypatch, tmp_path):
        path = tmp_path / "index.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("consortium hypothesis time") is None

    def test_top_level_list_falls_back_silently(self, monkeypatch, tmp_path):
        # WHY: syntactically valid JSON, structurally unexpected -- a bare
        # top-level list has no .get() and must not crash _load_trigger_index.
        path = tmp_path / "index.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("consortium hypothesis time") is None

    def test_non_dict_entry_falls_back_silently(self, monkeypatch, tmp_path):
        # WHY: a non-dict item in "entries" (or a dict missing "skill") must
        # be skipped, not crash the scan or corrupt the longest-match state.
        path = _write_index(
            tmp_path,
            [
                "not-a-dict",
                None,
                {"trigger": "no skill key here", "kind": "phrase"},
                {
                    "trigger": "разбери гипотезу консорциумом",
                    "skill": "boyko-scientific-consortium",
                    "kind": "phrase",
                },
            ],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("разбери гипотезу консорциумом") == "boyko-scientific-consortium"

    def test_slash_trigger_matches(self, monkeypatch, tmp_path):
        path = _write_index(
            tmp_path,
            [
                {
                    "trigger": "/boyko-consortium",
                    "skill": "boyko-scientific-consortium",
                    "kind": "slash",
                }
            ],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("run /boyko-consortium on this") == "boyko-scientific-consortium"

    def test_phrase_trigger_matches_with_word_boundary(self, monkeypatch, tmp_path):
        path = _write_index(
            tmp_path,
            [
                {
                    "trigger": "разбери гипотезу консорциумом",
                    "skill": "boyko-scientific-consortium",
                    "kind": "phrase",
                }
            ],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("Пожалуйста, разбери гипотезу консорциумом сейчас") == (
            "boyko-scientific-consortium"
        )

    def test_hyphenated_bare_trigger_matches(self, monkeypatch, tmp_path):
        path = _write_index(
            tmp_path,
            [
                {
                    "trigger": "agent-governance",
                    "skill": "agent-governance",
                    "kind": "hyphenated-bare",
                }
            ],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("check agent-governance rules") == "agent-governance"

    def test_bare_word_trigger_never_fires(self, monkeypatch, tmp_path):
        # WHY: "bare" kind is deliberately excluded -- too noisy to auto-suggest.
        path = _write_index(
            tmp_path, [{"trigger": "test", "skill": "some-other-skill", "kind": "bare"}]
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        # "test" is in KEYWORD_MAP already, mapped to tdd-workflow -- confirms
        # the auto-index's bare-word entry for a DIFFERENT skill never wins.
        assert find_skill("write test for auth") == "tdd-workflow"

    def test_more_specific_auto_index_trigger_beats_shorter_keyword_map_entry(
        self, monkeypatch, tmp_path
    ):
        # WHY this replaced "keyword_map_takes_precedence" (2026-09-10, real bug
        # found live): KEYWORD_MAP used to win unconditionally just by being
        # checked first, even when the auto-index had a longer, more specific
        # match for a DIFFERENT skill -- e.g. "experiment" (KEYWORD_MAP, 10
        # chars) always beat experiment-design's own real trigger phrases. A
        # real session found this by noticing 47 suggestions in one session
        # were 100% just 3 KEYWORD_MAP entries, 0% any of the other ~160
        # catalogued skills. Fix: the LONGER matched trigger text wins,
        # regardless of which source it came from.
        path = _write_index(
            tmp_path,
            [{"trigger": "security audit this", "skill": "some-other-skill", "kind": "phrase"}],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        # "security audit this" (20 chars) is longer than KEYWORD_MAP's own
        # best match here, "security" (8 chars) -- the more specific one wins.
        assert find_skill("security audit this code") == "some-other-skill"

    def test_keyword_map_wins_on_tie_length(self, monkeypatch, tmp_path):
        # WHY: a tie keeps KEYWORD_MAP's result -- it's hand-curated, and was
        # already trusted for this exact word before the auto-index existed.
        path = _write_index(
            tmp_path,
            [{"trigger": "security", "skill": "some-other-skill", "kind": "phrase"}],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("security review needed") == "security-audit"

    def test_real_incident_experiment_no_longer_shadows_experiment_design(
        self, monkeypatch, tmp_path
    ):
        # WHY: this is the EXACT real-world case that motivated the fix.
        # KEYWORD_MAP maps bare "experiment" -> git-worktrees. Before the fix,
        # any prompt containing "experiment" anywhere always got git-worktrees,
        # and experiment-design's own real (longer, more specific) trigger
        # phrase was never even checked.
        path = _write_index(
            tmp_path,
            [
                {
                    "trigger": "design the experiment",
                    "skill": "experiment-design",
                    "kind": "phrase",
                }
            ],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("please design the experiment for this ablation") == "experiment-design"
        # KEYWORD_MAP's bare "experiment" still wins when nothing more specific matches.
        assert find_skill("let's start a new experiment") == "git-worktrees"

    def test_longest_matching_trigger_wins(self, monkeypatch, tmp_path):
        # WHY both entries genuinely match the same prompt: "разбери гипотезу"
        # is a substring of the longer phrase below -- proves specificity
        # wins, not just "some other trigger happened not to match".
        path = _write_index(
            tmp_path,
            [
                {"trigger": "разбери гипотезу", "skill": "wrong-skill", "kind": "phrase"},
                {
                    "trigger": "разбери гипотезу консорциумом",
                    "skill": "boyko-scientific-consortium",
                    "kind": "phrase",
                },
            ],
        )
        monkeypatch.setattr(keyword_router, "TRIGGER_INDEX_PATH", path)
        assert find_skill("разбери гипотезу консорциумом") == "boyko-scientific-consortium"


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
