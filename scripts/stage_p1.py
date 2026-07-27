#!/usr/bin/env python3
"""Stage P1 hook files for commit."""

import subprocess

FILES = [
    "hooks/null_results_pre_check.py",
    "hooks/promotion_gate_guard.py",
    "tests/test_null_results_pre_check.py",
    "tests/test_promotion_gate_guard.py",
    "scripts/deploy_p1_hooks.py",
    "scripts/lint_p1_hooks.py",
    "scripts/stage_p1.py",
]
r = subprocess.run(["git", "add"] + FILES, capture_output=True, text=True)
print(r.stdout or r.stderr or "staged")
s = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
print(s.stdout[:1000])
