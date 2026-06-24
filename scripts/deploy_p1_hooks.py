#!/usr/bin/env python3
"""Copy P1 / research-methodology hooks from repo to global hooks directory.

Paths are resolved from __file__ so the script is cwd-independent (can be run
from any worktree). Idempotent — safe to re-run.
"""

import shutil
from pathlib import Path

HOOKS = [
    "null_results_pre_check",
    "promotion_gate_guard",
    "reject_gate_guard",  # NULL Exploitation Gate (gates REJECT)
    "null_retroscan",  # immediate retroscan of active PROMOTE on new NULL
]
REPO_HOOKS = Path(__file__).resolve().parent.parent / "hooks"
GLOBAL_DIR = Path.home() / ".claude" / "hooks"

for name in HOOKS:
    src = REPO_HOOKS / f"{name}.py"
    dst = GLOBAL_DIR / f"{name}.py"
    shutil.copy2(src, dst)
    print(f"deployed {name}.py -> {dst}")

print("Done.")
