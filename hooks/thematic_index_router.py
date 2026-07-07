#!/usr/bin/env python3
"""Session end hook: route new wiki entries to thematic indices.

Routes:
- git commits, hooks, skills → Claude-Code.index.md
- postmortems, lessons, [AVOID] → Lessons.index.md
- project retrospectives → Projects.index.md
"""

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from utils import file_lock


def route_entry(title: str, tags: list[str], content: str) -> str | None:
    """Determine which thematic index should receive this entry."""
    tags_lower = {t.lower() for t in tags}

    # Lessons index
    if tags_lower & {"avoid", "postmortem", "lesson", "archcode", "pattern"}:
        return "Lessons.index.md"
    if any(marker in content for marker in ["[AVOID]", "[REPEAT]", "постмортем"]):
        return "Lessons.index.md"

    # Projects index
    project_tags = {"reflexio", "geoscan", "terag", "geomiro", "verifind", "cogniml"}
    if tags_lower & project_tags:
        return "Projects.index.md"
    if "retrospective:" in title.lower():
        return "Projects.index.md"

    # Claude Code index (default for auto-generated)
    if tags_lower & {"auto", "feat", "fix", "git", "hooks", "skills", "agents"}:
        return "Claude-Code.index.md"
    if any(x in title.lower() for x in ["feat:", "fix:", "refactor:"]):
        return "Claude-Code.index.md"

    return None


def update_thematic_index(index_path: Path, entry_link: str, tags_str: str):
    """Prepend entry to "## Recent" section in thematic index.

    WHY the lock + existing-link check (MEDIUM, cross-model audit): every
    SessionEnd within the 5-minute "recent" window re-globs the same wiki
    entry and called this unconditionally -- without the existing-link
    check the same entry_link was prepended again on every run. The lock
    additionally protects against two concurrent SessionEnd hooks racing on
    the same read-modify-write, matching the fix shape already applied to
    moc_autolink.py's sibling update_moc() in this same audit pass.
    """
    if not index_path.exists():
        return

    try:
        lock_path = index_path.with_suffix(".lock")
        with file_lock(lock_path, timeout=15.0) as acquired:
            if not acquired:
                raise TimeoutError(f"Could not acquire thematic index lock: {lock_path}")

            content = index_path.read_text(encoding="utf-8")
            if entry_link in content:
                return

            marker = "## 📌 Recent" if "📌" in content else "## Recent"

            if marker in content:
                # Insert after marker
                content = content.replace(
                    f"{marker}\n", f"{marker}\n\n- {entry_link} — {tags_str}\n", 1
                )
            else:
                # Create Recent section
                lines = content.splitlines()
                insert_pos = next((i for i, line in enumerate(lines) if line.startswith("##")), 5)
                lines.insert(insert_pos, f"\n{marker}\n\n- {entry_link} — {tags_str}\n")
                content = "\n".join(lines)

            index_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        print(
            f"[thematic-index-router] WARNING: failed to update {index_path}: {exc}",
            file=sys.stderr,
        )


def main():
    wiki_dir = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
    if not wiki_dir.exists():
        return

    # Find recently created wiki entries (last 5 minutes)
    now = datetime.now(UTC).timestamp()
    recent_cutoff = now - 300  # 5 min

    for entry_file in wiki_dir.glob("20*.md"):  # YYYY-MM-DD pattern
        if entry_file.stat().st_mtime < recent_cutoff:
            continue

        try:
            content = entry_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract title and tags
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else entry_file.stem

        tags_match = re.search(r"\*\*Tags:\*\*\s+(.+)$", content, re.MULTILINE)
        tags_str = tags_match.group(1) if tags_match else ""
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        # Route to thematic index
        target_index = route_entry(title, tags, content)
        if not target_index:
            continue

        index_path = wiki_dir / target_index
        wikilink = f"[[{title}]]"
        update_thematic_index(index_path, wikilink, tags_str)


if __name__ == "__main__":
    main()
