#!/usr/bin/env python3
"""One-shot: add triggers: field to SKILL.md files missing it.

Strategy:
1. If description/BSV has "Triggers:" or "Триггеры:" → extract those keywords
2. Fallback: generate from name + key nouns in description first sentence
"""

import glob
import re
import sys
from pathlib import Path


def extract_trigger_text(text: str) -> list[str]:
    """Find Triggers: or Триггеры: line and parse comma-separated keywords."""
    m = re.search(
        r"(?:Triggers?|Триггеры?)\s*:\s*(.+?)(?:\n\n|\.\s|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if not m:
        return []
    raw = m.group(1).replace("\n", " ").strip()
    items = [t.strip().strip('"').strip("'").strip(",").strip() for t in raw.split(",")]
    items = [t for t in items if t and len(t) < 60 and not t.startswith("#")]
    return items[:12]


def name_to_triggers(name: str, description: str) -> list[str]:
    """Generate minimal triggers from skill name and description."""
    triggers = [name]
    # Add slash version if name has dashes (slash command)
    if "-" in name or "_" in name:
        triggers.append("/" + name)
    # Add words from name
    words = re.split(r"[-_]", name)
    if len(words) > 1:
        triggers.extend(words[:3])

    # Extract key nouns from first sentence of description
    first_sentence = re.split(r"\.\s", description)[0] if description else ""
    # Find capitalized or slash-prefixed words that look like keywords
    kws = re.findall(r"/[\w-]+|[A-Z][a-z]{3,}|[а-яА-Я]{5,}", first_sentence)
    triggers.extend(kws[:5])

    # Deduplicate while preserving order
    seen: set[str] = set()
    result = []
    for t in triggers:
        t = t.strip()
        if t and t.lower() not in seen and len(t) < 60:
            seen.add(t.lower())
            result.append(t)
    return result[:10]


def format_triggers(items: list[str]) -> str:
    inner = ", ".join(f'"{t}"' if (" " in t or "," in t) else t for t in items)
    return f"triggers: [{inner}]"


def process_file(filepath: str, dry_run: bool = False) -> str:
    """Add triggers: to frontmatter. Returns 'added', 'skipped', or 'error'."""
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "error"

    # Already has triggers in frontmatter
    if re.search(r"^triggers:", text, re.MULTILINE):
        return "skipped"

    # Find frontmatter block
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "error"  # No valid frontmatter

    _, fm_block, body = parts

    # Extract name from frontmatter, BSV comment, or directory name
    name_m = re.search(r"^name:\s*['\"]?(.+?)['\"]?\s*$", fm_block, re.MULTILINE)
    if name_m:
        name = name_m.group(1).strip()
    else:
        # Try BSV comment "Скил   : name"
        bsv_m = re.search(r"Скил\s*:\s*(.+)", text)
        if bsv_m:
            name = bsv_m.group(1).strip()
        else:
            # Fall back to parent directory name
            name = Path(filepath).parent.name

    # Extract description from frontmatter
    desc_m = re.search(
        r"^description:\s*[>|]?\s*\n?(.*?)(?=\n\w|\Z)", fm_block, re.MULTILINE | re.DOTALL
    )
    description = desc_m.group(1).strip() if desc_m else ""

    # Try to extract triggers from text
    triggers = extract_trigger_text(text)

    if not triggers:
        triggers = name_to_triggers(name, description)

    if not triggers:
        return "error"

    trigger_line = format_triggers(triggers)

    # Insert before closing --- of frontmatter
    new_fm = fm_block.rstrip() + f"\n{trigger_line}\n"
    new_text = "---" + new_fm + "---" + body

    if not dry_run:
        Path(filepath).write_text(new_text, encoding="utf-8")

    return "added"


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    # WHY Path.home() and not a hardcoded drive letter (found 2026-09-11
    # while wiring this script's output into install.sh -- see that file's
    # own WHY note on install_extension_skills): this file is committed to a
    # public repo, and the previous literal "C:/Users/serge/.claude/skills"
    # only ever matched one specific user's one specific machine. On any
    # other machine (a different Windows user, macOS, Linux, or CI) the glob
    # silently matched zero files -- "added=0 skipped=0 errors=0" looks
    # identical to "ran correctly, nothing to do" and identical to "path is
    # wrong for this user," so the bug had no way to surface on its own.
    # Path.home() resolves correctly on every platform and preserves the
    # exact behavior on the machine this was written for (Path.home() ==
    # C:\Users\serge for that user's own account).
    skills_dir = Path.home() / ".claude" / "skills"
    skill_files = sorted(glob.glob(str(skills_dir / "**" / "*.md"), recursive=True))
    skill_files = [f for f in skill_files if f.endswith("SKILL.md")]

    counts = {"added": 0, "skipped": 0, "error": 0}
    for filepath in skill_files:
        result = process_file(filepath, dry_run=dry_run)
        counts[result] += 1
        if result == "error":
            print(f"  ERROR: {filepath}")

    mode = "DRY RUN" if dry_run else "APPLIED"
    print(
        f"\n[{mode}] added={counts['added']} skipped={counts['skipped']} errors={counts['error']}"
    )


if __name__ == "__main__":
    main()
