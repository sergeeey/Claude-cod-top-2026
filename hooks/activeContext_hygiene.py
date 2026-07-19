#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: soft-nudge on unmarked narrative claims in activeContext.md.

WHY: RDR 2.1 preprint (Boyko, §6.4/Table 9) names a "Checkpoint Fidelity" criterion —
what may be carried forward as active state vs what must not (narrative summaries
without provenance, old claims without status). Skeptic red-team (2026-07-19, DDD
mode) verdict on this specific gap was BUILD_LIGHT, with one hard condition: the
linter must catch, as a positive control, the exact failure this repo already lived
through — a "~600/701 orphaned git.exe processes" claim that propagated unverified
across 9+ sessions in THIS file's own CURRENT STATE section (see
tests/test_activecontext_hygiene.py::test_positive_control_catches_the_real_incident).

Detection: an approximate/bare numeric claim (~N, около N, примерно N, roughly N) or
a hedge verb (кажется, вероятно, похоже, seems, probably, apparently) with NO
evidence marker ([VERIFIED]/[INFERRED]/[MEMORY]/[WEAK]/[CONFLICTING]/[UNKNOWN]/
[DOCS]/[CODE], per integrity.md's vocabulary) anywhere in the same paragraph.

WHY approximate-only, not any exact number: an exact-count claim ("2317 tests
passed") is this project's own normal evidence-heavy writing style throughout this
very session — flagging every exact number would nag on nearly every state update,
eroding trust exactly the way skeptic-triggers.md § Calibration warns against.
"~600" was itself an APPROXIMATE, unsourced figure — that specific shape is the
signal, not "any digit."

Does NOT: classify fact vs decision, auto-prune anything, block the edit (PostToolUse
fires after the edit already happened). Only path: activeContext.md (exact filename
match — covers both the canonical and legacy `_auto/` locations per
memory-protocol.md's dual-path convention, since this checks the filename suffix,
not the full relative path).
"""

from __future__ import annotations

import os
import re
import sys

from utils import emit_hook_result, get_tool_input, log_hook_trigger, parse_stdin

HOOK_NAME = "activeContext_hygiene"

_TARGET_FILENAME = "activeContext.md"

_EVIDENCE_MARKER = re.compile(
    r"\[(?:VERIFIED|INFERRED|MEMORY|WEAK|CONFLICTING|UNKNOWN|DOCS|CODE)[^\]]*\]"
)

# WHY approximate-prefixed only (not bare digits): see module docstring.
_NUMERIC_CLAIM = re.compile(r"(?:~|около\s+|примерно\s+|roughly\s+)\d+")

_HEDGE_VERB = re.compile(
    r"\b(?:кажется|вероятно|похоже|возможно|seems|probably|apparently|likely)\b",
    re.IGNORECASE,
)

_MAX_SHOWN = 5
_SNIPPET_LEN = 150


def scan_paragraphs(text: str) -> list[str]:
    """Pure core (no I/O — unit-testable): return flagged paragraph snippets.

    A paragraph is flagged if it contains a numeric-claim or hedge-verb shape
    AND has no evidence marker anywhere in it. Paragraphs are split on blank
    lines, matching how activeContext.md's own CURRENT STATE table rows and
    Recent-findings log entries are actually written (one claim per block).
    """
    flagged: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if not para.strip():
            continue
        if _EVIDENCE_MARKER.search(para):
            continue
        if _NUMERIC_CLAIM.search(para) or _HEDGE_VERB.search(para):
            snippet = " ".join(para.split())[:_SNIPPET_LEN]
            flagged.append(snippet)
    return flagged


def _new_text_from_tool_input(tool_name: str, tool_input: dict) -> str:
    # WHY `or ""` not `.get(key, "")`: the default only fires on a MISSING key.
    # An explicit `None` value (e.g. content: null) would otherwise round-trip
    # through str(None) into the literal 4-char string "None" -- benign today
    # only because "None" happens to match neither _NUMERIC_CLAIM nor
    # _HEDGE_VERB, but the same trap already caused real bugs twice earlier
    # this session (gate 9's depends_on: None, gate 10's maturity_evidence:
    # null in check_architecture.py) -- fixing proactively before a pattern
    # change makes it exploitable.
    if tool_name == "Write":
        return str(tool_input.get("content") or "")
    if tool_name == "Edit":
        return str(tool_input.get("new_string") or "")
    return ""


def _nudge_message(flagged: list[str]) -> str:
    shown = "\n".join(f"  - {s}" for s in flagged[:_MAX_SHOWN])
    more = f"\n  (+{len(flagged) - _MAX_SHOWN} more)" if len(flagged) > _MAX_SHOWN else ""
    return (
        f"[activeContext-hygiene] {len(flagged)} claim(s) in this edit look like "
        "narrative without an evidence marker (RDR 2.1 Checkpoint Fidelity, Table 9):\n"
        f"{shown}{more}\n"
        "Tag with [VERIFIED]/[INFERRED]/[MEMORY]/[WEAK]/[UNKNOWN] per integrity.md, "
        "or rephrase — unmarked approximate/hedged claims are exactly how the "
        "'~600 orphaned git.exe processes' claim propagated unverified for 9+ "
        "sessions in this same file. Soft nudge only — not blocked, not deleted."
    )


def main() -> None:
    # WHY: recursion guard — a subagent's own edits must not trip this hook.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    tool_input = get_tool_input(data)
    path = str(tool_input.get("file_path") or "").replace("\\", "/")
    if not path.endswith(_TARGET_FILENAME):
        sys.exit(0)

    new_text = _new_text_from_tool_input(tool_name, tool_input)
    if not new_text:
        sys.exit(0)

    flagged = scan_paragraphs(new_text)
    if not flagged:
        sys.exit(0)

    log_hook_trigger(
        hook_name=HOOK_NAME,
        trigger_type="unmarked_narrative_claim",
        action="warning",
        sample=flagged[0],
        session_id=data.get("session_id", "default"),
    )
    emit_hook_result("PostToolUse", _nudge_message(flagged))


if __name__ == "__main__":
    main()
