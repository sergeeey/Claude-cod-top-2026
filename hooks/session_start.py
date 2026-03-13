#!/usr/bin/env python3
"""SessionStart hook: output project context for Claude to consume.

POCHEMU: При старте/resume сессии Claude получает stdout этого скрипта
как контекст. Выводим activeContext.md + decisions.md проекта,
чтобы Claude не начинал "с чистого листа".
"""

import os
import subprocess
import sys
from pathlib import Path


CONFIG_REPO_MARKER = ".claude-code-config-repo"


def auto_update_config_repo():
    """If config was installed with --link, git pull the source repo.

    Detection: ~/.claude/.claude-code-config-repo contains repo path.
    """
    marker = Path.home() / ".claude" / CONFIG_REPO_MARKER
    if not marker.exists():
        return

    repo_path = marker.read_text(encoding="utf-8").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "pull", "--quiet", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"[SessionStart] Config updated from git: {result.stdout.strip()}")
        elif result.returncode != 0:
            # Silently ignore — network might be down
            pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def find_project_claude_dir() -> Path | None:
    """Walk up from CWD looking for .claude/memory/activeContext.md."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "memory" / "activeContext.md"
        if candidate.exists():
            return parent / ".claude" / "memory"
        # Also check if CLAUDE.md exists at this level (project root)
        if (parent / "CLAUDE.md").exists():
            claude_mem = parent / ".claude" / "memory"
            if claude_mem.exists():
                return claude_mem
    return None


def main():
    # Auto-update config repo if installed with --link
    auto_update_config_repo()

    mem_dir = find_project_claude_dir()
    if mem_dir is None:
        print("[SessionStart] No project .claude/memory/ found in path hierarchy.")
        return

    # Output active context
    active = mem_dir / "activeContext.md"
    if active.exists():
        print(f"=== PROJECT ACTIVE CONTEXT ({active}) ===")
        print(active.read_text(encoding="utf-8"))
        print("=== END ACTIVE CONTEXT ===\n")

    # Output decisions (compact)
    decisions = mem_dir / "decisions.md"
    if decisions.exists():
        content = decisions.read_text(encoding="utf-8")
        # Only output last 2000 chars to save context budget
        if len(content) > 2000:
            content = "...(truncated)...\n" + content[-2000:]
        print(f"=== PROJECT DECISIONS ({decisions}) ===")
        print(content)
        print("=== END DECISIONS ===\n")

    print(f"[SessionStart] Loaded project memory from {mem_dir.parent}")

    # Context Primer: reinforce key principles at session start
    print()
    print("[SessionStart] Routing Policy active. Before each task:")
    print("  1. Determine task type: research / code change / TDD / debug / security")
    print("  2. Follow route from routing-policy skill")
    print("  3. Evidence Policy: mark facts [VERIFIED]/[INFERRED]/[UNKNOWN]")
    print("  4. Hard Guards: Read before Edit, Local before MCP, Plan before 3+ files")


if __name__ == "__main__":
    main()
