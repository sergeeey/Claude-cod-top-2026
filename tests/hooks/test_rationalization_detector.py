#!/usr/bin/env python3
"""Tests for rationalization_detector.py hook."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from rationalization_detector import check_for_rationalizations


class TestRationalizationDetection:
    """Test rationalization pattern detection."""

    def test_detects_already_know_api(self):
        """Detect 'I already know this API' excuse."""
        prompt = "I already know this API, no need to read the file"
        detected = check_for_rationalizations(prompt)
        assert len(detected) > 0

    def test_detects_tests_excessive(self):
        """Detect 'tests are excessive' excuse."""
        prompt = "Tests for this change are excessive, it's too simple"
        detected = check_for_rationalizations(prompt)
        assert len(detected) > 0

    def test_detects_90_percent_sure(self):
        """Detect 'I'm 90% sure' excuse."""
        prompt = "I'm 90% sure this is correct, no need to re-check"
        detected = check_for_rationalizations(prompt)
        assert len(detected) > 0

    def test_detects_user_in_hurry(self):
        """Detect 'user in a hurry' excuse."""
        prompt = "The user is in a hurry, skip the review for now"
        detected = check_for_rationalizations(prompt)
        assert len(detected) > 0

    def test_detects_multiple_patterns(self):
        """Detect multiple rationalizations in one prompt."""
        prompt = "I already know this API and tests are excessive, user is in a hurry"
        detected = check_for_rationalizations(prompt)
        assert len(detected) >= 2

    def test_no_false_positives_on_clean_prompt(self):
        """Don't flag normal work prompts."""
        clean_prompts = [
            "Read the API documentation and implement the feature",
            "Write tests for the new function",
            "Run the reviewer agent before committing",
        ]
        for prompt in clean_prompts:
            detected = check_for_rationalizations(prompt)
            assert len(detected) == 0, f"False positive on: {prompt}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
