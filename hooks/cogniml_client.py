#!/usr/bin/env python3
"""Lightweight CogniML API client — stdlib only, fail-open.

WHY: CogniML (E:\\CogniML 2026) provides vector-based semantic retrieval
over structured Skills (ML experiment knowledge). We use it as a semantic
upgrade over keyword grep: when local search returns < 2 results,
/api/advise finds conceptually similar knowledge that shares no exact words.

Design: all calls have a 2-second timeout and return None on any error.
If CogniML is down, functions fail silently — hooks never block.
"""

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, cast

COGNIML_URL = os.getenv("COGNIML_API_URL", "http://localhost:8400")
# WHY: hooks must not block the UI, but Gemma4 26B needs more time than
# Qwen3 8B for /api/advise synthesis. 8s balances latency vs quality.
_TIMEOUT = 8


def _is_safe_target(url: str, has_token: bool) -> bool:
    """Only send bearer tokens to localhost — CogniML is local-only by design.
    WHY: env-controlled URL (CI poisoning, malicious .envrc) can redirect
    the bearer token to an attacker host. Reuse pattern from webhook_notify.py.
    """
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        if has_token:
            return (p.hostname or "") in ("localhost", "127.0.0.1", "::1")
        return True
    except Exception:
        return False


def _post(path: str, body: dict) -> dict | None:
    """POST JSON to CogniML. Returns parsed response or None on any error."""
    try:
        data = json.dumps(body).encode()
        token = os.getenv("COGNIML_API_BEARER_TOKEN", "")
        if not _is_safe_target(f"{COGNIML_URL}{path}", bool(token)):
            return None
        req = urllib.request.Request(
            f"{COGNIML_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            try:
                return cast(dict[str, Any], json.loads(resp.read()))
            except (json.JSONDecodeError, ValueError) as e:
                # WHY: F18 — network responses may be HTML error pages or partial reads
                return {"error": f"invalid JSON response: {e}"}
    except Exception:
        return None


def advise(query: str, top_k: int = 3) -> str | None:
    """Query CogniML for semantic advice. Returns synthesized answer or None.

    WHY: /api/advise runs vector similarity search + LLM synthesis. This gives
    results keyword grep misses when terminology differs (e.g. "NaN gradients"
    matches "exploding loss" because the embedding space captures semantics).
    """
    result = _post("/api/advise", {"query": query, "top_k": top_k})
    if result and result.get("answer"):
        return str(result["answer"])
    return None


_pushed_cache: set[str] = set()
# WHY: module-level constant so tests can monkeypatch it to a tmp path
_PUSHED_LEDGER: Path = Path.home() / ".claude" / "cache" / "cogniml_pushed.txt"


def push_wiki_entry(title: str, body: str, tags: list[str]) -> str | None:
    """Index a wiki entry into CogniML. Returns skill_id or None.

    WHY: every wiki entry written by session_save.py is pushed here so the
    knowledge is also available via semantic search. 'quick' capture mode
    skips LLM analysis — just structure + embedding.

    Idempotency: uses in-process cache + persistent file to avoid pushing
    the same experiment_id multiple times per session or across sessions.
    """
    slug = title.lower().replace(" ", "-")[:60]
    exp_id = f"wiki-{slug}"

    # WHY: CogniML API has no upsert — each POST creates a new skill with
    # a new UUID. Without this guard, the same wiki entry gets pushed 10+
    # times across sessions, creating 968 skills from 183 unique entries.
    if exp_id in _pushed_cache:
        return None

    # Persistent dedup: check/update a local ledger file
    ledger = _PUSHED_LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    try:
        known = set(ledger.read_text(encoding="utf-8").splitlines()) if ledger.exists() else set()
    except OSError:
        known = set()

    if exp_id in known:
        _pushed_cache.add(exp_id)
        return None

    result = _post(
        "/api/retrospective",
        {
            "experiment_id": exp_id,
            "project_name": "claude-cod",
            "capture_mode": "quick",
            "problem_summary": title,
            # WHY: 1500 chars = COGNIML_EMBED_BODY_CHARS default
            "evidence_notes": [body[:1500]],
            "applicability": tags,
        },
    )

    # Record push regardless of success — avoid retry storm on transient errors
    _pushed_cache.add(exp_id)
    try:
        with ledger.open("a", encoding="utf-8") as f:
            f.write(exp_id + "\n")
    except OSError:
        pass  # WHY: fail-open — dedup is best-effort, must not block hooks

    if result:
        return result.get("skill_id")
    return None
