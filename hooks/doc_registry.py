"""
doc_registry.py — Document deduplication registry.

Maps sha256(file_content) → {parsed_summary, wiki_path, analysis_title, tags}.
Prevents re-analyzing files that were already processed in past sessions.

KEY DESIGN: uses sha256 of CONTENT (not path) — survives file moves, copies,
renames. Same paper downloaded twice to different folders = same registry entry.

Used by:
  file_auto_parser.py  — auto-check on every UserPromptSubmit
  data-bridge skill    — manual register / annotate / list
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils import file_lock

REGISTRY_PATH = Path.home() / ".claude" / "cache" / "doc_registry.json"
# WHY (MEDIUM, cross-model audit): register()/annotate() both do a
# load-mutate-save sequence with no locking, so two concurrent registrations
# can both load the same "before" state and the later save silently loses
# the earlier one's update. _save()'s own os.replace() is atomic for the
# FILE SWAP, but does nothing for the read-modify-write spanning multiple
# calls above it.
_LOCK_PATH = REGISTRY_PATH.with_suffix(".lock")


# ── I/O ──────────────────────────────────────────────────────────────────────


def _load() -> dict[str, Any]:
    """Load registry. Returns empty dict if missing or corrupt."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            result: dict[str, Any] = json.load(f)
            return result
    except Exception:
        return {}


def _save(registry: dict[str, Any]) -> None:
    """Atomic write — temp file + os.replace, safe on Windows and POSIX."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2, default=str)
    # WHY retry on PermissionError (same real race found via a 20-thread
    # concurrency test in the sibling expert_registry.py): register()/
    # annotate() hold _LOCK_PATH during _save(), but read-only callers
    # (lookup(), list_all()) call _load() WITHOUT the lock by design, so
    # they don't serialize behind every write. On Windows, os.replace() can
    # transiently fail with PermissionError/WinError 5 if ANY reader has
    # REGISTRY_PATH open at that exact instant -- a short retry closes this
    # well-known Windows-specific race without forcing every read to take
    # the write lock too.
    last_exc: PermissionError | None = None
    for attempt in range(5):
        try:
            os.replace(str(tmp), str(REGISTRY_PATH))
            return
        except PermissionError as exc:
            last_exc = exc
            if attempt < 4:
                time.sleep(0.02 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


# ── Core ops ──────────────────────────────────────────────────────────────────


def sha256_of_file(path: str) -> str:
    """SHA-256 of file bytes. Key invariant: same content → same hash."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def lookup(path: str) -> dict[str, Any] | None:
    """
    Check if file at *path* is already registered.
    Returns entry dict or None if unknown.

    Raises OSError only if the file doesn't exist at all.
    """
    sha = sha256_of_file(path)
    return _load().get(sha)


def register(
    path: str,
    *,
    parsed_summary: str = "",
    wiki_path: str = "",
    analysis_title: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Register a file (create or update entry).

    Call this immediately after parsing to ensure the file is tracked.
    Call annotate() later when the analysis wiki note exists.

    Returns the entry dict.
    """
    sha = sha256_of_file(path)
    # WHY timeout=15.0 + explicit acquired-check (real bug found by a
    # cross-file concurrency test, not just reasoning): file_lock()'s
    # default timeout is 2.0s and, on timeout, YIELDS False rather than
    # raising -- `with file_lock(...):` still ENTERS the block even when
    # the lock was never acquired. Under real multi-file contention (40+
    # threads across two hooks' locks), some caller's wait exceeded 2s,
    # so it proceeded WITHOUT exclusivity, reintroducing the exact
    # lost-update race this lock exists to prevent (confirmed via a
    # deliberately-shortened timeout reproducing the corruption). 15s is
    # far more than any realistic JSON read-modify-write should ever need;
    # raising instead of silently proceeding means a genuine timeout
    # surfaces as an error, not silent data loss.
    with file_lock(_LOCK_PATH, timeout=15.0) as acquired:
        if not acquired:
            raise TimeoutError(f"Could not acquire doc_registry lock: {_LOCK_PATH}")
        registry = _load()
        now = datetime.now(UTC).isoformat()
        existing = registry.get(sha, {})

        entry: dict[str, Any] = {
            "sha256": sha,
            "filename": Path(path).name,
            "original_path": str(Path(path).resolve()),
            "registered_at": existing.get("registered_at", now),
            "last_seen_at": now,
            "parsed_summary": parsed_summary or existing.get("parsed_summary", ""),
            "wiki_path": wiki_path or existing.get("wiki_path", ""),
            "analysis_title": analysis_title or existing.get("analysis_title", ""),
            "tags": tags if tags is not None else existing.get("tags", []),
            "analyzed": bool(wiki_path or existing.get("wiki_path")),
        }
        registry[sha] = entry
        _save(registry)
    return entry


def annotate(
    path: str,
    *,
    wiki_path: str = "",
    analysis_title: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Add analysis metadata to an already-registered file.

    Call this AFTER Claude finishes analyzing a document and the wiki note exists.
    Returns updated entry, or None if file not in registry (register first).
    """
    sha = sha256_of_file(path)
    # WHY timeout=15.0 + acquired-check: see register() above for the full
    # explanation (real bug, confirmed via a cross-file concurrency test).
    with file_lock(_LOCK_PATH, timeout=15.0) as acquired:
        if not acquired:
            raise TimeoutError(f"Could not acquire doc_registry lock: {_LOCK_PATH}")
        registry = _load()
        if sha not in registry:
            return None

        if wiki_path:
            registry[sha]["wiki_path"] = wiki_path
            registry[sha]["analyzed"] = True
        if analysis_title:
            registry[sha]["analysis_title"] = analysis_title
        if tags is not None:
            registry[sha]["tags"] = tags
        registry[sha]["last_seen_at"] = datetime.now(UTC).isoformat()
        _save(registry)
        result: dict[str, Any] = registry[sha]
    return result


def list_all() -> list[dict[str, Any]]:
    """All registered files, newest last_seen first."""
    return sorted(
        _load().values(),
        key=lambda e: e.get("last_seen_at", ""),
        reverse=True,
    )


# ── Formatting ────────────────────────────────────────────────────────────────


def format_recall(entry: dict[str, Any]) -> str:
    """
    Format a registry entry as a context-injection string for additionalContext.
    Designed to be compact — Claude needs to see it's already done, not re-read the whole doc.
    """
    name = entry["filename"]
    date = entry.get("registered_at", "?")[:10]
    summary = entry.get("parsed_summary") or "no structural summary"
    title = entry.get("analysis_title", "")
    wiki = entry.get("wiki_path", "")
    tags = ", ".join(entry.get("tags", [])) or "—"

    lines = [f"⚑ [DOC-REGISTRY] File already in registry: {name} (first seen {date})"]
    if title:
        lines.append(f"  Analysis: {title}")
    lines.append(f"  Structure: {summary}")
    lines.append(f"  Tags: {tags}")
    if wiki:
        lines.append(f"  Wiki note: {wiki}")
        lines.append(
            "  ↳ DO NOT re-analyze from scratch — load wiki note above and continue from there."
        )
    else:
        lines.append("  ↳ No wiki note yet. After analysis, run: /data-bridge annotate to save.")
    return "\n".join(lines)
