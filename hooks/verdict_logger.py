#!/usr/bin/env python3
"""SubagentStop hook: machine-log every reviewer/security-guard verdict, so a
suspected-false-PASS rate can eventually be computed instead of assumed.

WHY: reviewer.md and security-guard.md both issue a structured verdict (VERDICT: LGTM |
NEEDS_WORK | BLOCK, and Verdict: PASS | BLOCK respectively), but today that verdict only
ever exists as chat text -- nothing persists it against the commit/files it was actually
about. There is no way to answer "how often did a reviewer LGTM turn out wrong later?"
without that record. iteration_guard.py already proved this exact extraction pattern works
(SubagentStop -> last_assistant_message -> VERDICT regex) for its own, narrower purpose
(the cap=3 escalation counter); this hook reuses the same shape for a different one:
append-only evidence, not enforcement.

Deliberately NOT reused from iteration_guard.py: this hook is independent (no cross-hook
import) per this repo's own hook-independence convention (hooks/CLAUDE.md: share utils.py,
not each other) -- and its failure mode is different: iteration_guard blocks on the internal
signed eo_loop.json state; this hook only ever appends telemetry and must never affect
control flow if it fails.

Honest scope: only reviewer and security-guard have a machine-parseable verdict format
today. Other agents (verifier, sec-auditor, skeptic, ...) are invisible to this log until
they adopt an equally strict format -- silently skipped, not estimated.

Also records `model` and `run_outcome`, read from the subagent's own transcript at
<projects>/<project>/<session>/subagents/agent-<agent_id>.jsonl. Either one is "unknown" when its
source is missing or unrecognised: no transcript on disk, several transcripts matching the ids,
an unreadable file, unsafe or missing ids in the event, no model or stop_reason on the final
message, or a value outside the documented set. When the transcript cannot be located or read,
both fields are "unknown". A gap is recorded as a gap, never estimated.

Fires on: SubagentStop. Never blocks, never denies, fail-open on every error path.
State: <project>/.claude/memory/verdict_log.jsonl (append-only JSONL, one record per line).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Recursion guard -- must never re-enter when Claude spawns subagents.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

from lib.discovery import find_file_upward
from lib.state import file_lock

SCHEMA_VERSION = 1

# Same shape as iteration_guard.py's _VERDICT_RE, kept independent (see module docstring).
# Case-SENSITIVE on purpose: reviewer.md's template literally reads "VERDICT: LGTM |
# NEEDS_WORK | BLOCK" (all-caps label); security-guard.md's reads "Verdict: PASS / BLOCK"
# (title-case label). For LGTM/NEEDS_WORK/PASS the two never collide anyway, but BLOCK is
# a value both formats use -- label casing is the only real signal that disambiguates it,
# so IGNORECASE would silently misattribute every security-guard BLOCK to reviewer
# (caught by test_extracts_security_guard_block, which is why this isn't IGNORECASE).
# ANCHORED to a line start (2026-11-07, owner-approved): the label must open a line, optionally
# preceded by markdown emphasis or heading marks (`**VERDICT: LGTM**`, `### Verdict: PASS`).
# A bullet or number marker may also precede it (`- VERDICT: LGTM`, `1. **VERDICT: LGTM**`).
# A sentence that merely mentions a verdict mid-line, a `>` quote, or a backtick span is not a
# verdict; neither is a template echo: the value followed ONLY by `|` / `/` separated verdict
# words up to the end of the line (`VERDICT: LGTM | NEEDS_WORK | BLOCK`, `Verdict: PASS / BLOCK`).
# A real line with a conditional tail (`VERDICT: BLOCK / NEEDS_WORK on P1`, `LGTM | see notes`)
# is NOT an echo: it counts, and most-severe-wins then keeps a genuine BLOCK from being outvoted.
# `BLOCKED` is read as BLOCK. hooks/iteration_guard.py still uses its own unanchored regex, so it
# counts some lines (mid-line mentions, echoes) that this logger rejects; left as is on purpose.
# When several anchored verdicts appear the MOST SEVERE wins (see _worst): a quoted PASS or
# LGTM can then never outvote a real BLOCK. Limit, stated: a quoted verdict on its own
# unindented line still looks like a real one, and such a quote can only make a record stricter.
_LINE_START = r"^[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+)?[*_#]*[ \t]*"
_VERDICT_WORD = r"(?:LGTM|NEEDS_WORK|BLOCK|PASS)"
_SEP = r"[ \t*_]*[|/][ \t]*"
# A template echo is (a) a chain of 3+ verdict words, whatever follows it
# (`... | BLOCK  <- one of`), or (b) a chain of any length that runs to the end of the
# line. A 2-word chain WITH a tail (`BLOCK / NEEDS_WORK on P1`) is a real verdict.
_NOT_A_TEMPLATE = (
    r"(?:ED)?\b(?!(?:" + _SEP + _VERDICT_WORD + r"){2}"
    r"|" + _SEP + _VERDICT_WORD + r"(?:" + _SEP + _VERDICT_WORD + r")*[ \t*_]*$)"
)
_SEVERITY = ("BLOCK", "NEEDS_WORK", "LGTM", "PASS")  # most severe first
_REVIEWER_RE = re.compile(
    _LINE_START + r"VERDICT:[ \t ]*[*_]*[ \t ]*(LGTM|NEEDS_WORK|BLOCK)" + _NOT_A_TEMPLATE,
    re.MULTILINE,
)
_SECURITY_GUARD_RE = re.compile(
    _LINE_START + r"Verdict:[ \t ]*[*_]*[ \t ]*(PASS|BLOCK)" + _NOT_A_TEMPLATE,
    re.MULTILINE,
)

# skeptic's scientific verdict. The four tags are NOT new: they are the existing vocabulary of
# rules/skeptic-triggers.md Step 4 (CONFIRMED-REAL / FALSIFIED / WEAKENED / NEEDS-REAL-DATA).
# Evidence levels are the existing audit-verification-gate.md markers, plus UNVERIFIED.
#
# The footer counts only as the TERMINAL contiguous block of SKEPTIC-* lines: everything
# after it must be blank. That one rule is what keeps prose, fenced examples and quoted
# footers from forging a verdict, keeps a reviewer message that merely quotes a footer a
# reviewer message, and stops fields from different blocks being merged (a red-team of the
# first version, 2026-11-07, broke each of those). None of the verdict values is in
# scripts/false_pass_rate.py's PASS_VERDICTS, so skeptic records never count as passes.
SKEPTIC_VERDICTS = ("CONFIRMED-REAL", "FALSIFIED", "WEAKENED", "NEEDS-REAL-DATA")
SKEPTIC_EVIDENCE = ("VERIFIED-REAL", "VERIFIED-SYNTHETIC", "VERIFIED-INLINE", "UNVERIFIED")
_SKEPTIC_PREFIX = "SKEPTIC-"


def _footer_block(message: str) -> list[str]:
    """Lines of the terminal contiguous SKEPTIC-* block ([] when the message has none)."""
    lines = message.replace("\r\n", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    block: list[str] = []
    while lines and lines[-1].startswith(_SKEPTIC_PREFIX):
        block.append(lines.pop().rstrip(" \t"))
    block.reverse()
    return block


def _field(block: list[str], label: str) -> str | None:
    """Last value of `label:` in the block, stripped; None unless it is printable, 1-200 chars."""
    value = None
    for line in block:
        if line.startswith(label + ":"):
            value = line[len(label) + 1 :].strip(" \t")
    # At least one ASCII letter/digit: printable-but-blank characters (U+2800, U+3164, ...)
    # must not pass as a citation. Non-ASCII-only references are downgraded, the safe side.
    if (
        value
        and len(value) <= 200
        and value.isprintable()
        and any(c.isascii() and c.isalnum() for c in value)
        and not _is_placeholder(value)
    ):
        return value
    return None


_PLACEHOLDERS = {
    "n/a", "na", "n.a", "nan", "none", "null", "nil", "tbd", "tba", "todo", "unknown",
    "pending", "x", "-", "?", "...",
}  # fmt: skip


def _is_placeholder(value: str) -> bool:
    """`n/a`, `none yet`, `TBD later`, `N/A (inline)`, `<path>` and the like are not a citation.

    A deny-list on the FIRST word, not a positive "looks like a path" test: a path-shape rule
    would also reject honest references such as a ticket id or a commit hash. Limit, stated:
    free text that merely avoids these words still passes."""
    v = value.strip().lower()
    if (v.startswith("<") and v.endswith(">")) or len(v) < 2:
        return True
    first = v.split()[0].strip(".,;:()[]")
    return v in _PLACEHOLDERS or first in _PLACEHOLDERS


def extract_skeptic_fields(message: str) -> dict[str, str]:
    """Self-reported verification status and references from a skeptic footer.

    These are CLAIMS by the skeptic run, never findings of this hook: the result never
    contains an independence flag (a run that reviews its own author's work cannot attest to
    its own independence -- see hooks/independence_scorer.py, UNKNOWN != INDEPENDENT), and a
    VERIFIED-REAL claim without a usable data reference is downgraded to UNVERIFIED,
    mirroring audit-verification-gate.md ("VERIFIED-REAL needs cited sources").
    """
    block = _footer_block(message)
    data_ref = _field(block, "SKEPTIC-DATA")
    criterion_ref = _field(block, "SKEPTIC-CRITERION")
    evidence = _field(block, "SKEPTIC-EVIDENCE")
    if evidence not in SKEPTIC_EVIDENCE:
        evidence = "UNVERIFIED"
    if evidence == "VERIFIED-REAL" and not data_ref:
        evidence = "UNVERIFIED"
    out = {"evidence_claimed": evidence}
    if criterion_ref:
        out["criterion_ref"] = criterion_ref
    if data_ref:
        out["data_ref"] = data_ref
    return out


def extract_legacy(message: str) -> tuple[str, str] | None:
    """Reviewer / security-guard extraction: label-casing disambiguation, line-start anchored."""
    if not message:
        return None
    message = message.replace("\r\n", "\n")
    found = _REVIEWER_RE.findall(message)
    if found:
        return "reviewer", _worst(found)
    found = _SECURITY_GUARD_RE.findall(message)
    if found:
        return "security-guard", _worst(found)
    return None


def _worst(verdicts: list[str]) -> str:
    return min(verdicts, key=lambda v: _SEVERITY.index(v.upper())).upper()


def extract(message: str) -> tuple[str, str] | None:
    """Return (agent, verdict) from a subagent's final message, or None if unrecognized."""
    if not message:
        return None
    block = _footer_block(message)
    if block:
        verdicts = [
            ln[len("SKEPTIC-VERDICT:") :].strip(" \t")
            for ln in block
            if ln.startswith("SKEPTIC-VERDICT:")
        ]
        valid = [v for v in verdicts if v in SKEPTIC_VERDICTS]
        if valid:
            return "skeptic", valid[-1]
        # A terminal SKEPTIC-* block with no valid verdict is a malformed skeptic footer, never a
        # reviewer / security-guard verdict in disguise (its own text may contain the reviewer
        # pattern). Deliberate trade: a real reviewer message that happens to END in such a
        # block is not logged either -- a lost record, chosen over a forged PASS.
        return None
    return extract_legacy(message)


def _git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _touched_files() -> list[str]:
    """Best-effort union of the last commit's files and the current working-tree diff --
    the verdict could be about either, depending on when in the commit cycle it fired."""
    files: set[str] = set()
    last_commit = _git(["diff", "--name-only", "HEAD~1..HEAD"])
    if last_commit:
        files.update(line for line in last_commit.splitlines() if line)
    working_tree = _git(["diff", "--name-only", "HEAD"])
    if working_tree:
        files.update(line for line in working_tree.splitlines() if line)
    return sorted(files)


def _log_path() -> Path | None:
    anchor = find_file_upward(str(Path(".claude") / "memory" / "activeContext.md"))
    if anchor is None:
        return None
    return anchor.parent / "verdict_log.jsonl"


# WHY: model and run_outcome exist only in the subagent's own transcript, and that file is
# found by path. Both ids are checked against _ID_RE before they reach a glob, so text from
# the event payload cannot widen the search beyond <projects>/*/<session>/subagents/.
_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
# Mapping from the final message's stop_reason. end_turn, max_tokens and refusal are the
# documented meanings; tool_use -> interrupted is an inference: the run ended on a tool call,
# before any answer to it. Any other value is recorded as "unknown", never guessed.
_STOP_TO_OUTCOME = {
    "end_turn": "completed",
    "max_tokens": "truncated",
    "refusal": "refused",
    "tool_use": "interrupted",
}


def _subagent_transcript(data: dict[str, object]) -> Path | None:
    """Return the subagent's transcript path, or None if it is not on disk."""
    session_id = data.get("session_id")
    agent_id = data.get("agent_id")
    if not (isinstance(session_id, str) and isinstance(agent_id, str)):
        return None
    if not (_ID_RE.fullmatch(session_id) and _ID_RE.fullmatch(agent_id)):
        return None
    root = Path.home() / ".claude" / "projects"
    matches = sorted(root.glob(f"*/{session_id}/subagents/agent-{agent_id}.jsonl"))
    # WHY: the same session id under two project folders would make the model a guess, so an
    # ambiguous match counts as absent and is recorded as "unknown".
    return matches[0] if len(matches) == 1 else None


def _last_assistant_meta(path: Path) -> tuple[str | None, str | None]:
    """Return (model, stop_reason) of the final non-synthetic assistant message."""
    # WHY: model and stop_reason come from that one message only. A last-non-null scan over the
    # whole file let an earlier turn's tool_use stand in for a final message with no stop_reason,
    # which mislabelled tool-using runs as interrupted (found on real reviewer transcripts,
    # 2026-10-16).
    last_id: str | None = None
    model_by_id: dict[str, str] = {}
    stop_by_id: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for n, line in enumerate(fh):
            if '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict) or (msg.get("role") or rec.get("type")) != "assistant":
                continue
            if msg.get("model") == "<synthetic>":
                continue
            # one assistant message is written as several records that share its id
            raw_id = msg.get("id")
            mid = raw_id if isinstance(raw_id, str) else f"line-{n}"
            last_id = mid
            if isinstance(msg.get("model"), str):
                model_by_id[mid] = msg["model"]
            if isinstance(msg.get("stop_reason"), str):
                stop_by_id[mid] = msg["stop_reason"]
    if last_id is None:
        return None, None
    return model_by_id.get(last_id), stop_by_id.get(last_id)


def _run_meta(data: dict[str, object]) -> tuple[str, str]:
    """Return (model, run_outcome) for this subagent run; ("unknown", "unknown") on any gap."""
    try:
        transcript = _subagent_transcript(data)
        if transcript is None:
            return "unknown", "unknown"
        model, stop_reason = _last_assistant_meta(transcript)
    except (OSError, RuntimeError, ValueError):  # RuntimeError: Path.home() with no HOME set
        return "unknown", "unknown"
    model_value = model if model and len(model) <= 100 and model.isprintable() else "unknown"
    return model_value, _STOP_TO_OUTCOME.get(stop_reason or "", "unknown")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    result = extract(str(data.get("last_assistant_message", "") or ""))
    if result is None:
        sys.exit(0)
    agent, verdict = result

    # Defensive corroboration only (external review, 2026-07-21, asked "why not read
    # subagent_type/agent_name off the event instead of inferring from label casing").
    # Evidenced answer: iteration_guard.py's own docstring/code establishes that THIS
    # payload shape (SubagentStop) never carries tool_input -- unlike PreToolUse/
    # PostToolUse, it only has last_assistant_message/session_id -- which is exactly why
    # iteration_guard.py, agent_lifecycle.py, and boyko_protocol_guard.py all resort to the
    # same message-content inference this hook uses. If a future Claude Code version DOES
    # add a top-level field, prefer it over the casing heuristic without extra cost; if not
    # (the documented status quo), this is a no-op.
    for key in ("subagent_type", "agent_type", "agent_name"):
        declared = data.get(key)
        if (
            isinstance(declared, str)
            and declared.strip().lower() == "skeptic"
            and agent != "skeptic"
        ):
            sys.exit(0)  # a declared skeptic without a valid footer has no loggable verdict
        if isinstance(declared, str) and declared.strip().lower().replace("_", "-") in (
            "reviewer",
            "security-guard",
        ):
            if agent == "skeptic":
                # a declared reviewer/security-guard run keeps its own verdict format; a
                # skeptic footer inside it is quoted text, not its verdict
                legacy = extract_legacy(str(data.get("last_assistant_message", "") or ""))
                if legacy is None:
                    sys.exit(0)
                agent, verdict = legacy
            else:
                agent = declared.strip().lower().replace("_", "-")
            break

    log_path = _log_path()
    if log_path is None:
        sys.exit(0)  # not inside a project with .claude/memory/ -- nothing to anchor to

    model, run_outcome = _run_meta(data)
    record = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(UTC).isoformat(),
        "agent": agent,
        "verdict": verdict,
        "session_id": str(data.get("session_id", "") or ""),
        "git_head": _git(["rev-parse", "HEAD"]),
        "files": _touched_files(),
        "model": model,
        "run_outcome": run_outcome,
    }
    if agent == "skeptic":
        record.update(extract_skeptic_fields(str(data.get("last_assistant_message", "") or "")))
        agent_id = data.get("agent_id")
        if isinstance(agent_id, str) and _ID_RE.fullmatch(agent_id):
            record["agent_id"] = agent_id

    # WHY file_lock (external review, 2026-07-21): parallel subagents (review-squad runs
    # reviewer + security-guard concurrently) can both hit SubagentStop close together,
    # racing an unlocked `open("a")` append -- POSIX appends are usually safe, but Windows
    # (this repo's own dev environment) has no such append-atomicity guarantee. Same idiom
    # as observation_capture.py: acquire, or skip -- never raise into the session over
    # telemetry, matching this hook's own fail-open contract.
    lock_path = log_path.with_suffix(".lock")
    try:
        with file_lock(lock_path, timeout=5.0) as acquired:
            if not acquired:
                sys.exit(0)  # telemetry only -- skip rather than risk a torn write
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # telemetry only -- never fail the session over a write error

    sys.exit(0)


if __name__ == "__main__":
    main()
