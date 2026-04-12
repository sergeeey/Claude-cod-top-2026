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

COGNIML_URL = os.getenv("COGNIML_API_URL", "http://localhost:8400")
# WHY: hooks must not block the UI; 2s is plenty for local loopback
_TIMEOUT = 2


def _post(path: str, body: dict) -> dict | None:
    """POST JSON to CogniML. Returns parsed response or None on any error."""
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{COGNIML_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        token = os.getenv("COGNIML_API_BEARER_TOKEN", "")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
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
        return result["answer"]
    return None


def push_wiki_entry(title: str, body: str, tags: list[str]) -> str | None:
    """Index a wiki entry into CogniML. Returns skill_id or None.

    WHY: every wiki entry written by session_save.py is pushed here so the
    knowledge is also available via semantic search. 'quick' capture mode
    skips LLM analysis — just structure + embedding. Fire-and-forget.
    """
    slug = title.lower().replace(" ", "-")[:60]
    result = _post(
        "/api/retrospective",
        {
            "experiment_id": f"wiki-{slug}",
            "project_name": "claude-cod",
            "capture_mode": "quick",
            "problem_summary": title,
            # WHY: 1500 chars = COGNIML_EMBED_BODY_CHARS default
            "evidence_notes": [body[:1500]],
            "applicability": tags,
        },
    )
    if result:
        return result.get("skill_id")
    return None
