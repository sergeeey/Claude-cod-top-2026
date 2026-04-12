#!/usr/bin/env python3
"""Stop hook: update timestamp, check memory staleness, process Raw→Wiki.

WHY: This is the last chance to remind Claude to update memory before
the user leaves. We check: if activeContext.md was not updated for >30 min,
but git log shows fresh commits — memory is stale.

Step 4 (Raw→Wiki): automatically converts raw notes in ~/.claude/memory/raw/
into structured wiki entries in ~/.claude/memory/wiki/. Low-friction capture:
drop a .md file in raw/, it becomes a wiki entry at end of session.
"""

import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import cogniml_client
from utils import find_project_memory


def get_last_commit_time() -> float | None:
    """Get timestamp of the last git commit."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _extract_tags(content: str) -> list[str]:
    """Extract #hashtags from content (excluding #raw itself).

    WHY: hashtags in raw notes become wiki metadata for search/filtering.
    """
    return [tag for tag in re.findall(r"#(\w+)", content) if tag.lower() != "raw"]


def _extract_title(content: str, filename: str) -> str:
    """Extract title from first H1 heading, or derive from filename.

    WHY: wiki entries need a stable title. H1 wins over filename
    because the author's intent is clearer in the heading.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    # Fallback: filename without extension, underscores → spaces
    return Path(filename).stem.replace("_", " ").replace("-", " ").title()


def _find_related_wiki(tags: list[str], wiki_dir: Path, exclude_source: str) -> list[str]:
    """Find existing wiki entries that share tags with this note.

    WHY: cross-linking notes by shared tags turns an isolated wiki folder
    into an actual traversable graph — the Karpathy Graph RAG pattern.
    Without [[wikilinks]], entries are a flat list; with them, they form
    a network that can be traversed by topic.
    """
    if not tags or not wiki_dir.exists():
        return []

    related: list[str] = []
    for f in sorted(wiki_dir.glob("*.md")):
        if f.name == exclude_source:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        # WHY: search tag words directly in text — handles both "#tag" (raw notes)
        # and "**Tags:** tag" (compiled wiki entries) without format dependency.
        if any(tag.lower() in text for tag in tags):
            title = f.stem.replace("-", " ").replace("_", " ").title()
            related.append(f"[[{title}]]")
    return related[:5]  # cap at 5 to keep entry readable


def _build_wiki_entry(
    title: str,
    tags: list[str],
    source: str,
    content: str,
    wiki_dir: Path | None = None,
) -> str:
    """Build a structured wiki entry from raw note content.

    WHY: consistent structure enables grep/search across wiki entries.
    Frontmatter-style header + cleaned body (no #raw tag, no H1 duplication).
    wiki_dir passed to enable wikilink generation (graph edges).
    """
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    tags_str = ", ".join(tags) if tags else "—"

    # Strip #raw tag and leading H1 from body (already in header)
    body_lines = []
    h1_seen = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not h1_seen:
            h1_seen = True
            continue  # title already in header
        # Remove standalone #raw tag occurrences
        cleaned = re.sub(r"\s*#raw\b", "", line, flags=re.IGNORECASE).rstrip()
        body_lines.append(cleaned)

    # Trim leading blank lines from body
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)

    body = "\n".join(body_lines)

    # WHY: wikilinks section turns isolated entries into a graph.
    # Only generated when wiki_dir is provided (not in tests that don't need it).
    related_section = ""
    if wiki_dir is not None:
        related = _find_related_wiki(tags, wiki_dir, source)
        if related:
            related_section = f"\n## Related\n\n{chr(10).join(related)}\n"

    return (
        f"# {title}\n\n"
        f"**Date:** {date_str}  \n"
        f"**Source:** {source}  \n"
        f"**Tags:** {tags_str}  \n\n"
        f"---\n\n"
        f"{body}\n"
        f"{related_section}"
    )


def process_raw_to_wiki(raw_dir: Path, wiki_dir: Path) -> int:
    """Process all .md files in raw_dir → structured entries in wiki_dir.

    Returns number of files processed.

    WHY: raw/ is the capture inbox (low friction). wiki/ is the structured
    knowledge base. This function is the conveyor belt between them.
    Processed files are moved to raw/processed/ for audit trail — never deleted.
    """
    if not raw_dir.exists():
        return 0

    processed_dir = raw_dir / "processed"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for raw_file in sorted(raw_dir.glob("*.md")):
        try:
            content = raw_file.read_text(encoding="utf-8")

            # WHY: only process files that contain #raw tag OR are in raw/ dir.
            # Files without #raw may have been placed there by mistake — still
            # process them (raw/ location is enough signal), but log it.
            title = _extract_title(content, raw_file.name)
            tags = _extract_tags(content)
            wiki_entry = _build_wiki_entry(
                title=title,
                tags=tags,
                source=f"raw/{raw_file.name}",
                content=content,
                wiki_dir=wiki_dir,
            )

            # WHY: timestamp prefix ensures chronological order in wiki/
            date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
            stem = re.sub(r"[^\w\-]", "_", raw_file.stem)
            wiki_file = wiki_dir / f"{date_prefix}_{stem}.md"

            # WHY: avoid silently overwriting an existing wiki entry
            # (same filename on same day). Append _N suffix if needed.
            if wiki_file.exists():
                n = 2
                while wiki_file.exists():
                    wiki_file = wiki_dir / f"{date_prefix}_{stem}_{n}.md"
                    n += 1

            wiki_file.write_text(wiki_entry, encoding="utf-8")

            # WHY: push to CogniML so wiki entries are also searchable via
            # vector similarity — complements local keyword grep in librarian.
            cogniml_client.push_wiki_entry(title, wiki_entry, tags)

            # Move to processed/ for audit trail
            processed_dir.mkdir(parents=True, exist_ok=True)
            raw_file.rename(processed_dir / raw_file.name)

            count += 1
        except OSError:
            pass  # WHY: fail-open — one bad file must not stop the rest

    return count


def main() -> None:
    try:
        # 1. Update global activeContext timestamp
        global_path = os.path.expanduser("~/.claude/memory/activeContext.md")
        if os.path.exists(global_path):
            with open(global_path, encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "## Last update" in line and i + 1 < len(lines):
                    lines[i + 1] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
                    break
            with open(global_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        # 2. Log session
        log_dir = os.path.expanduser("~/.claude/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "sessions.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat()} | SESSION_END\n")

        # 3. Check project memory staleness
        project_ctx = find_project_memory()
        if project_ctx is None:
            return

        ctx_mtime = project_ctx.stat().st_mtime
        ctx_age_min = (time.time() - ctx_mtime) / 60

        last_commit = get_last_commit_time()
        if last_commit is None:
            return

        commit_age_min = (time.time() - last_commit) / 60

        # If commit is newer than activeContext by >5 min → stale
        if last_commit > ctx_mtime and (last_commit - ctx_mtime) > 300:
            stale_min = (last_commit - ctx_mtime) / 60
            print(
                f"[session-save] WARNING: activeContext.md is"
                f" {stale_min:.0f} min behind latest commit."
            )
            print(
                f"[session-save] Last commit: {commit_age_min:.0f} min ago,"
                f" activeContext: {ctx_age_min:.0f} min ago."
            )
            print("[session-save] Memory should be updated before ending session.")

        # 4. Raw → Wiki pipeline
        # WHY: process raw notes at session end, not during session, to avoid
        # interrupting the user's flow. Session end is a natural processing point.
        raw_dir = Path.home() / ".claude" / "memory" / "raw"
        wiki_dir = Path.home() / ".claude" / "memory" / "wiki"
        processed = process_raw_to_wiki(raw_dir, wiki_dir)
        if processed > 0:
            print(
                f"[session-save] Raw→Wiki: {processed} note(s) processed → ~/.claude/memory/wiki/"
            )

    except Exception:
        pass


if __name__ == "__main__":
    main()
