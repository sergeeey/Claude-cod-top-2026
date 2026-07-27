#!/usr/bin/env python3
"""Lint the two P1 hooks."""

import subprocess
import sys

files = [
    "hooks/null_results_pre_check.py",
    "hooks/promotion_gate_guard.py",
]
result = subprocess.run(
    ["python", "-m", "ruff", "check", "--output-format", "concise"] + files,
    capture_output=True,
    text=True,
)
print(result.stdout or result.stderr or "All clean!")
sys.exit(result.returncode)
