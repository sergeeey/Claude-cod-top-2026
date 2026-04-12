#!/usr/bin/env python3
"""Weekly inbox review — deeper processing of ~/.claude/memory/inbox/.

WHY: Raw→Wiki (session_save.py) handles quick captures from raw/ with
minimal context. inbox/ is different: it stores half-formed ideas, voice-note
transcripts, and random thoughts that need RICHER processing — reading the
full wiki context to find connections that a simple tag-match would miss.

RixAI pattern: "inbox is processed weekly, ideas are woven into the graph
with full context awareness, not just appended to the wiki."

Usage:
    python scripts/inbox_review.py             # process all inbox/ files
    python scripts/inbox_review.py --dry-run   # show what would be processed
    python scripts/inbox_review.py --summary   # print summary only
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# WHY: script can run standalone (python scripts/inbox_review.py) OR be
# imported by hooks. sys.path insert lets it find hooks/ utils.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

INBOX_DIR = Path.home() / ".claude" / "memory" / "inbox"
WIKI_DIR = Path.home() / ".claude" / "memory" / "wiki"
PROCESSED_DIR = INBOX_DIR / "processed"

MAX_WIKI_CONTEXT_ENTRIES = 20  # WHY: cap context to avoid token explosion
MAX_CONTEXT_CHARS = 8000  # WHY: enough for rich cross-linking without overflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_keywords(text: str, min_len: int = 4) -> list[str]:
    """Extract unique meaningful keywords from text."""
    _STOP = frozenset(
        {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "have",
            "will",
            "been",
            "they",
            "were",
            "when",
            "into",
            "also",
            "some",
            "only",
            "это",
            "для",
            "при",
            "все",
            "как",
            "что",
            "или",
            "очень",
            "нет",
        }
    )
    words = re.findall(rf"\b[a-zA-Zа-яА-Я]{{{min_len},}}\b", text)
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        wl = w.lower()
        if wl not in _STOP and wl not in seen:
            seen.add(wl)
            result.append(wl)
    return result[:20]


def _load_wiki_context(keywords: list[str]) -> str:
    """Load relevant wiki entries as context for cross-linking.

    WHY: Unlike session_save.py which only uses index.md (fast path),
    inbox_review reads actual file content for richer context — we have
    more time (weekly batch) so we can afford deeper reads.
    """
    if not WIKI_DIR.exists() or not keywords:
        return ""

    scored: list[tuple[Path, int]] = []
    for f in sorted(WIKI_DIR.glob("*.md")):
        if f.name == "index.md":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = sum(1 for kw in keywords if kw in text.lower())
        if score > 0:
            scored.append((f, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    parts: list[str] = []
    total = 0
    for f, _ in scored[:MAX_WIKI_CONTEXT_ENTRIES]:
        try:
            snippet = f.read_text(encoding="utf-8", errors="ignore")[:500]
        except OSError:
            continue
        title = f.stem.replace("-", " ").replace("_", " ").title()
        entry = f"[[{title}]]:\n{snippet}\n"
        if total + len(entry) > MAX_CONTEXT_CHARS:
            break
        parts.append(entry)
        total += len(entry)

    return "\n---\n".join(parts)


def _find_wiki_links(inbox_content: str, wiki_context: str) -> list[str]:
    """Find wiki entries to cross-link based on keyword overlap.

    WHY: instead of just tag matching (as in session_save.py), we look for
    keyword overlap between the inbox note and wiki entry CONTENT snippets.
    This catches conceptual connections that tags don't capture.
    """
    keywords = set(_extract_keywords(inbox_content))
    links: list[str] = []

    # Extract [[Title]] from context and check for keyword matches
    for line in wiki_context.splitlines():
        m = re.match(r"\[\[([^\]]+)\]\]", line)
        if m:
            current_title = m.group(1)
            current_slug = current_title.lower()
            if any(kw in current_slug or kw in line.lower() for kw in keywords):
                if f"[[{current_title}]]" not in links:
                    links.append(f"[[{current_title}]]")

    return links[:6]  # WHY: cap at 6 — inbox note should link to most relevant, not everything


def _build_inbox_entry(
    title: str,
    source_file: str,
    content: str,
    wiki_links: list[str],
    category: str,
    tags: list[str],
) -> str:
    """Build a rich wiki entry from an inbox note.

    WHY: inbox entries get a richer format than raw→wiki entries because
    they've been through the weekly review — they have curated cross-links
    and a "Weaved on" timestamp showing when they were integrated.
    """
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    tags_str = ", ".join(tags) if tags else "—"

    # Clean body
    body_lines = []
    h1_seen = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not h1_seen:
            h1_seen = True
            continue
        cleaned = re.sub(r"\s*#inbox\b", "", line, flags=re.IGNORECASE).rstrip()
        body_lines.append(cleaned)
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    body = "\n".join(body_lines)

    links_section = ""
    if wiki_links:
        links_section = "\n## Woven Into\n\n" + "\n".join(f"- {lnk}" for lnk in wiki_links) + "\n"

    return (
        f"# {title}\n\n"
        f"**Date:** {date_str}  \n"
        f"**Source:** inbox/{source_file}  \n"
        f"**Tags:** {tags_str}  \n"
        f"**Category:** {category}  \n"
        f"**Weaved:** {date_str} (weekly inbox review)  \n\n"
        f"---\n\n"
        f"{body}\n"
        f"{links_section}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def process_inbox(dry_run: bool = False) -> int:
    """Process all .md files in inbox/ → wiki/ with rich cross-linking.

    Returns number of files processed.
    """
    if not INBOX_DIR.exists():
        print("[inbox-review] No inbox/ folder found. Create ~/.claude/memory/inbox/ to use.")
        return 0

    inbox_files = list(sorted(INBOX_DIR.glob("*.md")))
    if not inbox_files:
        print("[inbox-review] inbox/ is empty — nothing to process.")
        return 0

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    processed_dir = PROCESSED_DIR
    if not dry_run:
        processed_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in inbox_files:
        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        # Extract metadata
        title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f.stem.replace("_", " ").title()
        tags = [t for t in re.findall(r"#(\w+)", content) if t.lower() not in ("inbox", "raw")]
        keywords = _extract_keywords(content)

        # Auto-category
        from session_save import _assign_category  # WHY: reuse category logic

        category = _assign_category(tags)

        # Rich cross-linking via wiki context
        wiki_context = _load_wiki_context(keywords)
        wiki_links = _find_wiki_links(content, wiki_context)

        # Build entry
        entry = _build_inbox_entry(
            title=title,
            source_file=f.name,
            content=content,
            wiki_links=wiki_links,
            category=category,
            tags=tags,
        )

        if dry_run:
            print(f"\n{'=' * 60}")
            print(f"[DRY RUN] {f.name} → wiki/{title[:40]}.md")
            print(f"  Tags: {tags}")
            print(f"  Category: {category}")
            print(f"  Links found: {wiki_links}")
            count += 1
            continue

        # Write to wiki/ with date prefix
        date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
        stem = re.sub(r"[^\w\-]", "_", f.stem)
        wiki_file = WIKI_DIR / f"{date_prefix}_{stem}.md"
        n = 2
        while wiki_file.exists():
            wiki_file = WIKI_DIR / f"{date_prefix}_{stem}_{n}.md"
            n += 1

        wiki_file.write_text(entry, encoding="utf-8")
        f.rename(processed_dir / f.name)
        count += 1
        print(
            f"[inbox-review] {f.name} → {wiki_file.name} "
            f"(links: {len(wiki_links)}, cat: {category})"
        )

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly inbox review — weave inbox/ into wiki/")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    args = parser.parse_args()

    if args.summary:
        inbox_files = list(INBOX_DIR.glob("*.md")) if INBOX_DIR.exists() else []
        wiki_files = list(WIKI_DIR.glob("*.md")) if WIKI_DIR.exists() else []
        print(f"[inbox-review] inbox/: {len(inbox_files)} files pending")
        print(f"[inbox-review] wiki/: {len(wiki_files)} entries total")
        return

    count = process_inbox(dry_run=args.dry_run)
    if count > 0 and not args.dry_run:
        # Regenerate wiki index after adding new entries
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
        from session_save import update_wiki_index

        update_wiki_index(WIKI_DIR)
        print(f"[inbox-review] ✓ {count} note(s) weaved into wiki/, index.md updated")
    elif count == 0 and not args.dry_run:
        print("[inbox-review] Nothing to process.")


if __name__ == "__main__":
    main()
