#!/usr/bin/env python3
"""SessionStart hook: warn when the LIVE ~/.claude/hooks install has drifted
away from this repo's own hooks/ directory.

WHY (2026-09-01, Tracy strategic pass -> Critical Path item #1): this repo's
own CLAUDE.md documents the gap in prose ("a hook fixed here isn't live
until reinstalled/redeployed... several bugs this project has hit were
exactly this") but nothing ever mechanically checked for it. Confirmed the
same day, concretely: mcp_circuit_breaker.py/mcp_circuit_breaker_post.py
were fixed and merged (PR #296), yet the live ~/.claude/hooks copy on this
machine still ran the buggy version until someone happened to notice by
hand. This hook is the mechanization of that check -- it would have caught
that exact drift at the next session start.

Scope: only meaningful when the CURRENT working directory IS this repo
(hooks/registry.yaml + skills/registry.yaml both present) -- comparing
hashes only makes sense against the repo that produced the live install.
Silent no-op everywhere else, including a machine where CLAUDE_HOME was
never installed from this repo at all.

Deliberately NOT a promotion gate: read-only, warns via stdout (the
SessionStart additionalContext channel, matching estimand_guard.py's own
pattern), never blocks, never writes inside the repo. Autonomy Budget:
Green tier (read-only, 0 project files changed) per
.claude/rules/autonomy-budget.md.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

# WHY 8s ceiling, not "as long as it takes": autonomy-budget.md caps every
# SessionStart hook's wall-clock at 8s. Hashing ~100 small .py files is a
# few ms in practice; this is a hard stop against a slow/networked
# CLAUDE_HOME (e.g. a synced drive) turning a cheap check into a stall.
_MAX_FILES = 500


def is_this_repo(root: Path) -> bool:
    return (root / "hooks" / "registry.yaml").is_file() and (
        root / "skills" / "registry.yaml"
    ).is_file()


def resolve_claude_home() -> Path | None:
    env = os.environ.get("CLAUDE_HOME") or os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        candidate = Path(env)
        return candidate if candidate.is_dir() else None
    candidate = Path.home() / ".claude"
    return candidate if candidate.is_dir() else None


def sha256_of(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def find_drift(repo_hooks: Path, live_hooks: Path) -> list[str]:
    """Return relative paths present in BOTH trees whose content differs.

    WHY "present in both" only: a file that exists in the repo but was never
    installed (e.g. a brand-new hook not yet deployed) is an outstanding
    deploy step, not drift -- and a file only in the live tree may be a
    personal, non-repo hook (this repo's own CLAUDE.md documents exactly
    this case for personal-only consumers). Neither is this hook's concern.
    """
    drifted = []
    count = 0
    for repo_file in repo_hooks.rglob("*.py"):
        if "__pycache__" in repo_file.parts:
            continue
        count += 1
        if count > _MAX_FILES:
            break
        rel = repo_file.relative_to(repo_hooks)
        live_file = live_hooks / rel
        if not live_file.is_file():
            continue
        repo_hash = sha256_of(repo_file)
        live_hash = sha256_of(live_file)
        if repo_hash is not None and live_hash is not None and repo_hash != live_hash:
            drifted.append(str(rel))
    return drifted


def main() -> None:
    try:
        root = Path.cwd()
        if not is_this_repo(root):
            return
        claude_home = resolve_claude_home()
        if claude_home is None:
            return
        live_hooks = claude_home / "hooks"
        if not live_hooks.is_dir():
            return
        repo_hooks = root / "hooks"
        # WHY same-path check: a --link install (symlinks) or --target
        # pointing straight at this repo's own hooks/ makes drift
        # structurally impossible -- comparing a directory to itself would
        # only ever report zero drift, so skip the walk entirely.
        try:
            if live_hooks.resolve() == repo_hooks.resolve():
                return
        except OSError:
            pass

        drifted = find_drift(repo_hooks, live_hooks)
        if drifted:
            shown = drifted[:10]
            more = len(drifted) - len(shown)
            lines = "\n  ".join(shown)
            suffix = f"\n  ... and {more} more" if more > 0 else ""
            print(
                "[live-drift-guard] Live ~/.claude/hooks differs from this repo's "
                f"HEAD for {len(drifted)} file(s) -- a fix merged here isn't live "
                "until redeployed:\n  " + lines + suffix
            )
    except Exception as e:  # never block session start
        print(f"[live-drift-guard] skipped ({type(e).__name__})", file=sys.stderr)


if __name__ == "__main__":
    main()
