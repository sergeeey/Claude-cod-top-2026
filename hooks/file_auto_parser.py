"""
file_auto_parser.py — UserPromptSubmit hook.

Flow for each file path found in the user's message:
  1. Check doc_registry — if already analyzed: inject recall notice, skip re-parse.
  2. If new: parse with doc_bridge, cache JSON, register in doc_registry.
  3. Inject summary into Claude context via additionalContext.

Token savings: raw Excel 200 rows ≈ 8 000 tokens → parsed JSON ≈ 2 000 tokens.
Dedup savings: analyzed PDF re-mentioned → 0 extra tokens, analysis recalled from wiki.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SUPPORTED_EXT = {".pdf", ".xlsx", ".xls", ".csv", ".tsv", ".json", ".docx"}
CACHE_DIR = Path.home() / ".claude" / "cache" / "parsed"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _hooks_dir() -> str:
    return str(Path(__file__).parent)


def _ensure_hooks_in_path() -> None:
    d = _hooks_dir()
    if d not in sys.path:
        sys.path.insert(0, d)


def extract_paths(text: str) -> list[str]:
    """Extract file paths from a user message (Windows + Unix, quoted + bare)."""
    patterns = [
        r'"([^"]+\.[a-zA-Z]{2,5})"',  # "quoted path"
        r"'([^']+\.[a-zA-Z]{2,5})'",  # 'single quoted'
        r"([A-Za-z]:\\[^\s\"'<>|?*\n]+\.[a-zA-Z]{2,5})",  # Windows absolute
        r"(/(?:[^\s\"'<>|?*\n]+)/[^\s\"'<>|?*\n]+\.[a-zA-Z]{2,5})",  # Unix absolute
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text))
    return list(dict.fromkeys(found))  # dedupe, preserve order


_SHA256_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB


def _cache_key(path: str) -> Path:
    """
    Cache key strategy:
      small files (< 10 MB) → SHA256(content): survives rsync --no-times, git checkout
      large files (≥ 10 MB) → md5(path + mtime): avoids reading 100 MB on every prompt
    """
    from hashlib import md5, sha256

    p = Path(path)
    stem = p.stem[:40]
    if p.stat().st_size < _SHA256_SIZE_LIMIT:
        key = sha256(p.read_bytes()).hexdigest()[:12]
    else:
        key = md5((path + str(p.stat().st_mtime)).encode()).hexdigest()[:8]
    return CACHE_DIR / f"{stem}-{key}.json"


def _emit(event: str, context: str) -> None:
    """Write additionalContext JSON to stdout — the only channel into Claude's context."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": context,
                }
            }
        )
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    prompt = hook_input.get("prompt", "")
    candidates = extract_paths(prompt)
    targets = [
        p for p in candidates if Path(p).suffix.lower() in SUPPORTED_EXT and Path(p).exists()
    ]

    if not targets:
        sys.exit(0)

    _ensure_hooks_in_path()

    try:
        import doc_bridge
        import doc_registry
    except ImportError as e:
        print(f"[file-auto-parser] IMPORT ERROR: {e}", file=sys.stderr)
        sys.exit(0)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    recall_lines: list[str] = []  # files already in registry
    fresh_lines: list[str] = []  # files parsed for the first time

    for path in targets:
        # ── 1. Check registry first ───────────────────────────────────────
        try:
            existing = doc_registry.lookup(path)
        except Exception:
            existing = None

        if existing:
            recall_lines.append(doc_registry.format_recall(existing))
            # Update last_seen timestamp silently
            try:
                doc_registry.register(path)
            except Exception:
                pass
            continue  # skip re-parsing — we have the analysis

        # ── 2. Parse (new file) ───────────────────────────────────────────
        cached = _cache_key(path)
        label = ""

        if cached.exists():
            try:
                with open(cached, encoding="utf-8") as f:
                    parsed = json.load(f)
                label = "(cached)"
            except Exception:
                parsed = doc_bridge.parse(path)
                label = "(re-parsed)"
        else:
            parsed = doc_bridge.parse(path)
            label = "(fresh)"
            try:
                with open(cached, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, ensure_ascii=False, indent=2, default=str)
            except Exception as e:
                label = f"(no-cache: {e})"

        summary = doc_bridge.summarize(parsed)

        # ── 3. Register in doc_registry ───────────────────────────────────
        try:
            doc_registry.register(path, parsed_summary=summary)
        except Exception:
            pass

        fresh_lines.append(f"  • {summary} {label}")
        fresh_lines.append(f"    cache → {cached}")

    # ── Build context injection ────────────────────────────────────────────
    parts: list[str] = []

    if recall_lines:
        parts.append("\n".join(recall_lines))

    if fresh_lines:
        parts.append(
            f"[file-auto-parser] Parsed {len(fresh_lines) // 2} new file(s):\n"
            + "\n".join(fresh_lines)
            + "\nTip: after analysis run /data-bridge annotate to save to wiki."
        )

    if parts:
        _emit("UserPromptSubmit", "\n\n".join(parts))

    sys.exit(0)


if __name__ == "__main__":
    main()
