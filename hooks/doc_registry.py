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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path.home() / ".claude" / "cache" / "doc_registry.json"


# ── I/O ──────────────────────────────────────────────────────────────────────


def _load() -> dict[str, Any]:
    """Load registry. Returns empty dict if missing or corrupt."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(registry: dict[str, Any]) -> None:
    """Atomic write — temp file + os.replace, safe on Windows and POSIX."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2, default=str)
    os.replace(str(tmp), str(REGISTRY_PATH))


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
    return registry[sha]


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
