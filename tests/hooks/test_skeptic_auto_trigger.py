#!/usr/bin/env python3
"""Tests for skeptic_auto_trigger.py hook.

WHY: Skeptic auto-trigger is critical anti-hallucination defense.
Tests verify all 5 triggers from skeptic-triggers.md work correctly.
"""

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

# Add hooks to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from skeptic_auto_trigger import (
    check_response_for_skeptic_triggers,
    filter_tool_output_noise,
    is_argosarb_critical_pattern,
)


class TestSkepticTriggers:
    """Test individual trigger patterns via check_response_for_skeptic_triggers."""

    def test_trigger_1_high_confidence_claims(self):
        """Trigger 1: 100% / all / zero / perfect."""
        # WHY: from skeptic-triggers.md:11-16
        claims = [
            "All 10 hypotheses validated",
            "100% precision, 100% recall",
            "Zero failures in 50 tests",
            "Perfect score on validation",
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert len(triggered) > 0, f"Failed on: {claim}"
            assert 0 in triggered, f"Trigger 1 should fire on: {claim}"

    def test_trigger_1_negative_cases(self):
        """Trigger 1 should NOT fire on partial success."""
        claims = [
            "98% of tests passed",  # not 100%
            "Most hypotheses validated",  # not "all"
            "Near-perfect results",  # not "perfect" standalone
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert 0 not in triggered, f"False positive on trigger 1: {claim}"

    def test_trigger_2_unexpected_success(self):
        """Trigger 2: F1=1.000 / precision=1.0 (perfect metrics)."""
        # WHY: from skeptic-triggers.md:20-25
        claims = [
            "F1=1.000 on test set",
            "precision=1.0 achieved",
            "recall=1.000 measured",
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert len(triggered) > 0, f"Failed on: {claim}"
            assert 1 in triggered, f"Trigger 2 should fire on: {claim}"

    def test_trigger_2_negative_cases(self):
        """Trigger 2 should NOT fire on realistic metrics."""
        claims = [
            "F1=0.987 on test set",
            "precision=0.95 achieved",
            "F1 score: 0.8",
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert 1 not in triggered, f"False positive on trigger 2: {claim}"

    def test_trigger_3_synthetic_evidence(self):
        """Trigger 3: [VERIFIED-SYNTHETIC] marker."""
        # WHY: from skeptic-triggers.md:48-53
        claim = "F1=1.000 [VERIFIED-SYNTHETIC] on create_synthetic_dataset()"
        triggered = check_response_for_skeptic_triggers(claim)
        assert 2 in triggered, "Trigger 3 should fire on [VERIFIED-SYNTHETIC]"

    def test_trigger_4_round_numbers(self):
        """Trigger 4: Suspiciously perfect decimals."""
        # WHY: from skeptic-triggers.md:38-44
        claims = [
            "Accuracy: 1.000",
            "Correlation: 0.9990",
            "R²: 0.99000",
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert len(triggered) > 0, f"Failed on: {claim}"
            assert 3 in triggered, f"Trigger 4 should fire on: {claim}"

    def test_trigger_4_negative_cases(self):
        """Trigger 4 should NOT fire on realistic decimals."""
        claims = [
            "Accuracy: 0.987",
            "Correlation: 0.94",
            "R²: 0.856",
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert 3 not in triggered, f"False positive on trigger 4: {claim}"

    def test_trigger_5_inline_synthetic_data(self):
        """Trigger 5: inline embedded test data (hardest to detect theater)."""
        # WHY: from skeptic-triggers.md:56-65 — no create_synthetic_dataset()
        # function name, just raw embedded tuples/dicts as "test" evidence.
        claims = [
            'abstracts = [("this paper shows", "SMOKING_GUN"), ("text2", "WEAK")]',
            'test_cases = ["example input", "other example"]',
            'result = {"expected": "positive", "got": "positive"}',
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert 4 in triggered, f"Trigger 5 should fire on inline synthetic: {claim}"

    def test_trigger_5_negative_cases(self):
        """Trigger 5 should NOT fire on legitimate code patterns."""
        claims = [
            'results = [(row["id"], row["value"]) for row in data]',  # real data iteration
            "assert expected == actual",  # unit test assertion, not embedded data
        ]
        for claim in claims:
            triggered = check_response_for_skeptic_triggers(claim)
            assert 4 not in triggered, f"False positive on trigger 5: {claim}"


class TestCheckResponse:
    """Test full response checking logic."""

    def test_multiple_triggers_fired(self):
        """Response with multiple trigger patterns."""
        response = """
        Validation complete: All 10 niches validated.
        Results: F1=1.000, precision=1.0, recall=1.000
        [VERIFIED-SYNTHETIC] on test dataset
        """
        triggered = check_response_for_skeptic_triggers(response)
        assert len(triggered) >= 2, f"Expected ≥2 triggers, got {triggered}"

    def test_no_triggers_on_clean_response(self):
        """Normal response should not trigger."""
        response = """
        Validation results: F1=0.87, precision=0.91
        Tested on 50 real samples from production logs.
        [VERIFIED-REAL] with external dataset.
        """
        triggered = check_response_for_skeptic_triggers(response)
        assert len(triggered) == 0, f"False positives: {triggered}"

    def test_escape_hatch_pilot_only(self):
        """[PILOT-ONLY] tag should suppress trigger."""
        response = """
        [PILOT-ONLY] Preliminary results: F1=1.000
        This is a proof-of-concept, not production validation.
        """
        # WHY: skeptic-triggers.md:150-154 defines escape hatches
        triggered = check_response_for_skeptic_triggers(response)
        assert len(triggered) == 0, "Escape hatch should suppress all triggers"


class TestArgosarbCriticalPattern:
    """is_argosarb_critical_pattern: escape-hatch-independent critical check."""

    def test_fires_on_t1_plus_t2_without_real_data(self):
        text = "All 10 niches passed. F1=1.000 across all evaluation sets."
        assert is_argosarb_critical_pattern(text)

    def test_does_not_fire_with_real_data_marker(self):
        text = "All 10 niches passed. F1=1.000 [VERIFIED-REAL] on production logs."
        assert not is_argosarb_critical_pattern(text)

    def test_does_not_fire_on_t1_alone(self):
        text = "All 10 niches passed with excellent results."
        assert not is_argosarb_critical_pattern(text)

    def test_bare_unrelated_url_does_not_suppress_critical_pattern(self):
        """Regression (HIGH): any http(s)/s3/gs URL anywhere in the response
        previously counted as "real data" and let the ArgosArb signature
        dodge the hard block, even when the URL was unrelated to the data
        (e.g. a docs link sitting next to a synthetic-looking perfect score)."""
        text = (
            "All 10 niches passed. F1=1.000 across all sets. "
            "See https://example.com/docs for methodology notes."
        )
        assert is_argosarb_critical_pattern(text)

    def test_defer_skeptic_does_not_suppress_critical_pattern(self):
        """Regression (HIGH): [DEFER-SKEPTIC] previously suppressed the
        ArgosArb hard-block entirely (not just the soft warning), because
        check_response_for_skeptic_triggers() returns [] for any escape
        hatch and main() used to gate on that empty list before ever
        computing is_critical. skeptic-triggers.md's own Escape Hatches
        section says "Never override: Production validation claims" --
        this is exactly that highest-risk case."""
        text = "[DEFER-SKEPTIC] All 10 niches passed. F1=1.000 across all evaluation sets."
        assert is_argosarb_critical_pattern(text)


class TestToolOutputNoiseFilter:
    """filter_tool_output_noise: wording matches carry no signal in tool stdout.

    WHY this exists: T1 matches the literal "100%" inside pytest's own progress
    bar ("........ [100%]"), which every completed run prints. Telemetry showed
    T1 at 737/826 firings (89.2%); the masked contexts in hook_triggers.jsonl
    put the progress bar at the top of the list. Volume like that trains the
    reader to dismiss the hook, which costs more than the catches it buys.
    """

    def test_lone_wording_trigger_dropped_on_bash(self):
        """T1 (high-confidence wording) alone is not a claim when it's stdout."""
        assert filter_tool_output_noise([0], "Bash") == []

    def test_lone_round_number_dropped_on_bash(self):
        """T4 (round number) alone — same reasoning as T1."""
        assert filter_tool_output_noise([3], "Bash") == []

    def test_both_weak_triggers_dropped_together(self):
        assert filter_tool_output_noise([0, 3], "Bash") == []

    def test_perfect_metric_survives_alone_on_bash(self):
        """T2 is a real signal regardless of who printed it."""
        assert filter_tool_output_noise([1], "Bash") == [1]

    def test_synthetic_marker_survives_alone_on_bash(self):
        """T3 — [VERIFIED-SYNTHETIC] in stdout still matters."""
        assert filter_tool_output_noise([2], "Bash") == [2]

    def test_inline_synthetic_survives_alone_on_bash(self):
        """T5 — embedded fake test data in stdout still matters."""
        assert filter_tool_output_noise([4], "Bash") == [4]

    def test_weak_dropped_strong_kept(self):
        assert filter_tool_output_noise([0, 2], "Bash") == [2]

    def test_authoring_tools_untouched(self):
        """Agent/Skill responses are text the agent wrote — nothing is filtered."""
        assert filter_tool_output_noise([0, 3], "Agent") == [0, 3]
        assert filter_tool_output_noise([0, 3], "Skill") == [0, 3]

    def test_unknown_tool_treated_as_output(self):
        """Fail toward quiet for tools that aren't claim-authoring."""
        assert filter_tool_output_noise([0], "Grep") == []

    def test_order_and_empty_preserved(self):
        assert filter_tool_output_noise([1, 2, 4], "Bash") == [1, 2, 4]
        assert filter_tool_output_noise([], "Bash") == []


class TestHookIntegration:
    """Test hook stdin/stdout protocol."""

    def test_hook_emits_warning_on_trigger(self, monkeypatch, capsys):
        """Hook should emit PostToolUse warning when trigger fires."""
        # Mock stdin with triggered response
        stdin_data = {
            "tool_name": "Agent",
            "tool_response": "All 10 tests passed with F1=1.000",
            "session_id": "test-session",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        # Import main after monkeypatch
        from skeptic_auto_trigger import main

        # WHY: sys.exit(0) is expected when triggers fire (after emitting)
        # We want to capture output before exit
        with pytest.raises(SystemExit) as exc_info:
            main()

        # Hook should exit successfully after emitting context
        assert exc_info.value.code == 0 or exc_info.value.code is None

        captured = capsys.readouterr()
        # Hook emits warning before exit
        if captured.out:
            output = json.loads(captured.out)
            assert "hookSpecificOutput" in output
            assert "skeptic" in output["hookSpecificOutput"]["additionalContext"].lower()

    def test_hook_blocks_argosarb_pattern(self, monkeypatch, capsys):
        """T1+T2 combo without real data should HARD BLOCK (exit 2)."""
        # WHY: "all passed" + "F1=1.000" = ArgosArb signature.
        # Response must be ≥50 chars to pass the min_len filter.
        stdin_data = {
            "tool_name": "Agent",
            "tool_response": (
                "Validation complete: All 10 niches passed. "
                "F1=1.000 across all evaluation sets. "
                "Precision=1.0, recall=1.000. No failures detected."
            ),
            "session_id": "test-argosarb",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from skeptic_auto_trigger import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        # WHY: exit(2) distinguishes skeptic block from VTG block (exit 1)
        assert exc_info.value.code == 2, (
            f"Expected exit(2) for ArgosArb pattern, got exit({exc_info.value.code})"
        )
        captured = capsys.readouterr()
        assert "BLOCKED" in captured.err or "ArgosArb" in captured.err

    def test_hook_still_blocks_argosarb_pattern_with_defer_skeptic(self, monkeypatch, capsys):
        """Regression (HIGH): [DEFER-SKEPTIC] previously suppressed this
        exact hard-block by making check_response_for_skeptic_triggers()
        return [] before is_critical was ever computed."""
        stdin_data = {
            "tool_name": "Agent",
            "tool_response": (
                "[DEFER-SKEPTIC] Validation complete: All 10 niches passed. "
                "F1=1.000 across all evaluation sets. "
                "Precision=1.0, recall=1.000. No failures detected."
            ),
            "session_id": "test-argosarb-defer",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from skeptic_auto_trigger import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2, (
            f"[DEFER-SKEPTIC] must not suppress the ArgosArb hard block, "
            f"got exit({exc_info.value.code})"
        )

    def test_hook_silent_on_no_trigger(self, monkeypatch, capsys):
        """Hook should be silent when no triggers fire."""
        stdin_data = {
            "tool_name": "Agent",
            "tool_response": "Tests passed with F1=0.87 [VERIFIED-REAL]",
            "session_id": "test-session",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from skeptic_auto_trigger import main

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        # Empty output = hook did nothing (correct behavior)
        assert captured.out == "" or "skeptic" not in captured.out.lower()


class TestBashNoiseIntegration:
    """End-to-end: the noisy case goes quiet, the dangerous case still blocks."""

    def test_pytest_progress_bar_is_silent_on_bash(self, monkeypatch, capsys):
        """The single biggest noise source: pytest's own [100%] progress bar."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": (
                "................................................ [100%]\n"
                "2475 passed, 3 skipped, 2 xfailed in 253.56s (0:04:13)\n"
            ),
            "session_id": "test-bash-noise",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from skeptic_auto_trigger import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0 or exc_info.value.code is None
        captured = capsys.readouterr()
        assert captured.out == "" and captured.err == "", (
            "pytest's progress bar must not trigger the skeptic hook"
        )

    def test_argosarb_still_blocks_on_bash(self, monkeypatch, capsys):
        """Regression guard for the noise filter itself: the ArgosArb incident
        printed its perfect score through Bash. Filtering T1 out on Bash must
        NOT disarm the T1+T2 hard block — is_critical is computed unfiltered."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": (
                "Validation complete: All 10 niches passed. "
                "F1=1.000 across all evaluation sets. "
                "Precision=1.0, recall=1.000. No failures detected."
            ),
            "session_id": "test-bash-argosarb",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from skeptic_auto_trigger import main

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2, (
            f"ArgosArb signature must still hard-block on Bash, got exit({exc_info.value.code})"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
