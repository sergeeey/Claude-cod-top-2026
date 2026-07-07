#!/usr/bin/env python3
"""Post-tool hook: auto-link new notes to relevant MOCs.

Triggers: after Write/Edit to ~/.claude/memory/
Routes notes to MOC based on tags and content keywords.
"""

import json
import os
import re
import sys
from pathlib import Path

from utils import file_lock

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
    # WHY: prevent recursion when this hook fires inside a subagent's
    # SessionStart/etc — see hooks/CLAUDE.md "Recursion guard" section.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only process .claude/memory/ writes
    # WHY: resolve()+relative_to() prevents ".claude/memory_FAKE/" bypass
    # that a plain substring check allows.
    memory_root = (Path.home() / ".claude" / "memory").resolve()
    try:
        note_path = Path(file_path).resolve()
        note_path.relative_to(memory_root)
    except (ValueError, OSError):
        sys.exit(0)

    # Skip auto-generated and indices
    if any(x in file_path for x in ["_auto/", "index.md", "mocs/"]):
        sys.exit(0)

    if not note_path.exists():
        sys.exit(0)

    _MAX_NOTE_BYTES = 256 * 1024
    try:
        if note_path.stat().st_size > _MAX_NOTE_BYTES:
            sys.exit(0)
        content = note_path.read_text(encoding="utf-8", errors="ignore")
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
        update_moc(moc_path, note_path.stem, wikilink, _MAX_NOTE_BYTES)

    sys.exit(0)


def update_moc(moc_path: Path, note_stem: str, wikilink: str, max_bytes: int) -> None:
    """Add `wikilink` to `moc_path`'s "## Recent"/"## New" section if not
    already linked. Extracted from main()'s loop body -- WHY: lets tests
    exercise the actual locked read-modify-write directly, with concrete
    arguments, instead of driving it through main()'s stdin/json.load, which
    a concurrency test previously had to mock.patch per-thread -- and
    unittest.mock.patch is NOT thread-safe when multiple threads patch the
    same global target (json.load, Path.home) concurrently: one thread's
    patch/unpatch can corrupt another's, or leave the patched target broken
    for AN UNRELATED TEST FILE that runs afterward in the same pytest
    process. That mock-thread-safety bug, not the file-locking logic, was
    the root cause of a hard-to-reproduce cross-test data corruption found
    while testing this exact fix.
    """
    if not moc_path.exists():
        return

    try:
        # WHY lock (MEDIUM, cross-model audit): two concurrent note
        # writes routed to the SAME MOC previously raced on this
        # read-modify-write, so one write could overwrite the other's
        # link. Locked per-MOC-file, not globally, so updates to
        # DIFFERENT MOCs in the same run stay independent.
        # WHY timeout=15.0 + acquired-check (real bug, found by a
        # cross-file concurrency test): file_lock()'s default 2.0s
        # timeout yields False rather than raising -- a bare `with
        # file_lock(...):` still enters the block unprotected. Raising
        # here is caught by the except below and warned on stderr, same
        # as any other MOC-write failure -- not silent corruption.
        lock_path = moc_path.with_suffix(".lock")
        with file_lock(lock_path, timeout=15.0) as acquired:
            if not acquired:
                raise TimeoutError(f"Could not acquire MOC lock: {lock_path}")
            if moc_path.stat().st_size > max_bytes:
                return
            # WHY re-read inside the lock: another process may have
            # updated this exact MOC between our first exists()/size
            # check above and acquiring the lock.
            moc_content = moc_path.read_text(encoding="utf-8", errors="ignore")
            # Check if already linked
            if note_stem in moc_content:
                return

            # Find "## Recent" or "## New" section, add link
            if "## Recent" in moc_content:
                moc_content = moc_content.replace("## Recent\n", f"## Recent\n\n- {wikilink}\n")
            elif "## New" in moc_content:
                moc_content = moc_content.replace("## New\n", f"## New\n\n- {wikilink}\n")
            else:
                # Append at end
                moc_content += f"\n\n## Recent\n\n- {wikilink}\n"

            moc_path.write_text(moc_content, encoding="utf-8")
    except Exception as exc:
        # WHY stderr, not silent (LOW, cross-model audit): a failed MOC
        # write previously vanished with zero signal, leaving the MOC
        # index stale with no indication anything went wrong.
        print(f"[moc-autolink] WARNING: failed to update {moc_path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
