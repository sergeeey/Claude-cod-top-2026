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

try:
    import vector_store

    _VECTOR_STORE_AVAILABLE = True
except ImportError:
    _VECTOR_STORE_AVAILABLE = False

# WHY: recursion guard — if session_save is triggered inside an Agent SDK
# sub-invocation (e.g., compile.py spawns Claude), exit immediately to
# prevent double-processing and infinite loops.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

# WHY: dry-run mode — set CLAUDE_DRY_RUN=1 to preview what session_save
# would write without touching any files. Useful for testing and CI.
# Based on Evolver review gate pattern: show → confirm → execute.
DRY_RUN = os.environ.get("CLAUDE_DRY_RUN") == "1"


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

# WHY: anti-distortion patterns — phrases that commonly indicate summary distortion:
# overgeneralization (lost scope), dropped qualifiers, unsupported absolutes.
# Regex tuples: (pattern, label shown in the warning).
_DISTORTION_PATTERNS: list[tuple[str, str]] = [
    # Universal quantifiers without explicit scope
    (
        r"\b(always|never|everyone|nobody|all\s+\w+|every\s+\w+)\b",
        "universal quantifier — verify scope is stated",
    ),
    # Absolute superlatives
    (
        r"\b(is the only|is the best|is always|will always|will never)\b",
        "absolute superlative — qualifier or source may be missing",
    ),
    # Percentage / stat without scope context
    (
        r"\b\d{1,3}\.?\d*\s*%(?!\s*(?:of|in|for|from|when|where|among|confidence|coverage|based|—|--))",
        "statistic without scope — who/when/where may have been dropped",
    ),
    # Inference overclaim
    (
        r"\b(proves?|demonstrates?\s+that|therefore\s+all|thus\s+all)\b",
        "overclaim — consider replacing with 'suggests' or adding context",
    ),
]

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


# WHY: PARA (Projects / Areas / Resources / Archives) is a battle-tested
# personal knowledge organisation system (Tiago Forte). Mapping our flat
# wiki/ into PARA subdirs makes knowledge_librarian navigate O(1) per category
# instead of O(N) over all files, and mirrors the paperclip PARA-memory-files
# skill pattern we adopted from paperclipai/paperclip.
_PARA_PROJECTS_TAGS = frozenset(
    {"project", "sprint", "pr", "milestone", "release", "roadmap", "mvp"}
)
_PARA_ARCHIVES_TAGS = frozenset(
    {"archive", "archived", "done", "completed", "deprecated", "old", "closed"}
)
_PARA_AREAS_CATS = frozenset({"hooks", "skills", "general"})
_PARA_RESOURCES_CATS = frozenset({"research", "patterns", "tools", "obsidian"})


def _assign_para_dir(tags: list[str], category: str) -> str:
    """Map tags + category to a PARA subdirectory name.

    Returns one of: 'projects', 'areas', 'resources', 'archives'.

    WHY: forward-only — existing flat files stay where they are; only new
    entries land in PARA subdirs. No migration needed. index.md uses rglob
    so both flat and PARA files appear in the navigation map.
    """
    tag_set = {t.lower() for t in tags}
    if tag_set & _PARA_ARCHIVES_TAGS:
        return "archives"
    if tag_set & _PARA_PROJECTS_TAGS:
        return "projects"
    if category in _PARA_RESOURCES_CATS:
        return "resources"
    return "areas"  # default: hooks, skills, general


def _check_distortion(body: str) -> list[str]:
    """Scan wiki body for common summary-distortion patterns.

    WHY: LLM summaries tend toward omission and overgeneralization —
    qualifiers, scope limits, and uncertainty markers get dropped during
    compression. This scanner surfaces warnings so the author can add them
    back before the entry becomes "knowledge". Returns up to 3 warnings.

    Checks: universal quantifiers, absolute superlatives, unscoped statistics,
    and inference overclaims. False-positive rate is acceptable — warnings
    are advisory, not blockers.
    """
    warnings: list[str] = []
    body_lower = body.lower()
    for pattern, label in _DISTORTION_PATTERNS:
        if re.search(pattern, body_lower):
            warnings.append(label)
        if len(warnings) >= 3:
            break
    return warnings


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
    # WHY: rglob instead of glob — finds entries across PARA subdirs
    # (projects/, areas/, resources/, archives/) not just flat wiki/
    for f in sorted(wiki_dir.rglob("*.md")):
        if f.name in ("index.md", exclude_source):
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


def _extract_tldr(body: str, max_sentences: int = 2) -> str:
    """Extract first 1-2 sentences from body as TL;DR summary.

    WHY: PersistBench 2025 shows wiki entries >400 words reduce recall by 23%.
    A TL;DR gives knowledge_librarian a fast-path summary — agent reads 2
    sentences instead of the full entry to decide relevance.
    """
    sentences: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        # Skip headers, code blocks, bullets, empty lines
        if not line or line.startswith(("#", "-", "*", "`", ">", "|")):
            continue
        # Split on sentence boundaries (. ! ?)
        parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            part = part.strip()
            if len(part) > 20:  # skip fragments
                sentences.append(part)
            if len(sentences) >= max_sentences:
                break
        if len(sentences) >= max_sentences:
            break
    return " ".join(sentences[:max_sentences])


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
    distortion_section = ""
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

        # WHY: SNR anti-distortion check — LLM summaries tend to drop qualifiers,
        # scope limits, and uncertainty markers during compression. Surface warnings
        # so the author can restore them before the entry becomes "knowledge".
        distortions = _check_distortion(body)
        if distortions:
            distortion_section = (
                "\n## ⚠️ Distortion Risk\n\n"
                "> These patterns may indicate dropped qualifiers or lost scope:\n\n"
                + "\n".join(f"- {w}" for w in distortions)
                + "\n"
            )

    # WHY: research shows wiki entries >400 words reduce recall by 23% —
    # LLM "gets lost" in details and misses key facts (PersistBench 2025).
    # TL;DR (≤2 sentences) extracted from first non-empty paragraph gives
    # knowledge_librarian a fast-path summary without reading full entry.
    tldr = _extract_tldr(body)
    tldr_section = f"## TL;DR\n\n{tldr}\n\n---\n\n" if tldr else "---\n\n"

    return (
        f"# {title}\n\n"
        f"**Date:** {date_str}  \n"
        f"**Source:** {source}  \n"
        f"**Tags:** {tags_str}  \n"
        f"**Category:** {category}  \n\n"
        f"{tldr_section}"
        f"{body}\n"
        f"{related_section}"
        f"{conflict_section}"
        f"{distortion_section}"
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
    # WHY: rglob("*.md") recurses into PARA subdirs (projects/areas/resources/archives)
    # so new entries routed there are still indexed. daily/ notes are excluded by path check.
    # Flat legacy files in wiki_dir root are still picked up — no migration needed.
    for f in sorted(wiki_dir.rglob("*.md"), reverse=True):
        if f.name == "index.md":
            continue
        # Skip daily handoff notes — they are temporal logs, not knowledge entries
        if "daily" in f.parts:
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

        # Derive PARA category from file path (subdir name) or from tags
        para = (
            f.parent.name
            if f.parent != wiki_dir
            else _assign_para_dir(tags, _assign_category(tags))
        )
        entries.append({"file": f.name, "title": title, "tags": tags, "date": date, "para": para})

    if not entries:
        return

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")

    # Group by PARA subdir (projects/areas/resources/archives + legacy flat)
    para_map: dict[str, list[dict]] = {}
    for e in entries:
        para_map.setdefault(e.get("para", "areas"), []).append(e)

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

    # PARA navigation map — primary for agent navigation
    lines += ["", "## PARA", ""]
    for para_key in ("projects", "areas", "resources", "archives"):
        para_entries = para_map.get(para_key, [])
        if para_entries:
            lines.append(f"### {para_key.title()} ({len(para_entries)})")
            for e in para_entries:
                lines.append(f"- [[{e['title']}]]")
            lines.append("")

    lines += ["## By Topic", ""]
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
        if DRY_RUN:
            print(f"[dry-run] would write wiki index: {index_path} ({len(entries)} entries)")
        else:
            index_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        pass  # WHY: fail-open — index is a convenience, not a blocker


# ---------------------------------------------------------------------------
# Gap 2: Obsidian Web Clipper auto-pipeline
# ---------------------------------------------------------------------------

# WHY: env var allows each machine to point at its own vault without
# hardcoding OS-specific paths. Falls back to a config file for persistence.
_OBSIDIAN_RAW_ENV = "OBSIDIAN_RAW_DIR"
_OBSIDIAN_RAW_CONFIG = Path.home() / ".claude" / "cache" / "obsidian_raw_path.txt"


def _resolve_obsidian_raw_dir() -> Path | None:
    """Return the Obsidian vault raw/ path, or None if not configured."""
    env_val = os.environ.get(_OBSIDIAN_RAW_ENV, "").strip()
    if env_val:
        p = Path(env_val)
        if p.is_dir():
            return p

    if _OBSIDIAN_RAW_CONFIG.exists():
        try:
            stored = _OBSIDIAN_RAW_CONFIG.read_text(encoding="utf-8").strip()
            if stored:
                p = Path(stored)
                if p.is_dir():
                    return p
        except OSError:
            pass
    return None


def _has_processed_marker(content: str) -> bool:
    """Return True if YAML frontmatter contains 'processed: true'.

    WHY: Obsidian Web Clipper files must NOT be moved (that would break
    Obsidian sync). Instead we mark them in-place so we skip on the next run.
    """
    if not content.startswith("---"):
        return False
    end = content.find("---", 3)
    if end == -1:
        return False
    frontmatter = content[3:end]
    return bool(re.search(r"^\s*processed\s*:\s*true\s*$", frontmatter, re.MULTILINE))


def _add_processed_marker(content: str) -> str:
    """Inject 'processed: true' into frontmatter, or prepend a new block."""
    if content.startswith("---"):
        # Insert after the opening ---\n
        return content.replace("---\n", "---\nprocessed: true\n", 1)
    return "---\nprocessed: true\n---\n\n" + content


def scan_obsidian_raw(obsidian_raw_dir: Path, wiki_dir: Path) -> int:
    """Convert unprocessed Obsidian Web Clipper files → wiki entries.

    Marks processed files in-place via frontmatter (does NOT move them).
    Returns number of files processed.

    WHY: Web Clipper drops pages into the Obsidian vault raw/ folder. This
    function bridges that folder into our ~/.claude/memory/wiki/ pipeline
    so clipped articles become part of the agent's knowledge base.
    """
    if not obsidian_raw_dir.exists():
        return 0

    wiki_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for raw_file in sorted(obsidian_raw_dir.glob("*.md")):
        try:
            content = raw_file.read_text(encoding="utf-8", errors="ignore")
            if _has_processed_marker(content):
                continue  # already processed in a previous session

            title = _extract_title(content, raw_file.name)
            tags = _extract_tags(content)
            wiki_entry = _build_wiki_entry(
                title=title,
                tags=tags,
                source=f"obsidian-raw/{raw_file.name}",
                content=content,
                wiki_dir=wiki_dir,
            )

            category = _assign_category(tags)
            para_subdir = _assign_para_dir(tags, category)
            date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
            stem = re.sub(r"[^\w\-]", "_", raw_file.stem)
            para_dir = wiki_dir / para_subdir
            para_dir.mkdir(parents=True, exist_ok=True)
            wiki_file = para_dir / f"{date_prefix}_{stem}.md"

            # Upsert: check PARA subdir and legacy flat wiki/ for existing stem
            existing = list(para_dir.glob(f"*_{stem}.md")) or list(wiki_dir.glob(f"*_{stem}.md"))
            if existing:
                wiki_file = existing[0]

            wiki_file.write_text(wiki_entry, encoding="utf-8")
            cogniml_client.push_wiki_entry(title, wiki_entry, tags)

            # Mark original file as processed (in-place, no move)
            raw_file.write_text(_add_processed_marker(content), encoding="utf-8")
            count += 1
        except OSError:
            pass  # fail-open

    return count


# ---------------------------------------------------------------------------
# Gap 3: Session handoff (Daily Note)
# ---------------------------------------------------------------------------


def _get_recent_commits(n: int = 5) -> list[str]:
    """Return last n commit subjects from the current repo. Empty list on error."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--format=%s", "--no-merges"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return []


def _get_session_observations(date_str: str) -> list[str]:
    """Read today's observation log and return bullet lines (up to 10)."""
    obs_file = Path.home() / ".claude" / "memory" / "_auto" / "raw" / f"session-{date_str}.md"
    if not obs_file.exists():
        return []
    try:
        lines = obs_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        return [ln.strip() for ln in lines if ln.strip().startswith("-")][:10]
    except OSError:
        return []


def _get_current_focus() -> str:
    """Extract ## Current Focus section from activeContext.md (first 300 chars)."""
    ctx = find_project_memory()
    if ctx is None:
        return ""
    try:
        content = ctx.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"## Current Focus\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if m:
            return m.group(1).strip()[:300]
    except OSError:
        pass
    return ""


def _get_wiki_entries_today(wiki_dir: Path, date_str: str) -> list[str]:
    """Return titles of wiki entries created/modified today (flat + PARA subdirs)."""
    titles: list[str] = []
    for f in wiki_dir.rglob(f"{date_str}_*.md"):
        if re.search(r"_\d+\.md$", f.name):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            title_match = re.search(r"^# (.+)", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            titles.append(title)
        except OSError:
            pass
    return titles


def _build_session_block(wiki_dir: Path, date_str: str) -> str:
    """Build one session section for the daily note."""
    now_time = datetime.now(UTC).strftime("%H:%M")

    commits = _get_recent_commits(5)
    observations = _get_session_observations(date_str)
    focus = _get_current_focus()
    wiki_today = _get_wiki_entries_today(wiki_dir, date_str)

    # Need at least one signal to write a non-empty block
    if not commits and not observations and not focus:
        return ""

    lines = [f"## Session — {now_time}", ""]

    if commits:
        lines.append("### What was done")
        for c in commits:
            lines.append(f"- {c}")
        lines.append("")

    if observations:
        lines.append("### Activity")
        lines.extend(observations)
        lines.append("")

    if focus:
        lines.append("### Where we stopped")
        lines.append(focus)
        lines.append("")

    if wiki_today:
        lines.append("### Wiki entries touched today")
        for t in wiki_today:
            lines.append(f"- [[{t}]]")
        lines.append("")

    return "\n".join(lines)


def write_daily_note(wiki_dir: Path) -> None:
    """Append a session block to today's daily note in wiki/daily/.

    WHY: Karpathy handoff pattern — each session leaves a breadcrumb so the
    next session starts with context instead of re-discovering the state.
    Multiple sessions per day append separate blocks to the same file.
    """
    try:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        session_block = _build_session_block(wiki_dir, date_str)
        if not session_block.strip():
            return

        daily_dir = wiki_dir / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        note_path = daily_dir / f"{date_str}.md"

        if DRY_RUN:
            mode = "append to" if note_path.exists() else "create"
            print(f"[dry-run] would {mode} daily note: {note_path}")
        elif note_path.exists():
            existing = note_path.read_text(encoding="utf-8")
            note_path.write_text(existing + "\n\n" + session_block, encoding="utf-8")
        else:
            header = f"# Daily Note — {date_str}\n\n"
            note_path.write_text(header + session_block, encoding="utf-8")
    except Exception:
        pass  # WHY: fail-open — handoff note is a convenience, not a blocker


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

            # WHY: timestamp prefix ensures chronological order within each dir.
            # PARA subdir routes the entry to projects/areas/resources/archives
            # based on tags — forward-only, no migration of existing flat files.
            category = _assign_category(tags)
            para_subdir = _assign_para_dir(tags, category)
            date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
            stem = re.sub(r"[^\w\-]", "_", raw_file.stem)
            para_dir = wiki_dir / para_subdir
            para_dir.mkdir(parents=True, exist_ok=True)
            wiki_file = para_dir / f"{date_prefix}_{stem}.md"

            # WHY: upsert — check both PARA subdir and legacy flat wiki/ for
            # existing entries to avoid duplication across the migration boundary.
            existing = list(para_dir.glob(f"*_{stem}.md")) or list(wiki_dir.glob(f"*_{stem}.md"))
            if existing:
                wiki_file = existing[0]  # reuse first match (upsert)

            if DRY_RUN:
                print(f"[dry-run] would write wiki: {wiki_file}")
                print(f"[dry-run] would move raw:  {raw_file.name} → processed/")
            else:
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
        if DRY_RUN:
            print("[dry-run] session_save.py — preview mode (CLAUDE_DRY_RUN=1)")
            print("[dry-run] no files will be written")

        # 1. Update global activeContext timestamp
        global_path = os.path.expanduser("~/.claude/memory/_auto/activeContext.md")
        if os.path.exists(global_path):
            with open(global_path, encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "## Last update" in line and i + 1 < len(lines):
                    lines[i + 1] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
                    break
            if not DRY_RUN:
                with open(global_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            else:
                print(f"[dry-run] would update timestamp in: {global_path}")

        # 2. Log session
        log_dir = os.path.expanduser("~/.claude/logs")
        log_path = os.path.join(log_dir, "sessions.log")
        if not DRY_RUN:
            os.makedirs(log_dir, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now(UTC).isoformat()} | SESSION_END\n")
        else:
            print(f"[dry-run] would append SESSION_END to: {log_path}")

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
        raw_dir = Path.home() / ".claude" / "memory" / "_auto" / "raw"
        wiki_dir = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
        processed = process_raw_to_wiki(raw_dir, wiki_dir)
        if processed > 0:
            print(
                f"[session-save] Raw→Wiki: {processed} note(s) processed → ~/.claude/memory/wiki/"
            )

        # 4b. Obsidian Web Clipper → Wiki pipeline
        # WHY: if user has OBSIDIAN_RAW_DIR configured, auto-convert clipped
        # web pages into wiki entries — same pipeline as raw/, but leaves
        # originals in place (marked with processed: true in frontmatter).
        obsidian_raw = _resolve_obsidian_raw_dir()
        if obsidian_raw:
            obs_processed = scan_obsidian_raw(obsidian_raw, wiki_dir)
            if obs_processed > 0:
                print(f"[session-save] Obsidian→Wiki: {obs_processed} clipped note(s) processed")

        # 5. Regenerate wiki index.md (Karpathy navigation map)
        # WHY: always regenerate — even if no new raw notes, wiki may have grown
        # from other sources. Fresh index = agent has accurate map at next start.
        update_wiki_index(wiki_dir)

        # 5b. Rebuild vector index for semantic search
        if _VECTOR_STORE_AVAILABLE:
            vector_store.rebuild_index(wiki_dir)

        # 6. Session handoff — Daily Note
        # WHY: Karpathy pattern — each session leaves a breadcrumb so the
        # next session starts with context. Appends to wiki/daily/YYYY-MM-DD.md.
        write_daily_note(wiki_dir)

    except Exception:
        pass


if __name__ == "__main__":
    main()
