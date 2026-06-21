#!/usr/bin/env python3
"""Check which referenced hooks exist only in global, not in worktree."""

import os

MISSING_FROM_WORKTREE = [
    "estimand_guard",
    "experiment_insight",
    "file_auto_parser",
    "pattern_escalation_review",
    "project_classifier",
]

GLOBAL = "C:/Users/serge/.claude/hooks"
WORKTREE = "hooks"

print("=== REFERENCED BUT MISSING FROM WORKTREE ===")
for h in MISSING_FROM_WORKTREE:
    fname = f"{h}.py"
    in_global = os.path.exists(f"{GLOBAL}/{fname}")
    in_worktree = os.path.exists(f"{WORKTREE}/{fname}")
    status = []
    if in_global:
        status.append("GLOBAL✓")
    else:
        status.append("GLOBAL✗")
    if in_worktree:
        status.append("WORKTREE✓")
    else:
        status.append("WORKTREE✗")
    print(f"  {h}: {' | '.join(status)}")

print()
print("=== NOT REGISTERED — check if they should be ===")
NOT_REGISTERED = ["cogniml_client", "learning_tips", "vector_store"]
for h in NOT_REGISTERED:
    fname = f"{h}.py"
    in_global = os.path.exists(f"{GLOBAL}/{fname}")
    print(f"  {h}: {'GLOBAL✓' if in_global else 'GLOBAL✗ (dev only)'}")

# Also check all global hooks not in worktree
print()
print("=== GLOBAL hooks NOT in worktree (installed but not tracked in git) ===")
global_hooks = {
    f.replace(".py", "") for f in os.listdir(GLOBAL) if f.endswith(".py") and f != "utils.py"
}
worktree_hooks = {
    f.replace(".py", "") for f in os.listdir(WORKTREE) if f.endswith(".py") and f != "utils.py"
}
global_only = global_hooks - worktree_hooks
for h in sorted(global_only):
    print(f"  - {h}")
