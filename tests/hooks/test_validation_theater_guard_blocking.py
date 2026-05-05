#!/usr/bin/env python3
"""Tests for validation_theater_guard.py blocking mode.

WHY: H2 from Sprint 1 — add hard blocking for critical validation theater.
Perfect score + synthetic data simultaneously = highest risk case.
"""

import json
import sys
from io import StringIO
from pathlib import Path

import pytest

# Add hooks to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))

from validation_theater_guard import should_block_validation


class TestBlockingLogic:
    """Test blocking decision logic."""

    def test_block_perfect_score_plus_synthetic(self):
        """Block when perfect score AND synthetic data in same output."""
        # WHY: ArgosArb incident — F1=1.000 on synthetic data
        outputs = [
            "F1=1.000 [VERIFIED-SYNTHETIC] on create_synthetic_dataset()",
            "All 10 tests passed. Using mock_data for validation.",
            "precision=1.000, recall=1.000 on SYNTHETIC_CASES",
            "100% success rate (synthetic test data)",
        ]
        for output in outputs:
            assert should_block_validation(output), f"Should block: {output}"

    def test_no_block_perfect_score_real_data(self):
        """Don't block perfect score if marked [VERIFIED-REAL]."""
        outputs = [
            "F1=1.000 [VERIFIED-REAL] on production logs from S3",
            "All tests passed using real customer data",
            "100% accuracy on external benchmark dataset (URL: https://...)",
        ]
        for output in outputs:
            assert not should_block_validation(output), f"Should NOT block: {output}"

    def test_no_block_synthetic_without_perfect_score(self):
        """Don't block synthetic data if score is realistic."""
        outputs = [
            "F1=0.87 [VERIFIED-SYNTHETIC] for unit test",
            "75% passed on mock_data (expected for edge cases)",
            "create_synthetic_dataset() → F1=0.64",
        ]
        for output in outputs:
            assert not should_block_validation(output), f"Should NOT block: {output}"

    def test_no_block_imperfect_score(self):
        """Don't block realistic scores even without [VERIFIED-REAL]."""
        outputs = [
            "F1=0.95 on test set",
            "98% of cases passed",
            "precision=0.987, recall=0.912",
        ]
        for output in outputs:
            assert not should_block_validation(output), f"Should NOT block: {output}"


class TestBlockingIntegration:
    """Test hook integration with blocking."""

    def test_hook_blocks_critical_case(self, monkeypatch):
        """Hook should exit(1) on critical validation theater."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": {"output": "Validation complete: F1=1.000 on synthetic_cases"},
            "session_id": "test",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from validation_theater_guard import main

        # WHY: sys.exit(1) should raise SystemExit with code 1
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1, "Should exit with code 1 (block)"

    def test_hook_warns_non_critical_case(self, monkeypatch, capsys):
        """Hook should warn (not block) on perfect score alone."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": {
                "output": "F1=1.000 on test dataset (source not specified, length >50 chars to trigger warning)"
            },
            "session_id": "test",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from validation_theater_guard import main

        # Hook should complete normally (no blocking exit(1))
        # May or may not call sys.exit(0) — that's implementation detail
        try:
            main()
        except SystemExit as e:
            # If exit called, should be 0 (not blocking)
            assert e.code == 0 or e.code is None, f"Should not block, got exit({e.code})"

        captured = capsys.readouterr()
        assert "Perfect score" in captured.out, "Should warn about perfect score"

    def test_hook_silent_on_real_data(self, monkeypatch, capsys):
        """Hook should be silent when [VERIFIED-REAL] present."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_response": {"output": "F1=0.87 [VERIFIED-REAL] on production dataset"},
            "session_id": "test",
        }
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(stdin_data)))

        from validation_theater_guard import main

        # Hook should complete normally (may or may not exit)
        try:
            main()
        except SystemExit as e:
            # If exit called, should be 0
            assert e.code == 0 or e.code is None

        captured = capsys.readouterr()
        assert captured.out == "" or "validation-theater" not in captured.out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
