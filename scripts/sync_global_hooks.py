#!/usr/bin/env python3
"""Copy global-only hooks into worktree hooks/ for git tracking.

Skips: example-hook (template), test_agent_context_filter (test helper).
"""

import os
import shutil

GLOBAL = "C:/Users/serge/.claude/hooks"
WORKTREE = "hooks"

SKIP = {"example-hook", "test_agent_context_filter"}

global_hooks = {
    f.replace(".py", ""): f
    for f in os.listdir(GLOBAL)
    if f.endswith(".py") and f not in ("utils.py",)
}
worktree_hooks = {f.replace(".py", "") for f in os.listdir(WORKTREE) if f.endswith(".py")}

global_only = set(global_hooks) - worktree_hooks - SKIP

print(f"Copying {len(global_only)} hooks:")
copied = []
for name in sorted(global_only):
    fname = global_hooks[name]
    src = f"{GLOBAL}/{fname}"
    dst = f"{WORKTREE}/{fname}"
    shutil.copy2(src, dst)
    copied.append(fname)
    print(f"  + {fname}")

print(f"\nDone. {len(copied)} files copied.")
