#!/usr/bin/env python3
"""SessionStart hook: output project context for Claude to consume.

WHY: On session start/resume Claude receives stdout from this script
as context. We output the project activeContext.md + decisions.md,
so Claude does not start from scratch.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

# WHY: find_project_claude_dir, find_scope_fence, parse_scope_fence moved
# to utils.py as shared utilities — removing duplication between session_start and drift_guard.
from utils import find_project_claude_dir, find_scope_fence, parse_scope_fence
from learning_tips import LEARNING_LOG_PATH, select_tip

# ── Learning tip colours ──────────────────────────────────────────────────────
_Y = "\033[93m"  # bright yellow
_B = "\033[1m"  # bold
_R = "\033[0m"  # reset
_BOX_W = 68

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
            ["git", "-C", repo_path, "pull", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and "Already up to date" not in output:
                print(f"[SessionStart] Config updated: {output}")
        else:
            # Log to stderr (not visible to Claude, but useful for debugging)
            print(
                f"[SessionStart] Config auto-update skipped: {result.stderr.strip()}",
                file=sys.stderr,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def print_scope_fence():
    """Print Scope Fence status at session start."""
    fence_source = find_scope_fence()

    if fence_source is None:
        print(
            "\n[SessionStart] No Scope Fence found. "
            "Create .scope-fence.md in project root or add ## Scope Fence to activeContext.md."
        )
        return

    # WHY: parse_scope_fence from utils encapsulates parsing — no logic duplication here.
    fence = parse_scope_fence(fence_source.read_text(encoding="utf-8"))
    fence_goal = fence.get("goal", "")
    fence_not_now = fence.get("not_now", "")

    if fence_goal and not fence_goal.startswith("{{"):
        source_label = fence_source.name
        print(f"\n[SessionStart] Scope Fence active (from {source_label}).")
        print(f"  Goal: {fence_goal}")
        if fence_not_now and not fence_not_now.startswith("{{"):
            print(f"  NOT NOW: {fence_not_now}")
    else:
        print(
            "\n[SessionStart] No Scope Fence found. "
            "Add ## Scope Fence to .scope-fence.md (universal) or activeContext.md "
            "(Goal, Boundary, Done when, NOT NOW) to stay focused."
        )


FIRST_RUN_MARKER = ".first-run"


def check_first_run():
    """Show welcome message on first session after install, then remove marker."""
    marker = Path.home() / ".claude" / FIRST_RUN_MARKER
    if not marker.exists():
        return

    # WHY: delete marker first so it only fires once, even if session crashes.
    marker.unlink()

    rules_dir = Path.home() / ".claude" / "rules"
    hooks_dir = Path.home() / ".claude" / "hooks"
    skills_dir = Path.home() / ".claude" / "skills"

    rules = sorted(f.stem for f in rules_dir.glob("*.md")) if rules_dir.is_dir() else []
    hooks = (
        sorted(f.stem for f in hooks_dir.glob("*.py") if f.stem != "__init__" and f.stem != "utils")
        if hooks_dir.is_dir()
        else []
    )
    skills_core = (
        sorted(d.name for d in (skills_dir / "core").iterdir() if d.is_dir())
        if (skills_dir / "core").is_dir()
        else []
    )

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         Claude Code Config — installed successfully!        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    if rules:
        print(f"  Rules ({len(rules)}):  {', '.join(rules)}")
    if hooks:
        print(f"  Hooks ({len(hooks)}):  {len(hooks)} Python guards active")
    if skills_core:
        print(f"  Skills ({len(skills_core)}): {', '.join(skills_core)}")
    print()
    print("  How it works:")
    print("  • Evidence Policy — every claim tagged [VERIFIED]/[INFERRED]/[UNKNOWN]")
    print("  • Hooks run 100% deterministically (0 tokens, can't be ignored)")
    print("  • Skills activate by keyword (e.g. say 'tests' → TDD workflow)")
    print()
    print("  Quick start:")
    print("  • Just work normally — the config enhances Claude automatically")
    print("  • Edit ~/.claude/CLAUDE.md IDENTITY section to customize for yourself")
    print("  • See docs/troubleshooting.md if something feels off")
    print()


def _box_line_ss(content: str = "") -> str:
    inner = _BOX_W - 4
    return f"│ {content:<{inner}} │"


def print_learning_tip() -> None:
    """Show one yellow learning tip at session start.

    WHY: Each session is a learning opportunity. We read learning_log.md
    to pick the next unseen Claude Code tip and show it in bright yellow
    so it stands out from the normal context output.
    """
    try:
        log_content = ""
        if LEARNING_LOG_PATH.exists():
            log_content = LEARNING_LOG_PATH.read_text(encoding="utf-8")

        tip = select_tip(log_content, "other")
        inner = _BOX_W - 4

        lines = [
            "┌" + "─" * (_BOX_W - 2) + "┐",
            _box_line_ss(f"🎓 ИЗУЧАЕМ CLAUDE CODE  [Level {tip['level']} · {tip['tag']}]"),
            _box_line_ss("─" * (_BOX_W - 6)),
        ]
        for paragraph in tip["text"].split("\n"):
            for wrapped in textwrap.wrap(paragraph, inner) or [""]:
                lines.append(_box_line_ss(wrapped))
        lines.append(_box_line_ss())
        lines.append(_box_line_ss("▶ Попробуй:"))
        for wrapped in textwrap.wrap(tip["next_try"], inner):
            lines.append(_box_line_ss(f"  {wrapped}"))
        lines.append("└" + "─" * (_BOX_W - 2) + "┘")

        box = "\n".join(lines)
        print(f"\n{_Y}{_B}{box}{_R}\n")
    except Exception:
        pass  # WHY: never crash session start due to learning tip failure


def main():
    # First-run welcome (fires once after install)
    check_first_run()

    # Learning tip — yellow box, stands out from context
    print_learning_tip()

    # Auto-update config repo if installed with --link
    auto_update_config_repo()

    mem_dir = find_project_claude_dir()

    # Output project memory if available
    if mem_dir is not None:
        active = mem_dir / "activeContext.md"
        if active.exists():
            print(f"=== PROJECT ACTIVE CONTEXT ({active}) ===")
            print(active.read_text(encoding="utf-8"))
            print("=== END ACTIVE CONTEXT ===\n")

        decisions = mem_dir / "decisions.md"
        if decisions.exists():
            content = decisions.read_text(encoding="utf-8")
            if len(content) > 2000:
                content = "...(truncated)...\n" + content[-2000:]
            print(f"=== PROJECT DECISIONS ({decisions}) ===")
            print(content)
            print("=== END DECISIONS ===\n")

        print(f"[SessionStart] Loaded project memory from {mem_dir.parent}")
    else:
        print("[SessionStart] No project .claude/memory/ found in path hierarchy.")

    # Scope Fence: always check, even without .claude/memory/
    print_scope_fence()

    # Context Primer: reinforce key principles at session start
    print()
    print("[SessionStart] Routing Policy active. Before each task:")
    print("  1. Determine task type: research / code change / TDD / debug / security")
    print("  2. Follow route from routing-policy skill")
    print("  3. Evidence Policy: mark facts [VERIFIED]/[INFERRED]/[UNKNOWN]")
    print("  4. Hard Guards: Read before Edit, Local before MCP, Plan before 3+ files")


if __name__ == "__main__":
    main()
