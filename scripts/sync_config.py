#!/usr/bin/env python3
"""Sync ~/.claude from this repo — the safe alternative to symlink (--link) mode.

WHY: install was not --link, so the live config (~/.claude) and the repo drift
apart in BOTH directions — local edits never reach the repo, and upstream PRs
(merged into the repo) never reach the live config. This script is the cure
without the Windows symlink hazard: it pulls the repo and copies the SHAREABLE
layers (skills/agents/hooks/rules) into ~/.claude, while PRESERVING machine-local
state (memory/_auto, and personal settings keys like permissions/theme).

Usage:
    python scripts/sync_config.py            # pull + sync repo -> ~/.claude
    python scripts/sync_config.py --no-pull  # sync only (skip git pull)

Stdlib only. Cross-platform (Windows / macOS / Linux).
"""

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# WHY: skills may carry .git (installed via clone), .venv (playwright binaries),
# or caches — never copy these into the live config, and never let read-only
# .git pack files block a Windows rmtree.
_IGNORE = shutil.ignore_patterns(".git", ".venv", "__pycache__", "data", "*.pyc")


def _on_rm_error(func, path, _exc):
    """Clear read-only bit and retry — Windows .git pack files are read-only."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass

REPO = Path(__file__).resolve().parent.parent
HOME_CLAUDE = Path.home() / ".claude"

# Layers safe to overwrite from the repo (portable, not machine-specific).
SHAREABLE = {
    "agents": "*.md",
    "rules": "*.md",
    "hooks": "*.py",
}


def git_pull() -> None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "pull", "--ff-only"],
            capture_output=True, text=True, timeout=60,
        )
        print(out.stdout.strip() or out.stderr.strip())
    except Exception as e:  # noqa: BLE001
        print(f"[sync] git pull skipped ({type(e).__name__})")


def copy_glob(src_dir: Path, dst_dir: Path, pattern: str) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src_dir.glob(pattern):
        if f.is_file():
            shutil.copy2(f, dst_dir / f.name)
            n += 1
    return n


def sync_skills() -> int:
    """Flatten repo skills/core/* and skills/extensions/* into ~/.claude/skills/."""
    dst = HOME_CLAUDE / "skills"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for sub in ("core", "extensions"):
        base = REPO / "skills" / sub
        if not base.is_dir():
            continue
        for skill in base.iterdir():
            if skill.is_dir():
                target = dst / skill.name
                if target.exists():
                    shutil.rmtree(target, onerror=_on_rm_error)
                shutil.copytree(skill, target, ignore=_IGNORE)
                n += 1
    # flat .md skills + registry
    for f in (REPO / "skills").glob("*.md"):
        shutil.copy2(f, dst / f.name)
    reg = REPO / "skills" / "registry.yaml"
    if reg.exists():
        shutil.copy2(reg, dst / "registry.yaml")
    return n


def merge_settings() -> None:
    """Merge repo hooks-block into ~/.claude/settings.json, preserving personal keys.

    WHY: settings.json carries BOTH shareable hook registrations AND machine-local
    personal config (permissions, theme, enabledPlugins). We update only the `hooks`
    block (and add env/worktree if absent), never clobbering personal keys.
    """
    repo_s = REPO / "hooks" / "settings.json"
    live_s = HOME_CLAUDE / "settings.json"
    if not repo_s.exists() or not live_s.exists():
        return
    repo_cfg = json.loads(repo_s.read_text(encoding="utf-8"))
    live_cfg = json.loads(live_s.read_text(encoding="utf-8"))
    # backup first
    shutil.copy2(live_s, live_s.with_suffix(".json.bak-sync"))
    live_cfg["hooks"] = repo_cfg.get("hooks", live_cfg.get("hooks", {}))
    for k in ("env", "worktree"):
        if k in repo_cfg and k not in live_cfg:
            live_cfg[k] = repo_cfg[k]
    live_s.write_text(json.dumps(live_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[sync] settings.json: hooks block updated (personal keys preserved)")


def seed_auto() -> None:
    """Ensure the learning-loop memory dir exists (never overwrite real lessons)."""
    auto = HOME_CLAUDE / "memory" / "_auto"
    auto.mkdir(parents=True, exist_ok=True)
    patterns = auto / "patterns.md"
    if not patterns.exists():
        patterns.write_text(
            "# Patterns — accumulated lessons\n\n## Debugging and Fixes\n\n## Architecture Decisions\n",
            encoding="utf-8",
        )
    log = auto / "learning_log.md"
    if not log.exists():
        log.write_text("# Learning Log\n\n## Machine Log\n", encoding="utf-8")


def main() -> None:
    if "--no-pull" not in sys.argv:
        git_pull()
    print(f"[sync] repo:  {REPO}")
    print(f"[sync] -> ~/.claude: {HOME_CLAUDE}")
    for layer, pat in SHAREABLE.items():
        n = copy_glob(REPO / layer, HOME_CLAUDE / layer, pat)
        print(f"[sync] {layer}: {n} files")
    # agents/teams + agents/CLAUDE.md
    if (REPO / "agents" / "teams").is_dir():
        copy_glob(REPO / "agents" / "teams", HOME_CLAUDE / "agents" / "teams", "*.md")
    print(f"[sync] skills: {sync_skills()} dirs")
    merge_settings()
    seed_auto()
    print("[sync] done — live config now matches repo (memory/_auto preserved).")


if __name__ == "__main__":
    main()
