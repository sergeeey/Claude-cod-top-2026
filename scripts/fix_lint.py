#!/usr/bin/env python3
"""Auto-fix lint in synced hooks."""

import subprocess
import sys

FILES = [
    "hooks/hook_observability.py",
    "hooks/hypothesis_router.py",
    "hooks/markitdown_auto_convert.py",
    "hooks/pre_vault_write.py",
]

result = subprocess.run(
    [sys.executable, "-m", "ruff", "check", "--fix", "--select", "I,F,E"] + FILES,
    capture_output=True,
    text=True,
)
print(result.stdout or "(fixed)")
if result.stderr:
    print(result.stderr)
print(f"Exit: {result.returncode}")
