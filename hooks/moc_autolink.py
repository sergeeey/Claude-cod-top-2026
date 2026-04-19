#!/usr/bin/env python3
"""Post-tool hook: auto-link new notes to relevant MOCs.

Triggers: after Write/Edit to ~/.claude/memory/
Routes notes to MOC based on tags and content keywords.
"""

import json
import re
import sys
from pathlib import Path

# Tag → MOC mapping
MOC_MAP = {
    "claude-code": "mocs/Claude-cod-top-2026 MOC.md",
    "hooks": "mocs/Claude-cod-top-2026 MOC.md",
    "agents": "mocs/AI-Era Engineering MOC.md",
    "archcode": "mocs/Research Science MOC.md",
    "genomics": "mocs/Research Science MOC.md",
    "geomiro": "mocs/GeoMiro MOC.md",
    "geopolitical": "mocs/GeoMiro MOC.md",
    "security": "mocs/Security MOC.md",
    "pentest": "mocs/Security MOC.md",
    "solo-founding": "mocs/Solo Founding MOC.md",
    "startup": "mocs/Solo Founding MOC.md",
}


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only process .claude/memory/ writes
    if ".claude/memory" not in file_path:
        sys.exit(0)

    # Skip auto-generated and indices
    if any(x in file_path for x in ["_auto/", "index.md", "mocs/"]):
        sys.exit(0)

    memory_root = Path.home() / ".claude" / "memory"
    note_path = Path(file_path)

    if not note_path.exists():
        sys.exit(0)

    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception:
        sys.exit(0)

    # Extract tags
    tags = re.findall(r"#(\w+)", content)
    if not tags:
        sys.exit(0)

    # Find relevant MOCs
    mocs_to_update = set()
    for tag in tags:
        if tag.lower() in MOC_MAP:
            mocs_to_update.add(MOC_MAP[tag.lower()])

    if not mocs_to_update:
        sys.exit(0)

    # Get note title
    title = note_path.stem.replace("_", " ").replace("-", " ")
    wikilink = f"[[{note_path.relative_to(memory_root).as_posix()}|{title}]]"

    # Update each MOC
    for moc_rel_path in mocs_to_update:
        moc_path = memory_root / moc_rel_path
        if not moc_path.exists():
            continue

        try:
            moc_content = moc_path.read_text(encoding="utf-8")
            # Check if already linked
            if str(note_path.stem) in moc_content:
                continue

            # Find "## Recent" or "## New" section, add link
            if "## Recent" in moc_content:
                moc_content = moc_content.replace("## Recent\n", f"## Recent\n\n- {wikilink}\n")
            elif "## New" in moc_content:
                moc_content = moc_content.replace("## New\n", f"## New\n\n- {wikilink}\n")
            else:
                # Append at end
                moc_content += f"\n\n## Recent\n\n- {wikilink}\n"

            moc_path.write_text(moc_content, encoding="utf-8")
        except Exception:
            continue

    sys.exit(0)


if __name__ == "__main__":
    main()
