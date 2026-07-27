#!/usr/bin/env python3
"""Lint all P1 hook and test files."""

import subprocess
import sys

files = [
    "hooks/null_results_pre_check.py",
    "hooks/promotion_gate_guard.py",
    "tests/test_null_results_pre_check.py",
    "tests/test_promotion_gate_guard.py",
]
r = subprocess.run(
    ["python", "-m", "ruff", "check", "--output-format", "concise"] + files,
    capture_output=True,
    text=True,
)
print(r.stdout or r.stderr or "All clean!")
sys.exit(r.returncode)
