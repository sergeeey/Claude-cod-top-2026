#!/usr/bin/env python3
"""Copy P1 hooks from worktree to global hooks directory."""

import shutil
from pathlib import Path

HOOKS = ["null_results_pre_check", "promotion_gate_guard"]
GLOBAL_DIR = Path.home() / ".claude" / "hooks"

for name in HOOKS:
    src = Path("hooks") / f"{name}.py"
    dst = GLOBAL_DIR / f"{name}.py"
    shutil.copy2(src, dst)
    print(f"deployed {name}.py → {dst}")

print("Done.")
