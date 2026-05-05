#!/usr/bin/env python3
"""Tests for inline synthetic data detection in validation_theater_guard.

WHY: H3 from Sprint 1 — detect embedded test cases without function names.
From skeptic-triggers.md:56-65.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from validation_theater_guard import SYNTHETIC_DATA_PATTERNS


class TestInlineSyntheticDetection:
    """Test patterns detect inline synthetic data."""

    def test_detects_embedded_list_of_tuples(self):
        """Detect abstracts = [("text", "LABEL")] pattern."""
        code = """
        abstracts = [
            ("example 1", "LABEL"),
            ("example 2", "LABEL")
        ]
        """
        matches = [p for p in SYNTHETIC_DATA_PATTERNS if p.search(code)]
        assert len(matches) > 0, "Should detect embedded tuple list"

    def test_detects_embedded_dict(self):
        """Detect test_data = {"input": ..., "expected": ...} pattern."""
        code = """
        test_data = {
            "input": "sample text",
            "expected": "LABEL"
        }
        """
        matches = [p for p in SYNTHETIC_DATA_PATTERNS if p.search(code)]
        assert len(matches) > 0, "Should detect embedded dict"

    def test_detects_embedded_string_list(self):
        """Detect examples = ["text 1", "text 2"] pattern."""
        code = """
        examples = [
            "text 1",
            "text 2",
            "text 3"
        ]
        """
        matches = [p for p in SYNTHETIC_DATA_PATTERNS if p.search(code)]
        assert len(matches) > 0, "Should detect embedded string list"

    def test_does_not_detect_real_data_loading(self):
        """Don't flag real data loading patterns."""
        real_data_code = [
            'response = requests.get("https://api.nih.gov/grants")',
            'df = pd.read_csv("real_data.csv")',
            'with open("data.json") as f: data = json.load(f)',
        ]
        for code in real_data_code:
            matches = [p for p in SYNTHETIC_DATA_PATTERNS if p.search(code)]
            assert len(matches) == 0, f"Should NOT flag real data: {code}"

    def test_combined_realistic_validator(self):
        """Real-world validator with inline synthetic should be detected."""
        validator_code = """
def test_classifier():
    # Inline test cases (synthetic)
    test_cases = [
        ("This is fraud", "FRAUD"),
        ("Normal transaction", "CLEAN"),
    ]
    for text, expected in test_cases:
        result = classify(text)
        assert result == expected
        """
        matches = [p for p in SYNTHETIC_DATA_PATTERNS if p.search(validator_code)]
        assert len(matches) > 0, "Should detect inline synthetic in realistic code"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
