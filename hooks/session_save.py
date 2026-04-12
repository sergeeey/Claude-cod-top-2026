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
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import cogniml_client
from utils import find_project_memory

# WHY: recursion guard — if session_save is triggered inside an Agent SDK
# sub-invocation (e.g., compile.py spawns Claude), exit immediately to
# prevent double-processing and infinite loops.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)


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


# WHY: tag clusters map user-defined hashtags to human-readable category names.
# Auto-categorisation turns a flat wiki/ into a navigable structure without
# requiring the user to manually assign folders — inspired by RixAI inbox method.
_CATEGORY_MAP: dict[str, frozenset[str]] = {
    "research": frozenset(
        {
            "research",
            "ml",
            "hypothesis",
            "dataset",
            "paper",
            "auc",
            "baseline",
            "science",
            "experiment",
        }
    ),
    "hooks": frozenset(
        {"hook", "session", "posttooluse", "pretooluse", "sessionstart", "sessionend", "stop"}
    ),
    "skills": frozenset({"skill", "routing", "tdd", "mentor", "brainstorm", "workflow", "agent"}),
    "patterns": frozenset(
        {"pattern", "avoid", "repeat", "lesson", "postmortem", "retro", "decision"}
    ),
    "obsidian": frozenset({"obsidian", "vault", "wikilink", "dataview", "templater", "canvas"}),
    "tools": frozenset({"mcp", "cogniml", "gitnexus", "docker", "api", "tool"}),
}

# WHY: AFFIRM markers signal "do this", NEGATE markers signal "avoid this".
# A new note saying [REPEAT] about X while an existing note says [AVOID] about X
# (on the same tag) = genuine contradiction worth surfacing.
_AFFIRM_MARKERS = frozenset(
    {"[repeat]", "повторять", "prefer", "recommended", "use this", "do this"}
)
_NEGATE_MARKERS = frozenset({"[avoid]", "избегать", "never", "don't", "don't use", "не делай"})


def _assign_category(tags: list[str]) -> str:
    """Return the best-matching category for a set of tags, or 'general'.

    WHY: auto-category in wiki headers enables grouping in index.md
    without requiring the user to think about folder structure.
    Uses most-votes wins: tag set vs category keyword sets.
    """
    if not tags:
        return "general"
    tag_set = {t.lower() for t in tags}
    best_cat, best_score = "general", 0
    for cat, keywords in _CATEGORY_MAP.items():
        score = len(tag_set & keywords)
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat


def _detect_contradictions(
    new_content: str, new_tags: list[str], wiki_dir: Path, exclude_source: str
) -> list[str]:
    """Find existing wiki entries that may contradict the new note.

    WHY: RixAI pattern — if new knowledge opposes existing knowledge on
    the same topic, surface it explicitly as [CONFLICTING] rather than
    silently overwriting. Requires TWO signals to fire:
      1. Tag overlap  (same topic)
      2. Opposing directive markers (one says REPEAT, other says AVOID)
    This keeps false-positive rate low — single keyword matches fire constantly.
    """
    if not new_tags or not wiki_dir.exists():
        return []

    new_lower = new_content.lower()
    new_affirms = any(m in new_lower for m in _AFFIRM_MARKERS)
    new_negates = any(m in new_lower for m in _NEGATE_MARKERS)

    if not new_affirms and not new_negates:
        return []  # new note has no directives — nothing to contradict

    conflicts: list[str] = []
    for f in sorted(wiki_dir.glob("*.md")):
        if f.name in ("index.md", exclude_source):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # Signal 1: tag overlap
        tag_match = re.search(r"\*\*Tags:\*\*\s*(.+)", text)
        if not tag_match:
            continue
        # WHY: Tags line ends with "  \" (Markdown line-break). rstrip removes
        # trailing backslash so set intersection works correctly.
        existing_tags = {
            t.strip().rstrip("\\").strip().lower()
            for t in tag_match.group(1).split(",")
            if t.strip().rstrip("\\").strip() not in ("", "—")
        }
        if not (set(t.lower() for t in new_tags) & existing_tags):
            continue

        # Signal 2: opposing directives
        existing_lower = text.lower()
        existing_affirms = any(m in existing_lower for m in _AFFIRM_MARKERS)
        existing_negates = any(m in existing_lower for m in _NEGATE_MARKERS)

        contradiction = (new_affirms and existing_negates) or (new_negates and existing_affirms)
        if contradiction:
            title = f.stem.replace("-", " ").replace("_", " ").title()
            conflicts.append(f"[[{title}]]")

    return conflicts[:3]  # cap at 3 — show the most notable, not all


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
    category = _assign_category(tags)

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

    # WHY: wikilinks + contradiction sections only generated with wiki_dir
    # (not in unit tests that check raw content without a real wiki folder).
    related_section = ""
    conflict_section = ""
    if wiki_dir is not None:
        related = _find_related_wiki(tags, wiki_dir, source)
        if related:
            related_section = f"\n## Related\n\n{chr(10).join(related)}\n"

        # WHY: RixAI pattern — surface contradictions immediately so the user
        # decides which claim to trust, rather than silently stacking conflicting
        # facts. Two signals required (tag overlap + opposing directives) to
        # keep false-positive rate low.
        conflicts = _detect_contradictions(content, tags, wiki_dir, source)
        if conflicts:
            conflict_section = (
                "\n## ⚠️ Potential Contradictions\n\n"
                "> Review — these entries may conflict on [AVOID]/[REPEAT] directives:\n\n"
                + "\n".join(f"- {c}" for c in conflicts)
                + "\n"
            )

    return (
        f"# {title}\n\n"
        f"**Date:** {date_str}  \n"
        f"**Source:** {source}  \n"
        f"**Tags:** {tags_str}  \n"
        f"**Category:** {category}  \n\n"
        f"---\n\n"
        f"{body}\n"
        f"{related_section}"
        f"{conflict_section}"
    )


def update_wiki_index(wiki_dir: Path) -> None:
    """Regenerate index.md — the navigation map for knowledge_librarian.

    WHY: Without an index, knowledge_librarian greps all files blindly —
    O(N) reads per session start. With index.md (Karpathy method), it reads
    ONE file to get a structured overview of the entire knowledge base, then
    navigates directly to relevant entries. Faster, clearer, agent-friendly.

    Format:
        # Knowledge Base Index
        ## Recent (last 7)
        ## By Topic
            ### research (3)
            - [[10 Уроков Archcode Postmortem]]
    """
    if not wiki_dir.exists():
        return

    entries: list[dict] = []
    for f in sorted(wiki_dir.glob("*.md"), reverse=True):
        if f.name == "index.md":
            continue
        # WHY: skip numbered chunk fragments (e.g. cogniml-skill-abc_12.md) —
        # split pages of one source file, not standalone entries.
        if re.search(r"_\d+\.md$", f.name):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # Title: first H1 or stem
        title = f.stem.replace("-", " ").replace("_", " ").title()
        for line in content.splitlines()[:5]:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Tags: from "**Tags:** tag1, tag2  " line
        tags: list[str] = []
        tag_match = re.search(r"\*\*Tags:\*\*\s*(.+)", content)
        if tag_match:
            raw_tags = tag_match.group(1).strip().rstrip("\\").strip()
            tags = [t.strip() for t in raw_tags.split(",") if t.strip() not in ("", "—")]

        # Date from filename prefix YYYY-MM-DD_stem
        date = ""
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", f.stem)
        if date_match:
            date = date_match.group(1)

        entries.append({"file": f.name, "title": title, "tags": tags, "date": date})

    if not entries:
        return

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")

    # Group by tag
    tag_map: dict[str, list[dict]] = {}
    for e in entries:
        for tag in e["tags"] or ["untagged"]:
            tag_map.setdefault(tag, []).append(e)

    lines = [
        "# Knowledge Base Index",
        f"*Auto-generated · {now} · {len(entries)} entries*",
        "",
        "## Recent",
        "",
    ]
    for e in entries[:10]:
        tag_str = ", ".join(e["tags"][:3]) if e["tags"] else ""
        suffix = f" — {tag_str}" if tag_str else ""
        lines.append(f"- [[{e['title']}]]{suffix}")

    lines += ["", "## By Topic", ""]
    for tag in sorted(tag_map):
        tag_entries = tag_map[tag]
        lines.append(f"### {tag} ({len(tag_entries)})")
        # WHY: no cap — every entry must be reachable via the index.
        # Capping at 8 hid 96% of the knowledge base from knowledge_librarian
        # (discovered 2026-04-12: 52 unique entries for 1444 files).
        for e in tag_entries:
            lines.append(f"- [[{e['title']}]]")
        lines.append("")

    index_path = wiki_dir / "index.md"
    try:
        index_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass  # WHY: fail-open — index is a convenience, not a blocker


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

        # 5. Regenerate wiki index.md (Karpathy navigation map)
        # WHY: always regenerate — even if no new raw notes, wiki may have grown
        # from other sources. Fresh index = agent has accurate map at next start.
        update_wiki_index(wiki_dir)

    except Exception:
        pass


if __name__ == "__main__":
    main()
