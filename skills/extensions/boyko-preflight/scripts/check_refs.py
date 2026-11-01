#!/usr/bin/env python3
"""Find dead file references in an instruction file (CLAUDE.md, SKILL.md, AGENTS.md).

WHY: an instruction that points to a file that no longer exists tells the agent to
read nothing. claude-md-doctor (agent-clinic, verified 2026-11-01) checks dead
references as a basic health signal. This is the cheap version: backticked paths
ending in .md, .py, .json, .yaml, .yml or .sh are resolved and reported if missing.

Resolution order for a relative path: next to the instruction file, then in --base.
A leading ~ expands to the home directory. Tokens with spaces or wildcards are skipped.

Usage: python check_refs.py <file.md> [--base <dir>]
Exit code: 0 if every reference resolves, 1 if any is missing, 2 on usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXTENSIONS = (".md", ".py", ".json", ".yaml", ".yml", ".sh")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")


def candidate_refs(text: str) -> list[str]:
    """Backticked tokens that look like a file path to a known extension."""
    refs: list[str] = []
    for token in BACKTICK_RE.findall(text):
        token = token.strip()
        if not token.endswith(EXTENSIONS):
            continue
        if any(ch in token for ch in " *?<>|{}"):
            continue
        if "://" in token:
            continue
        refs.append(token)
    return refs


def resolves(ref: str, source_dir: Path, base: Path | None) -> bool:
    expanded = Path(ref).expanduser()
    if expanded.is_absolute():
        return expanded.exists()
    if (source_dir / expanded).exists():
        return True
    if base is None:
        return False
    if (base / expanded).exists():
        return True
    # WHY: a bare name such as `check_architecture.py` in prose is not a path. Accept it
    # if a file of that name exists anywhere under the base directory.
    if "/" not in ref:
        return any(base.rglob(ref))
    return False


def missing_refs(path: Path, base: Path | None) -> list[str]:
    text = path.read_text(encoding="utf-8")
    seen: list[str] = []
    for ref in candidate_refs(text):
        if ref in seen:
            continue
        if not resolves(ref, path.parent, base):
            seen.append(ref)
    return seen


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("Usage: python check_refs.py <file.md> [--base <dir>]")
        return 2

    target = Path(args[0])
    if not target.is_file():
        print(f"ERROR: {target} is not a file")
        return 2

    base: Path | None = None
    if "--base" in args:
        idx = args.index("--base")
        if idx + 1 >= len(args):
            print("ERROR: --base needs a directory")
            return 2
        base = Path(args[idx + 1])

    missing = missing_refs(target, base)
    print(f"=== check_refs: {target} ===")
    if missing:
        print(f"MISSING ({len(missing)}):")
        for ref in missing:
            print(f"  - {ref}")
        return 1
    print("OK. all file references resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
