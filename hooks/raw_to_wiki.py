#!/usr/bin/env python3
"""Stop hook: convert raw notes and Obsidian clips into wiki entries.

WHY: automatically converts raw notes in ~/.claude/memory/_auto/raw/ into
structured wiki entries in ~/.claude/memory/_auto/wiki/. Low-friction capture:
drop a .md file in raw/, it becomes a wiki entry at end of session. Also
scans an optional Obsidian Web Clipper folder (OBSIDIAN_RAW_DIR) through
the same pipeline, regenerates the wiki index, rebuilds the vector search
index, and appends a session-handoff breadcrumb to the daily note.

WHY split from session_save.py (2026-08-28, /tracy strategic pass after
deletion-test found session_save.py was a 1043-line God-module with two
unrelated responsibilities): this pipeline -- note parsing, tagging,
contradiction/distortion detection, wiki-entry construction, index
regeneration -- is a fundamentally different concern from session-end
bookkeeping (timestamp update, session log, memory-staleness warning).
See hooks/session_save.py for that half, split out the same day. Both
remain registered on Stop independently, matching the existing
multi-hook-per-event pattern already used by webhook_notify.py/
wiki_reminder.py/thematic_index_router.py.
"""

import hashlib
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import cogniml_client
from lib.discovery import find_project_memory
from lib.state import file_lock

try:
    import vector_store

    _VECTOR_STORE_AVAILABLE = True
except ImportError:
    _VECTOR_STORE_AVAILABLE = False

_MAX_READ_BYTES = 1 * 1024 * 1024  # 1 MB — raw notes should never exceed this


def _safe_read(p: Path, limit: int = _MAX_READ_BYTES) -> str:
    """Read file with size cap to prevent OOM on oversized raw/ dumps.
    WHY: raw/ and OBSIDIAN_RAW_DIR are user-writable (Web Clipper, drag-drop).
    """
    try:
        if p.stat().st_size > limit:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


# WHY: recursion guard — if this hook is triggered inside an Agent SDK
# sub-invocation (e.g., compile.py spawns Claude), exit immediately to
# prevent double-processing and infinite loops.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

# WHY: dry-run mode — set CLAUDE_DRY_RUN=1 to preview what this hook
# would write without touching any files. Useful for testing and CI.
# Based on Evolver review gate pattern: show → confirm → execute.
DRY_RUN = os.environ.get("CLAUDE_DRY_RUN") == "1"


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


# WHY (owner request 2026-09-04, pearl_registry finding from the
# memory-retrieval-repair TZ's live redeploy verification): auto_capture.py
# tags every note it writes with the literal "#auto-capture" marker
# (hooks/auto_capture.py's _capture_git_commit/_capture_test_failure).
# Measured on the live corpus: these notes were 1756 of 2061 files (85%),
# dominating both keyword and dense-search candidates and diluting
# corpus-wide TF-IDF weight for real, curated content -- the exact harm
# this PARA-routing pipeline exists to keep out of the "areas/resources"
# folders these notes would otherwise land in.
#
# WHY a substring check on raw content, not the parsed `tags` list:
# _extract_tags()'s `#(\w+)` regex stops at the hyphen, so "#auto-capture"
# is parsed into the tag "auto" -- too generic/collision-prone to filter on
# safely. The literal marker string survives verbatim in the note's raw
# content (only "#raw" is stripped by _build_wiki_entry's body cleaning),
# so checking the untouched source string is both correct and avoids
# touching the shared, widely-used tag-extraction regex for this one case.
#
# WHY a dedicated PARA-adjacent directory, not a content check at scan/
# index time: vector_store._iter_indexable_files()'s corpus fingerprint
# (PR-1) is deliberately stat()-only for performance -- adding a content
# read there to check for this tag on every file, every Stop event, would
# reintroduce the exact "re-embed everything on every Stop" cost PR-1 was
# built to eliminate. Routing to its own directory keeps the exclusion a
# pure path check everywhere it needs to apply, matching the existing
# "daily/" exclusion's own performance profile exactly.
_AUTO_CAPTURE_MARKER = "#auto-capture"
_RETRIEVAL_EXCLUDED_PARA_DIR = "auto_capture"

# WHY these two additions (owner request 2026-09-04, pearl_registry finding
# from re-measuring the corpus after the #auto-capture fix): 188 more files
# were diluting retrieval the same way, from two OTHER sources neither
# tagged "#auto-capture":
#
# 1. "#auto-generated" (105 files, "cogniml-skill-*.md") -- a retrospective
#    generator external to this repo (grep confirms no hooks/*.py writes
#    this filename pattern) that drops files into raw/, which
#    process_raw_to_wiki() then converts exactly like any other raw note --
#    its **Source:** field is genuinely "raw/cogniml-skill-<hash>.md", so
#    this IS a live, ongoing write path through OUR pipeline, just from
#    content this repo doesn't itself produce. Handled the same way as
#    "#auto-capture": a content-marker check, live in _resolve_para_dir().
#
# 2. Legacy git-capture filenames (83 files, "git-feat-<hash>.md"/
#    "git-fix-<hash>.md") -- an older or parallel commit-capture mechanism
#    that predates auto_capture.py's current "auto-git-*" + "#auto-capture"
#    convention. These carry no distinguishing content tag at all (just
#    generic "#feat #git"/"#fix #git", which a genuine hand-written note
#    could also use) -- filtering on tag content would be collision-prone.
#    grep confirms no hooks/*.py in this repo generates this naming pattern
#    today, so this is migration-only cleanup, NOT wired into
#    _resolve_para_dir()'s write path -- there is no live writer to
#    intercept. Detected instead by the wiki filename's own rigid,
#    low-collision shape (git-{feat,fix,refactor}-<6-10 hex chars>.md).
_AUTO_GENERATED_MARKER = "#auto-generated"
_RETRIEVAL_EXCLUDED_MARKERS = (_AUTO_CAPTURE_MARKER, _AUTO_GENERATED_MARKER)
_LEGACY_GIT_CAPTURE_RE = re.compile(r"_git-(?:feat|fix|refactor)-[0-9a-f]{6,10}\.md$")


def _resolve_para_dir(content: str, tags: list[str], category: str) -> str:
    """Like _assign_para_dir, but routes auto_capture.py (and other
    similarly-marked) notes to a dedicated, retrieval-excluded directory
    instead of the normal PARA categories. See _AUTO_CAPTURE_MARKER's own
    WHY comment above."""
    if any(marker in content for marker in _RETRIEVAL_EXCLUDED_MARKERS):
        return _RETRIEVAL_EXCLUDED_PARA_DIR
    return _assign_para_dir(tags, category)


def migrate_retrieval_excluded_notes(wiki_dir: Path) -> int:
    """One-time cleanup: move existing wiki entries matching any
    retrieval-excluded signal (content marker or the legacy git-capture
    filename shape) out of whatever PARA dir they were already written to,
    into _RETRIEVAL_EXCLUDED_PARA_DIR. Returns count moved.

    WHY this is needed in addition to _resolve_para_dir(): that fix only
    routes NEW notes correctly going forward. It does nothing for notes
    already written before each signal was added to this function -- on
    the live corpus that was 1756 "#auto-capture" files (85%, pearl_registry
    2026-09-04), then a further 188 files from two other sources (105
    "#auto-generated", 83 legacy git-feat-/git-fix-* with no content
    marker at all -- see _LEGACY_GIT_CAPTURE_RE's own WHY comment above).
    Run this once against a corpus that predates a given signal; it is a
    no-op (0 moved) on a corpus that doesn't need it.

    WHY not wired into any hook's automatic per-Stop path: this does a
    full-content read of every wiki file, which is exactly the cost
    _iter_indexable_files()'s stat()-only fingerprint (PR-1) exists to
    avoid on the hot path. This is a deliberate one-off, invoked manually.

    Idempotent and non-destructive: skips files already under the excluded
    dir, and skips (rather than overwrites) a same-name collision at the
    destination -- data is never silently lost.
    """
    if not wiki_dir.exists():
        return 0
    dest_dir = wiki_dir / _RETRIEVAL_EXCLUDED_PARA_DIR
    moved = 0
    for f in sorted(wiki_dir.rglob("*.md")):
        if f.name == "index.md" or _RETRIEVAL_EXCLUDED_PARA_DIR in f.parts:
            continue
        if not _LEGACY_GIT_CAPTURE_RE.search(f.name):
            try:
                content = _safe_read(f)
            except OSError:
                continue
            if not any(marker in content for marker in _RETRIEVAL_EXCLUDED_MARKERS):
                continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name
        if dest.exists():
            continue  # name collision -- leave the source in place, don't clobber
        f.rename(dest)
        moved += 1
    return moved


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
    # WHY: rglob instead of glob — finds entries across PARA subdirs
    # (projects/, areas/, resources/, archives/) not just flat wiki/,
    # matching the established pattern in _find_related_wiki() below.
    for f in sorted(wiki_dir.rglob("*.md")):
        if f.name in ("index.md", exclude_source):
            continue
        try:
            text = _safe_read(f)
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
            text = _safe_read(f).lower()
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
    exclude_filename: str = "",
) -> str:
    """Build a structured wiki entry from raw note content.

    WHY: consistent structure enables grep/search across wiki entries.
    Frontmatter-style header + cleaned body (no #raw tag, no H1 duplication).
    wiki_dir passed to enable wikilink generation (graph edges).

    WHY exclude_filename is separate from source: `source` is a display-only
    provenance string ("raw/note.md") shown in the entry's own header — it
    never matches a PARA-routed destination file's basename, so it cannot be
    used to exclude that destination from the related/contradiction scans.
    `exclude_filename` is the actual upsert-destination basename (e.g.
    "2026-09-04_note.md"), computed by the caller BEFORE this function runs.
    Falls back to `source` when omitted (existing callers/tests unaffected).
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
        exclude_name = exclude_filename or source
        related = _find_related_wiki(tags, wiki_dir, exclude_name)
        if related:
            related_section = f"\n## Related\n\n{chr(10).join(related)}\n"

        # WHY: RixAI pattern — surface contradictions immediately so the user
        # decides which claim to trust, rather than silently stacking conflicting
        # facts. Two signals required (tag overlap + opposing directives) to
        # keep false-positive rate low.
        conflicts = _detect_contradictions(content, tags, wiki_dir, exclude_name)
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
        # Skip auto_capture.py notes — excluded from retrieval, see
        # _resolve_para_dir()'s own WHY comment above
        if "auto_capture" in f.parts:
            continue
        # WHY: skip numbered chunk fragments (e.g. cogniml-skill-abc_12.md) —
        # split pages of one source file, not standalone entries.
        if re.search(r"_\d+\.md$", f.name):
            continue
        try:
            content = _safe_read(f)
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
        # WHY rel_path, not f.name (memory-retrieval-repair-tz.md PR-2, fixes
        # 0.2): the index previously wrote [[Title]] with no way back to the
        # actual file when title != filename stem (the normal case for
        # dated slugs) -- knowledge_librarian._read_wiki_content() guessed
        # WIKI_DIR/{title}.md and almost always missed. rel_path (POSIX,
        # relative to wiki_dir, includes the PARA subdir and .md extension)
        # is the same join key vector_store.WikiRef already uses.
        rel_path = f.relative_to(wiki_dir).as_posix()
        entries.append(
            {
                "rel_path": rel_path,
                "title": title,
                "tags": tags,
                "date": date,
                "para": para,
            }
        )

    if not entries:
        # WHY: don't just skip -- if index.md already exists from before
        # every entry became excluded (e.g. a corpus that is now entirely
        # daily/auto_capture notes after a migration), leaving it in place
        # lets knowledge_librarian's keyword-index path keep parsing
        # [[rel_path|Title]] entries whose files no longer live there,
        # rendering stale/dead references as WARM hits (Codex review,
        # PR #347, reproduced before fixing). Regenerate a fresh,
        # header-only index instead of returning with the stale one intact.
        index_path = wiki_dir / "index.md"
        if index_path.exists() and not DRY_RUN:
            try:
                index_path.write_text("# Knowledge Base Index\n", encoding="utf-8")
            except OSError:
                pass  # fail-open -- same tolerance as the write path below
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
        # WHY [[rel_path|Title]] alias syntax, not [[Title]] (PR-2, fixes 0.2):
        # real Obsidian alias syntax -- knowledge_librarian.py already does
        # title.split("|")[0] defensively (previously unreached dead code,
        # confirmed by grep; this activates it) to recover rel_path from the
        # match, so no change needed to the [[...]] extraction regex itself.
        lines.append(f"- [[{e['rel_path']}|{e['title']}]]{suffix}")

    # PARA navigation map — primary for agent navigation
    lines += ["", "## PARA", ""]
    for para_key in ("projects", "areas", "resources", "archives"):
        para_entries = para_map.get(para_key, [])
        if para_entries:
            lines.append(f"### {para_key.title()} ({len(para_entries)})")
            for e in para_entries:
                lines.append(f"- [[{e['rel_path']}|{e['title']}]]")
            lines.append("")

    lines += ["## By Topic", ""]
    for tag in sorted(tag_map):
        tag_entries = tag_map[tag]
        lines.append(f"### {tag} ({len(tag_entries)})")
        # WHY: no cap — every entry must be reachable via the index.
        # Capping at 8 hid 96% of the knowledge base from knowledge_librarian
        # (discovered 2026-04-12: 52 unique entries for 1444 files).
        for e in tag_entries:
            lines.append(f"- [[{e['rel_path']}|{e['title']}]]")
        lines.append("")

    index_path = wiki_dir / "index.md"
    try:
        if DRY_RUN:
            print(f"[dry-run] would write wiki index: {index_path} ({len(entries)} entries)")
        else:
            index_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as exc:
        # WHY: fail-open — index is a convenience, not a blocker, but a
        # silently-swallowed failure here (LOW, cross-model audit) leaves
        # knowledge_librarian reading a stale/missing index with no signal.
        print(f"[session-save] WARNING: failed to write {index_path}: {exc}", file=sys.stderr)


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
            stored = _safe_read(_OBSIDIAN_RAW_CONFIG).strip()
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
            content = _safe_read(raw_file)
            if _has_processed_marker(content):
                continue  # already processed in a previous session

            title = _extract_title(content, raw_file.name)
            tags = _extract_tags(content)

            # WHY: computed BEFORE _build_wiki_entry() -- see that function's
            # own WHY comment on exclude_filename (same fix as
            # process_raw_to_wiki() above, Codex review PR #342).
            category = _assign_category(tags)
            para_subdir = _resolve_para_dir(content, tags, category)
            date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
            stem = re.sub(r"[^\w\-]", "_", raw_file.stem)
            para_dir = wiki_dir / para_subdir
            para_dir.mkdir(parents=True, exist_ok=True)
            wiki_file = para_dir / f"{date_prefix}_{stem}.md"

            # Upsert: check PARA subdir and legacy flat wiki/ for existing stem
            existing = list(para_dir.glob(f"*_{stem}.md")) or list(wiki_dir.glob(f"*_{stem}.md"))
            if existing:
                wiki_file = existing[0]

            wiki_entry = _build_wiki_entry(
                title=title,
                tags=tags,
                source=f"obsidian-raw/{raw_file.name}",
                content=content,
                wiki_dir=wiki_dir,
                exclude_filename=wiki_file.name,
            )

            wiki_file.write_text(wiki_entry, encoding="utf-8")
            # WHY skip for excluded notes (Codex review, PR #347): CogniML
            # is a separate semantic backend knowledge_librarian.py falls
            # back to when local retrieval finds nothing at all
            # (cogniml_client.advise() in main()) -- pushing an excluded
            # note here would let it resurface through that path even
            # though it is excluded from every LOCAL retrieval surface.
            if para_subdir != _RETRIEVAL_EXCLUDED_PARA_DIR:
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
        lines = _safe_read(obs_file).splitlines()
        return [ln.strip() for ln in lines if ln.strip().startswith("-")][:10]
    except OSError:
        return []


def _get_current_focus() -> str:
    """Extract ## Current Focus section from activeContext.md (first 300 chars)."""
    ctx = find_project_memory()
    if ctx is None:
        return ""
    try:
        content = _safe_read(ctx)
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
            content = _safe_read(f)
            title_match = re.search(r"^# (.+)", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            titles.append(title)
        except OSError:
            pass
    return titles


_SESSION_HASH_RE = re.compile(r"<!-- session-hash: ([0-9a-f]+) -->")


def _build_session_block(wiki_dir: Path, date_str: str) -> str:
    """Build one session section for the daily note.

    WHY the trailing session-hash comment (MEDIUM, cross-model audit):
    repeated Stop runs in quick succession see identical commits/
    observations/focus and previously appended a near-identical block every
    time, growing the daily note unboundedly. The hash lets write_daily_note
    skip appending when the signal is unchanged since the last write.
    """
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

    signal = "\n".join(lines[2:]).strip()
    signal_hash = hashlib.sha256(signal.encode("utf-8")).hexdigest()[:12]
    lines.append(f"<!-- session-hash: {signal_hash} -->")

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
            return

        lock_path = note_path.with_suffix(".lock")
        with file_lock(lock_path, timeout=15.0) as acquired:
            if not acquired:
                raise TimeoutError(f"Could not acquire daily note lock: {lock_path}")

            if note_path.exists():
                existing = _safe_read(note_path)
                new_hash_match = _SESSION_HASH_RE.search(session_block)
                existing_hashes = _SESSION_HASH_RE.findall(existing)
                if (
                    new_hash_match
                    and existing_hashes
                    and existing_hashes[-1] == new_hash_match.group(1)
                ):
                    return  # identical signal to the most recent block -- skip duplicate
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
            content = _safe_read(raw_file)
            if not content:
                continue

            # WHY: only process files that contain #raw tag OR are in raw/ dir.
            # Files without #raw may have been placed there by mistake — still
            # process them (raw/ location is enough signal), but log it.
            title = _extract_title(content, raw_file.name)
            tags = _extract_tags(content)

            # WHY: timestamp prefix ensures chronological order within each dir.
            # PARA subdir routes the entry to projects/areas/resources/archives
            # based on tags — forward-only, no migration of existing flat files.
            # Computed BEFORE _build_wiki_entry() (not after, as in the prior
            # version) so the actual upsert-destination basename can be passed
            # as exclude_filename -- see _build_wiki_entry's own WHY comment.
            # Without this, updating an existing note with an opposing
            # directive gets flagged as contradicting its own prior version,
            # and that self-reference gets baked into the file being
            # overwritten (Codex review, PR #342, reproduced before fixing).
            category = _assign_category(tags)
            para_subdir = _resolve_para_dir(content, tags, category)
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

            wiki_entry = _build_wiki_entry(
                title=title,
                tags=tags,
                source=f"raw/{raw_file.name}",
                content=content,
                wiki_dir=wiki_dir,
                exclude_filename=wiki_file.name,
            )

            if DRY_RUN:
                print(f"[dry-run] would write wiki: {wiki_file}")
                print(f"[dry-run] would move raw:  {raw_file.name} → processed/")
            else:
                wiki_file.write_text(wiki_entry, encoding="utf-8")

                # WHY: push to CogniML so wiki entries are also searchable via
                # vector similarity — complements local keyword grep in librarian.
                # Skipped for excluded notes (Codex review, PR #347) -- see
                # the Obsidian pipeline's identical check above for the WHY.
                if para_subdir != _RETRIEVAL_EXCLUDED_PARA_DIR:
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
            print("[dry-run] raw_to_wiki.py — preview mode (CLAUDE_DRY_RUN=1)")
            print("[dry-run] no files will be written")

        # 1. Raw → Wiki pipeline
        # WHY: process raw notes at session end, not during session, to avoid
        # interrupting the user's flow. Session end is a natural processing point.
        raw_dir = Path.home() / ".claude" / "memory" / "_auto" / "raw"
        wiki_dir = Path.home() / ".claude" / "memory" / "_auto" / "wiki"
        processed = process_raw_to_wiki(raw_dir, wiki_dir)
        if processed > 0:
            print(f"[raw-to-wiki] Raw→Wiki: {processed} note(s) processed → ~/.claude/memory/wiki/")

        # 2. Obsidian Web Clipper → Wiki pipeline
        # WHY: if user has OBSIDIAN_RAW_DIR configured, auto-convert clipped
        # web pages into wiki entries — same pipeline as raw/, but leaves
        # originals in place (marked with processed: true in frontmatter).
        obsidian_raw = _resolve_obsidian_raw_dir()
        if obsidian_raw:
            obs_processed = scan_obsidian_raw(obsidian_raw, wiki_dir)
            if obs_processed > 0:
                print(f"[raw-to-wiki] Obsidian→Wiki: {obs_processed} clipped note(s) processed")

        # 3. Regenerate wiki index.md (Karpathy navigation map)
        # WHY: always regenerate — even if no new raw notes, wiki may have grown
        # from other sources. Fresh index = agent has accurate map at next start.
        update_wiki_index(wiki_dir)

        # 3b. Rebuild vector index for semantic search
        # WHY log the report, not just call-and-discard (memory-retrieval-repair-tz.md
        # PR-1): rebuild_index() now returns a structured RebuildReport (scanned/
        # indexed/failed/skipped/changed) instead of a bare count -- a silent
        # discard would hide the exact "N indexed" vs "N failed silently"
        # ambiguity that let this chain's defects ship behind a green suite.
        if _VECTOR_STORE_AVAILABLE:
            report = vector_store.rebuild_index(wiki_dir)
            if report.changed:
                # WHY include deleted (memory-retrieval-repair-tz.md PR-3,
                # fixes 0.4): rebuild_index() now actually removes stale
                # entries for deleted/renamed files -- surfacing the count
                # here makes that visible in Stop-hook output instead of a
                # silent, unverifiable "N indexed" that says nothing about
                # what was cleaned up.
                print(
                    f"[raw-to-wiki] Vector index rebuilt: {report.indexed} indexed, "
                    f"{report.deleted} deleted, {report.failed} failed, "
                    f"backend={report.backend}"
                )

        # 4. Session handoff — Daily Note
        # WHY: Karpathy pattern — each session leaves a breadcrumb so the
        # next session starts with context. Appends to wiki/daily/YYYY-MM-DD.md.
        write_daily_note(wiki_dir)

    except Exception as e:
        import traceback

        # WHY: F14 — previously swallowed silently — at least log to stderr so user sees it.
        # WHY stderr: stdout is the hook protocol, must not contaminate.
        print(f"[raw_to_wiki error] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    main()
