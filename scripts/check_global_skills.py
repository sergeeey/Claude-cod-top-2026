#!/usr/bin/env python3
"""Check which repo skills are reachable from the global flat skill directory.

WHY: merging a skill to this repo's main does NOT make it invocable in other
projects -- Claude Code discovers global skills flat under
~/.claude/skills/<name>/, not nested under core/extensions/ the way this
repo organizes them. install.sh's own sync_global_skills() targets the wrong
(nested) path -- verified 2026-07-17 against a known-working skill
(boyko-knowledge-audit exists only flat, never under extensions/). This
script is the manual (non-CI; CI runners don't have the user's personal
~/.claude/) equivalent of tests/test_structure.py's registry<->disk gates,
but for the repo<->global boundary specifically.

Usage: python scripts/check_global_skills.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    print("PyYAML required: pip install pyyaml")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
GLOBAL_SKILLS = Path.home() / ".claude" / "skills"


def main() -> None:
    registry = yaml.safe_load((ROOT / "skills" / "registry.yaml").read_text(encoding="utf-8"))

    deployed: list[str] = []
    missing: list[tuple[str, str]] = []  # (name, suggested cp command)
    skipped: list[str] = []

    for section in ("core", "extensions"):
        for entry in registry.get(section) or []:
            name = entry["name"]
            entry_type = entry.get("type", "directory")

            if entry_type == "external":
                skipped.append(f"{name} (external git-clone skill, no local artifact expected)")
                continue

            if entry_type == "file":
                repo_path = ROOT / "skills" / section / f"{name}.md"
                global_path = GLOBAL_SKILLS / f"{name}.md"
            else:
                repo_path = ROOT / "skills" / section / name
                global_path = GLOBAL_SKILLS / name

            if not repo_path.exists():
                continue  # covered by tests/test_structure.py's own ghost-entry gate

            if global_path.exists():
                deployed.append(name)
            else:
                if entry_type == "file":
                    cmd = f'cp "{repo_path}" "{global_path}"'
                else:
                    cmd = f'cp -r "{repo_path}" "{global_path}"'
                missing.append((name, cmd))

    print("=== Global skill deployment check ===")
    print(f"Registry: {len(deployed) + len(missing)} deployable entries checked")
    print(f"Deployed globally: {len(deployed)}")
    print(f"Skipped (external/community, no local deploy expected): {len(skipped)}")
    print()

    if missing:
        print(f"NOT deployed globally ({len(missing)}) -- not invocable from other projects yet:")
        for name, cmd in missing:
            print(f"  - {name}")
            print(f"      {cmd}")
        print()
        print("Note: do NOT run `install.sh --sync-global-skills` to fix this -- it targets")
        print("~/.claude/skills/extensions/, which is not where Claude Code actually looks.")
        print("See project memory (project_skills_global_deploy.md) for the full finding.")
        sys.exit(1)

    print("All repo skills are deployed globally.")


if __name__ == "__main__":
    main()
