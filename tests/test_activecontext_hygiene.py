"""Tests for activeContext_hygiene.py — RDR 2.1 Checkpoint Fidelity nudge.

Positive control (mandatory per the DDD skeptic verdict on this gap, 2026-07-19):
the linter MUST catch the historical "~600/701 orphaned git.exe processes" claim
shape, replayed unmarked — the actual incident that motivated this hook. If this
test fails, the pattern set is wrong; do not merge until it passes.
"""

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from activeContext_hygiene import (
    _EVIDENCE_MARKER,
    _HEDGE_VERB,
    _NUMERIC_CLAIM,
    _new_text_from_tool_input,
    _nudge_message,
    main,
    scan_paragraphs,
)


class TestPositiveControlRealIncident:
    """Ground truth: this specific claim shape lived unverified in this
    project's own activeContext.md for 9+ sessions. The linter exists because
    of this exact incident -- it must catch it."""

    def test_catches_the_real_historical_claim_unmarked(self):
        para = (
            "branch: main -- ~600/701 orphaned git.exe processes detected, "
            "investigate before continuing."
        )
        flagged = scan_paragraphs(para)
        assert len(flagged) == 1
        assert "600" in flagged[0]

    def test_same_claim_with_evidence_marker_is_not_flagged(self):
        # WHY: this is what the retraction actually looked like once verified --
        # the linter must not nag on a claim that IS properly marked.
        para = (
            "[VERIFIED] git.exe count oscillates 19-36 via wmic, ordinary "
            "git-status polling by Claude.exe -- NOT a leak, retracting the "
            "earlier ~600 orphaned claim."
        )
        assert scan_paragraphs(para) == []


class TestScanParagraphsControl:
    def test_plain_fact_with_marker_not_flagged(self):
        para = "[VERIFIED] full suite 2317 passed, 3 skipped, 2 xfailed."
        assert scan_paragraphs(para) == []

    def test_exact_number_without_marker_is_NOT_flagged(self):
        # WHY: exact counts ("2317 tests passed") are this project's own normal
        # evidence-heavy writing style -- only APPROXIMATE-shaped claims (~N)
        # are flagged, or the linter would nag on nearly every state update.
        para = "2317 tests passed after the fix."
        assert scan_paragraphs(para) == []

    def test_hedge_verb_without_marker_is_flagged(self):
        para = "Вероятно, это связано с устаревшим кэшем модулей."
        flagged = scan_paragraphs(para)
        assert len(flagged) == 1

    def test_hedge_verb_with_marker_not_flagged(self):
        # WHY [WEAK] not [HYPOTHESIS]: this hook's vocabulary is integrity.md's
        # 8 canonical markers exactly (see _EVIDENCE_MARKER) -- [HYPOTHESIS] is
        # a status label used elsewhere (FL claim status, skeptic verdicts),
        # not part of that set, so it correctly does NOT suppress the nudge.
        para = "[WEAK] вероятно связано с кэшем, требует проверки."
        assert scan_paragraphs(para) == []

    def test_multiple_paragraphs_only_unmarked_ones_flagged(self):
        text = (
            "[VERIFIED] 90 hooks confirmed via ls | wc -l.\n\n"
            "~50 skills seem outdated and probably need review.\n\n"
            "[MEMORY] roughly 12 agents recalled from last session."
        )
        flagged = scan_paragraphs(text)
        # WHY only the middle paragraph: first and third both carry a marker
        # despite ALSO containing "roughly"/exact numbers -- marker wins.
        assert len(flagged) == 1
        assert "50 skills" in flagged[0]

    def test_empty_text_returns_empty(self):
        assert scan_paragraphs("") == []

    def test_blank_paragraphs_are_skipped(self):
        assert scan_paragraphs("\n\n\n   \n\n") == []


class TestToolInputExtraction:
    def test_write_uses_content_field(self):
        assert _new_text_from_tool_input("Write", {"content": "hello ~40"}) == "hello ~40"

    def test_edit_uses_new_string_field(self):
        assert _new_text_from_tool_input("Edit", {"new_string": "hi ~40"}) == "hi ~40"

    def test_unknown_tool_returns_empty(self):
        assert _new_text_from_tool_input("Bash", {"command": "ls"}) == ""

    def test_missing_field_returns_empty(self):
        assert _new_text_from_tool_input("Write", {}) == ""

    def test_none_content_value_does_not_become_literal_none_string(self):
        # WHY: dict.get(key, default) only uses default on a MISSING key -- an
        # explicit content: null round-trips through str(None) into the
        # literal string "None" unless guarded with `or ""`. Same trap that
        # bit gate 9/10 earlier this session (depends_on: None,
        # maturity_evidence: null in check_architecture.py).
        assert _new_text_from_tool_input("Write", {"content": None}) == ""

    def test_none_new_string_value_does_not_become_literal_none_string(self):
        assert _new_text_from_tool_input("Edit", {"new_string": None}) == ""


class TestNudgeMessage:
    def test_message_names_the_historical_incident(self):
        msg = _nudge_message(["~600 orphaned processes, no source"])
        assert "600 orphaned git.exe" in msg
        assert "not blocked" in msg

    def test_message_truncates_beyond_max_shown(self):
        flagged = [f"claim {i} ~{i}" for i in range(8)]
        msg = _nudge_message(flagged)
        assert "+3 more" in msg


class TestRegexConstants:
    def test_numeric_claim_matches_approximate_forms(self):
        for text in ("~600", "около 600", "примерно 600", "roughly 600"):
            assert _NUMERIC_CLAIM.search(text), text

    def test_numeric_claim_does_not_match_bare_exact_number(self):
        assert _NUMERIC_CLAIM.search("2317 tests") is None

    def test_evidence_marker_matches_known_vocabulary(self):
        for tag in (
            "[VERIFIED]",
            "[INFERRED]",
            "[MEMORY]",
            "[WEAK]",
            "[CONFLICTING]",
            "[UNKNOWN]",
            "[DOCS]",
            "[CODE]",
            "[VERIFIED-REAL]",  # WHY: suffix variants must still match
        ):
            assert _EVIDENCE_MARKER.search(tag), tag

    def test_hedge_verb_case_insensitive(self):
        assert _HEDGE_VERB.search("It Seems this works")


class TestMainEndToEnd:
    """Reviewer P2 (2026-07-19): 19 unit tests covered scan_paragraphs/etc, but
    nothing drove main() itself through fake stdin -- a typo in _TARGET_FILENAME
    or a broken parse_stdin() call could slip through all of them silently.
    These close that gap, matching gate 9/10's mutation/non-vacuity precedent.
    """

    @staticmethod
    def _stdin(data: dict) -> io.StringIO:
        return io.StringIO(json.dumps(data))

    def _run(self, monkeypatch, capsys, data: dict) -> str:
        """Drive main() end-to-end through fake stdin, return captured stdout.

        WHY tolerant of both endings: matches locality_escalation_guard.py's
        own house style -- sys.exit(0) is used on EARLY skip paths only; the
        "work done, nudge emitted" path falls through and returns normally
        (the process still exits 0 when run as __main__, just not via an
        explicit call at that point).
        """
        monkeypatch.setattr("sys.stdin", self._stdin(data))
        try:
            main()
        except SystemExit as exc:
            assert exc.code in (0, None)
        return capsys.readouterr().out

    def test_real_incident_shape_through_wired_main(self, monkeypatch, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Edit",
            "session_id": "e2e-1",
            "tool_input": {
                "file_path": ".claude/memory/activeContext.md",
                "new_string": "~600 orphaned git.exe processes on this machine, investigate.",
            },
        }
        out = self._run(monkeypatch, capsys, payload)
        assert "activeContext-hygiene" in out
        assert "600 orphaned git.exe" in out

    def test_marked_claim_through_wired_main_is_silent(self, monkeypatch, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Edit",
            "session_id": "e2e-2",
            "tool_input": {
                "file_path": ".claude/memory/activeContext.md",
                "new_string": "[VERIFIED] 2317 tests passed via pytest.",
            },
        }
        assert self._run(monkeypatch, capsys, payload) == ""

    def test_wrong_file_through_wired_main_is_silent(self, monkeypatch, capsys):
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Edit",
            "session_id": "e2e-3",
            "tool_input": {"file_path": "README.md", "new_string": "~999 unverified figure"},
        }
        assert self._run(monkeypatch, capsys, payload) == ""

    def test_recursion_guard_through_wired_main_is_silent(self, monkeypatch, capsys):
        # WHY this must go through main(), not process_edit-style unit test:
        # the guard is an `if os.environ.get(...): sys.exit(0)` at the TOP of
        # main() -- only an end-to-end call proves it actually short-circuits
        # before parse_stdin/scan_paragraphs run at all.
        monkeypatch.setenv("CLAUDE_INVOKED_BY", "subagent")
        payload = {
            "tool_name": "Edit",
            "session_id": "e2e-4",
            "tool_input": {
                "file_path": ".claude/memory/activeContext.md",
                "new_string": "~600 orphaned git.exe processes, unmarked, should be suppressed.",
            },
        }
        assert self._run(monkeypatch, capsys, payload) == ""

    def test_none_file_path_through_wired_main_is_silent(self, monkeypatch, capsys):
        # WHY: covers the file_path: None trap fixed alongside content/new_string
        # -- str(None) must not accidentally satisfy the filename suffix check.
        monkeypatch.delenv("CLAUDE_INVOKED_BY", raising=False)
        payload = {
            "tool_name": "Edit",
            "session_id": "e2e-5",
            "tool_input": {"file_path": None, "new_string": "~600 orphaned unmarked"},
        }
        assert self._run(monkeypatch, capsys, payload) == ""
