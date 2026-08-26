#!/usr/bin/env python3
"""Build a trigger-phrase -> skill-name index from personal SKILL.md files.

WHY this script exists: hooks/keyword_router.py's hand-curated KEYWORD_MAP
covers only 20 phrases -> 7 skills out of ~180 installed skills, because
maintaining a bigger map by hand doesn't scale and gets forgotten. 162 of
171 skills under ~/.claude/skills already declare a machine-readable
`triggers:` YAML field in their SKILL.md frontmatter -- this script turns
that into a lookup index keyword_router.py can load at runtime instead of
scanning 170+ files on every single user prompt.

WHY the output is NOT committed to this repo (D:\\Claude-cod-top-2026,
public GitHub): the only correct scan target is the LIVE, personal
~/.claude/skills catalog, which is a superset of this repo's own
skills/core + skills/extensions -- roughly 50 personal-only skills
(e.g. wealth-protocol) were deliberately never contributed here. Committing
their trigger phrases would leak private skill content into a public repo.
This repo's own .gitignore already draws exactly this line (excludes
skills/*/data/ as "local machine state, not committed"). The default output
path here follows the same convention: it writes into the user's private,
no-remote ~/.claude checkout, not into this repo's own hooks/data/.

WHY registry.yaml's own `triggers:` field is NOT used as an input: it is a
DIFFERENT, coarser trigger source meant for skill-manager.sh's install/search
flow, not for passive prompt-time suggestion. Sampled entries (e.g.
routing-policy: [task, implement, fix, debug, review, plan]) are exactly the
bare-dictionary-word noise this script's filter exists to keep out. Folding
it in later "for more coverage" would reintroduce that noise -- don't.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # types-PyYAML intentionally not a dep

DEFAULT_SKILLS_DIR = Path.home() / ".claude" / "skills"
DEFAULT_OUTPUT = Path.home() / ".claude" / "hooks" / "data" / "skill_trigger_index.json"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def extract_frontmatter(text: str) -> dict[str, Any] | None:
    """Parse the YAML frontmatter block from a SKILL.md file's raw text.

    Returns None if there is no well-formed --- ... --- block, or if the
    block does not parse as valid YAML (malformed frontmatter is real, not
    hypothetical -- ~/.claude/skills/analyst/SKILL.md has a stray quote that
    breaks its own triggers: line). Never raises.
    """
    match = _FRONTMATTER_RE.search(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def classify_trigger(trigger: str) -> str:
    """Classify a trigger phrase into a false-positive risk tier.

    - slash:            /skillname                       -- unambiguous
    - colon:             skeptic:                         -- de facto command form
    - hyphenated-bare:   agent-governance (no spaces)     -- compound identifier, low risk
    - phrase:            two or more words                -- needs word-boundary match
    - bare:               single plain word (e.g. "test") -- excluded unless hand-curated
    """
    t = trigger.strip()
    if t.startswith("/"):
        return "slash"
    if t.endswith(":") and t[:-1].replace("-", "").isalpha():
        return "colon"
    if " " in t or "\t" in t:
        return "phrase"
    if "-" in t:
        return "hyphenated-bare"
    return "bare"


def build_index(skills_dir: Path) -> dict[str, Any]:
    """Scan skills_dir/*/SKILL.md and build the flat entries list.

    Directories without a SKILL.md (eval workspace scratch dirs like
    orient-workspace/) are silently skipped -- they are not skills lacking
    a field, they are not skills at all.
    """
    entries: list[dict[str, str]] = []
    skipped: list[str] = []
    skill_count = 0

    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(skill_dir.name)
            continue

        frontmatter = extract_frontmatter(text)
        if frontmatter is None:
            skipped.append(skill_dir.name)
            continue

        name = frontmatter.get("name") or skill_dir.name
        triggers = frontmatter.get("triggers")
        if not isinstance(triggers, list) or not triggers:
            continue

        skill_count += 1
        for raw in triggers:
            trigger = str(raw).strip()
            if not trigger:
                continue
            entries.append(
                {"trigger": trigger, "skill": str(name), "kind": classify_trigger(trigger)}
            )

    return {
        "_meta": {
            "generated_from": str(skills_dir),
            "skill_count": skill_count,
            "trigger_count": len(entries),
            "skipped": sorted(skipped),
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="Directory containing one subdirectory per skill (default: ~/.claude/skills)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the JSON index (default: ~/.claude/hooks/data/...)",
    )
    args = parser.parse_args()

    if not args.skills_dir.is_dir():
        print(f"error: skills directory not found: {args.skills_dir}", file=sys.stderr)
        return 1

    index = build_index(args.skills_dir)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = index["_meta"]
    print(f"scanned {args.skills_dir}")
    print(f"  skills with usable triggers: {meta['skill_count']}")
    print(f"  total trigger entries: {meta['trigger_count']}")
    print(f"  skipped (no SKILL.md or malformed frontmatter): {len(meta['skipped'])}")
    if meta["skipped"]:
        print(f"    {', '.join(meta['skipped'])}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
