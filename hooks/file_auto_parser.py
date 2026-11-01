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

# WHY these constants exist at all (credential-disclosure gap, found live
# 2026-09-12): this hook parses ANY supported-extension file merely NAMED in
# chat text -- no tool call, no permission_policy.py gate of any kind, since
# it fires on UserPromptSubmit, not PreToolUse. Confirmed live on this exact
# machine: mentioning `~/.claude/.credentials.json` (Claude Code's own OAuth
# accessToken/refreshToken plus ~26 MCP plugins' OAuth material) and
# `~/.claude.json` (the full MCP config) caused both to be fully parsed and
# cached in plaintext under CACHE_DIR, then RE-INGESTED a second time when a
# review report merely quoted the resulting cache file's own path back into
# chat -- a live, self-perpetuating feedback loop, not a one-off.
#
# WHY a location gate, not just a name denylist (skeptic + sec-auditor
# design review, 2026-09-12, DDD Trigger 3): a name-substring check alone
# (permission_policy.py's SENSITIVE_PATH_PATTERNS, imported below as a
# SECOND, independent layer) was falsified against this exact incident --
# `~/.claude.json` matched none of that tuple's entries at review time, and
# even now that it's been added there (Credential Non-Possession P1.1,
# #436), a cache file this hook itself writes is named from the SOURCE
# path's `Path.stem` (`.claude.json` -> `.claude-<hash>.json`), which no
# longer contains the literal substring that made the original sensitive --
# reproduced live during this same review when a report path
# `.claude-3fd5529b05f0.json` (an existing secret-containing cache file) was
# mentioned and re-parsed into a THIRD copy.
#
# WHY a path-COMPONENT check, not `is_relative_to(root)` (revised, sec-
# auditor-found, live-verified 2026-09-12 against a real existing cache file
# on this machine -- a first cut of this fix used `is_relative_to` against
# drive-rooted `_HOME / ".claude"` etc. and was falsified): `Path.resolve()`
# does NOT canonicalize a Windows extended-length prefix (`\\?\C:\...`) or a
# UNC admin-share form (`\\localhost\C$\...`) -- both resolve to THEMSELVES,
# so a drive-rooted `is_relative_to()` check returns False for the exact
# same file the root check was written to catch. Confirmed live: a probe
# using `\\?\` plus an existing `~/.claude/cache/parsed/*.json` file
# returned sensitive=False. Worse than a silent miss: `extract_paths()`'s
# quoted-string regex and its Windows-absolute regex both match a single
# quoted `\\?\`-prefixed path, yielding TWO candidates -- the unprefixed one
# is correctly caught and reported in the "Skipped N" notice, while the
# prefixed twin sails through in the SAME run, so the notice actively
# reassures while the leak still happens.
#
# A component check closes this (and the UNC case, and a symlinked/
# junctioned ~/.claude, all in one construct, confirmed by directly
# inspecting `Path.parts` for both prefixed forms) because pathlib still
# segments a `\\?\`- or UNC-form path on its `\` separators the same way --
# it doesn't need the prefix to be canonicalized to see a literal
# `.claude`/`.ssh`/`.aws` component in it. This also makes it a strict
# superset of the drive-rooted check it replaces (a normal `C:\Users\<u>\
# .claude\...` path has `.claude` as a component too), so there is no
# separate root-based check left to maintain. It also catches a project-
# local `.claude/` directory (this repo has one), not just the home one --
# a deliberate widening, not a bug: `.claude/` directories carry Claude
# Code's own config/hook-state files at any level, never research data this
# hook exists to parse, and this machine's own doc_registry.json already
# shows a project-local `.claude/settings.local.json` was auto-parsed
# historically under the pre-fix behavior.
#
# `~/.claude.json` itself needs a SEPARATE exact-file check because it is a
# sibling of `.claude/`, not inside it -- its own basename never appears as
# a `.claude`-only path component (the last component is `.claude.json`,
# not `.claude`).
_HOME = Path.home().resolve()
_CONFIG_EXACT_FILES: tuple[Path, ...] = (_HOME / ".claude.json",)
_CONFIG_SEGMENTS: frozenset[str] = frozenset({".claude", ".ssh", ".aws"})

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


def _is_sensitive_path(path: str, name_patterns: tuple[str, ...]) -> bool:
    r"""True if *path* is Claude Code's own credential/config surface, or its
    literal or resolved form names a known credential-file pattern.

    Two independent checks (both required -- neither alone survived the
    2026-09-12 skeptic + sec-auditor review, see the WHY block above
    `_CONFIG_EXACT_FILES`):

    1. Location (`_CONFIG_SEGMENTS`/`_CONFIG_EXACT_FILES`): structural, not
       name-based -- catches `.credentials.json`, `~/.claude.json`, and any
       renamed/hashed cache derivative of either, without needing to guess
       a filename shape. Component-based (checks `Path.parts`), not a
       drive-rooted `is_relative_to()` comparison, specifically because the
       latter was falsified against a real Windows extended-length-prefix
       (`\\?\C:\...`) and UNC admin-share (`\\host\C$\...`) bypass -- see
       the WHY block above for the live reproduction.
    2. Name (`name_patterns`, the caller's SENSITIVE_PATH_PATTERNS):
       catches a similarly-sensitive file living OUTSIDE those roots (a
       project's own `.mcp.json`, an exported `credentials.json` in
       Downloads). Checked against BOTH the raw candidate string and its
       resolved form -- the raw string alone misses a `..` traversal
       segment or a symlink target; resolve() alone misses a path that no
       longer exists by the time this runs (`Path.resolve()` still
       succeeds on Windows/POSIX for a nonexistent path, so this is a
       belt-and-suspenders check, not a correctness requirement).
    """
    try:
        resolved: Path | None = Path(path).resolve()
    except (OSError, ValueError):
        resolved = None

    if resolved is not None:
        if resolved in _CONFIG_EXACT_FILES:
            return True
        if any(part.lower() in _CONFIG_SEGMENTS for part in resolved.parts):
            return True

    candidates = [path]
    if resolved is not None:
        candidates.append(str(resolved))
    for raw in candidates:
        scan = raw.replace("\\", "/").lower()
        if scan and any(pattern in scan for pattern in name_patterns):
            return True
    return False


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
        # WHY usedforsecurity=False: this digest is a cache-key fingerprint
        # over path+mtime, never an integrity/auth check -- and it is
        # truncated to 32 bits below, so md5-vs-sha256 is irrelevant to its
        # collision profile. The flag marks the non-security intent
        # (flagged by an external bandit-style audit; ruff's `S` ruleset is
        # not enabled in this repo) and lets the call succeed on
        # FIPS-enforcing builds, where a bare md5() raises ValueError at
        # call time.
        key = md5((path + str(p.stat().st_mtime)).encode(), usedforsecurity=False).hexdigest()[:8]
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
    existing_candidates = [
        p for p in candidates if Path(p).suffix.lower() in SUPPORTED_EXT and Path(p).exists()
    ]

    if not existing_candidates:
        sys.exit(0)

    _ensure_hooks_in_path()

    # WHY the sensitivity import lives in this SAME try/except as
    # doc_bridge/doc_registry, not a separate one (sec-auditor-found,
    # 2026-09-12): file_auto_parser.py is `fail_mode: open` (hooks/
    # registry.yaml) -- its own PARSING function should degrade gracefully
    # on error. But a security GATE degrading to "gate disabled, parse
    # everything" on the exact same ImportError is the wrong failure
    # direction. Sharing this block means an import failure takes the
    # already-existing `sys.exit(0)` path below -- nothing gets parsed or
    # cached at all -- which is fail-open for hook *availability* and
    # fail-closed for *disclosure* at the same time, with no separate
    # fallback branch that could silently ship "filter off".
    try:
        import doc_bridge
        import doc_registry
        from permission_policy import SENSITIVE_PATH_PATTERNS
    except ImportError as e:
        print(f"[file-auto-parser] IMPORT ERROR: {e}", file=sys.stderr)
        sys.exit(0)

    skipped_sensitive = [
        p for p in existing_candidates if _is_sensitive_path(p, SENSITIVE_PATH_PATTERNS)
    ]
    targets = [p for p in existing_candidates if p not in skipped_sensitive]

    if skipped_sensitive:
        # WHY stderr, not _emit()/additionalContext (sec-auditor-found,
        # 2026-09-12): the path was already visible to Claude in the user's
        # own prompt regardless of what this hook does, so naming it again
        # in additionalContext discloses nothing new about the PATH -- but
        # announcing "N credential-looking files were skipped" IN CONTEXT
        # is itself a signal that something worth reading sits there, and
        # Read has zero gate on any path (permission_policy.py's
        # ALWAYS_SAFE_TOOLS). stderr keeps this debuggable (visible to the
        # user/operator) without adding a second-order pointer into the
        # live conversation.
        print(
            f"[file-auto-parser] Skipped {len(skipped_sensitive)} "
            "credential/config-looking path(s) -- not parsed or cached.",
            file=sys.stderr,
        )

    if not targets:
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
