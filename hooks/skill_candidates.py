#!/usr/bin/env python3
"""UserPromptSubmit hook: advisory skill candidates from a full-text index of ALL available skills.

WHY (research note docs/audits/skill-discovery-research-2026-11-24.md): the native skill list shows
a description for only a fraction of the library, and asking the model to search on its own did not
happen (0 of 11 fresh sessions). The decision to look is therefore moved out of the model: this hook
runs the local BM25 search (scripts/skill_search.py) on each user message and, only when the
match is
confident, adds at most two candidates as context. The model keeps every right: ignore them, combine
them, or do the task without a skill. Nothing blocks, nothing is mandatory, and a missing or failing
search simply produces no output.

Not a safety classifier: it never reads or changes the routing-floor tiers
(routing_floor_classifier.py) and shares no state with them.

Behaviour:
- Skips slash commands (the user already named a skill), very short or continuation messages, and
  messages with too few content terms to say anything.
- Each skill is offered at most once per session, so a later sub-task can still surface a new skill
  but the same one is not repeated.
- Search runs against the skills Claude Code can really load (project scope and skillOverrides
  honoured through skill_search's own discovery).
- Kill switch: SKILL_CANDIDATES=0. Experiment mode (off unless set): SKILL_CANDIDATES_HOLDOUT=<p>
  withholds the candidates with probability p (decided by a hash of session and message) and, if
  SKILL_CANDIDATES_LOG is a path, appends one counts-only JSON line per decision (no message text).

Fires on: UserPromptSubmit. Non-blocking, fail-open, recursion-guarded.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

if os.environ.get("CLAUDE_INVOKED_BY") or os.environ.get("SKILL_CANDIDATES") == "0":
    sys.exit(0)

from lib.runtime import emit_hook_result, hook_main, parse_stdin, strip_non_user_content
from lib.state import atomic_write_json, load_json_state

MIN_CONTENT_TERMS = 5  # fewer distinct content words than this: a continuation, not a task
MAX_CANDIDATES = 2
STATE_DIR = Path.home() / ".claude" / "state"
STATE_KEEP_SECONDS = 7 * 24 * 3600


def _load_search() -> Any:
    """Import scripts/skill_search.py from the sibling scripts/ folder (repo and ~/.claude)."""
    import importlib.util  # function-level: optional, and keeps the module-level imports minimal

    path = Path(__file__).resolve().parent.parent / "scripts" / "skill_search.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("skill_search_impl", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("skill_search_impl", mod)
    spec.loader.exec_module(mod)
    return mod


def _short(text: str, n: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _state_path(session_id: str) -> Path:
    return STATE_DIR / f"skill_candidates_{hashlib.sha1(session_id.encode()).hexdigest()[:12]}.json"


def _prune(now: float) -> None:
    try:
        for f in STATE_DIR.glob("skill_candidates_*.json"):
            if now - f.stat().st_mtime > STATE_KEEP_SECONDS:
                f.unlink()
    except OSError:
        pass


def _held_out(session_id: str, prompt: str) -> bool | None:
    """None when experiment mode is off; otherwise True if this message is in the control arm."""
    raw = os.environ.get("SKILL_CANDIDATES_HOLDOUT")
    if not raw:
        return None
    try:
        p = float(raw)
    except ValueError:
        return None
    h = hashlib.sha256(f"{session_id}|{prompt}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64 < p


def _log(record: dict) -> None:
    path = os.environ.get("SKILL_CANDIDATES_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> None:
    try:
        data = parse_stdin()
    except Exception:
        sys.exit(0)
    prompt = strip_non_user_content(str(data.get("prompt", "") or "")).strip()
    if not prompt or prompt.startswith("/"):
        sys.exit(0)
    ss = _load_search()
    if ss is None or len(set(ss.tokenize(prompt))) < MIN_CONTENT_TERMS:
        sys.exit(0)

    t0 = time.perf_counter()
    session_id = str(data.get("session_id", "") or "no-session")
    project = Path(str(data.get("cwd") or os.getcwd()))
    res = ss.search(prompt, Path.home() / ".claude", project=project, top=MAX_CANDIDATES + 3)
    if not res["confident"]:
        sys.exit(0)

    state_file = _state_path(session_id)
    shown = load_json_state(state_file).get("shown", [])
    fresh = [c for c in res["candidates"] if c["name"] not in shown][:MAX_CANDIDATES]
    if not fresh:
        sys.exit(0)

    arm = _held_out(session_id, prompt)
    _log(
        {
            "ts": int(time.time()),
            "session": hashlib.sha1(session_id.encode()).hexdigest()[:10],
            "arm": "none" if arm is None else ("control" if arm else "treatment"),
            "names": [c["name"] for c in fresh],
            "seconds": round(time.perf_counter() - t0, 3),
        }
    )
    if arm:
        sys.exit(0)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(state_file, {"shown": [*shown, *[c["name"] for c in fresh]]})
    _prune(time.time())
    lines = [
        "[skill-candidates] Full-text match of this message against all available skills "
        "(advisory: the native skill list stays first; use one, combine them, or ignore "
        "them and do the task directly):"
    ]
    lines += [f"{i}. {c['name']}: {_short(c['purpose'])}" for i, c in enumerate(fresh, 1)]
    emit_hook_result("UserPromptSubmit", "\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
