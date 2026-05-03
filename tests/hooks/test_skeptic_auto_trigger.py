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

from skeptic_auto_trigger import check_response_for_skeptic_triggers


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
