#!/usr/bin/env python3
"""Copy methodology-stack hooks from repo to global hooks directory.

Paths resolved from __file__ so the script is cwd-independent. Idempotent.
"""

import shutil
from pathlib import Path

HOOKS = [
    "null_results_pre_check",
    "promotion_gate_guard",
    "reject_gate_guard",  # NULL Exploitation Gate (gates REJECT)
    "null_retroscan",  # retroscan active PROMOTE on new NULL
    "weakened_test_guard",  # detect tests weakened to force a pass
    "commit_test_gate",  # warn on commit of untested source changes
    "iteration_guard",  # enforce Evaluator-Optimizer cap=3
]
REPO_HOOKS = Path(__file__).resolve().parent.parent / "hooks"
GLOBAL_DIR = Path.home() / ".claude" / "hooks"

for name in HOOKS:
    src = REPO_HOOKS / f"{name}.py"
    if not src.exists():
        print(f"SKIP {name}.py (not in this worktree)")
        continue
    shutil.copy2(src, GLOBAL_DIR / f"{name}.py")
    print(f"deployed {name}.py -> {GLOBAL_DIR / f'{name}.py'}")

print("Done.")
