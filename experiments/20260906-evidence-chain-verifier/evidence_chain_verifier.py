"""Prototype only — not wired into check_architecture.py / Gate 10.

Core design decision (this is the whole point of the prototype): the verifier
NEVER trusts a hash chain or "here is the log" blob handed to it by the party
being verified. It independently re-locates the claimed content inside the
real, harness-authored session transcript file on disk. A hash chain that is
merely internally self-consistent proves nothing — it can be fabricated
entirely offline (this is exactly test #4 below, and exactly the flaw a
reviewer identified in the naive "agent hash-chains its own log" design).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class VerdictResult:
    verdict: str  # ACCEPT / REJECT
    reason: str


def find_in_transcript(transcript_path: str, needle: str) -> list[int]:
    """Independent search: does this exact content exist, verbatim, in the
    real harness-written transcript file? Returns matching line numbers.
    This is the step that a self-supplied hash chain cannot substitute for.
    """
    hits = []
    with open(transcript_path, encoding="utf-8", errors="ignore") as f:
        for lineno, line in enumerate(f, start=1):
            if needle in line:
                hits.append(lineno)
    return hits


def verify_claimed_agent_run(
    transcript_path: str,
    claimed_description_marker: str,
    claimed_report_verdict_snippet: str,
) -> VerdictResult:
    """Test harness for one (report, transcript) pair.

    claimed_description_marker: a string that should appear verbatim in the
      real transcript if the Agent call genuinely happened (e.g. the Agent
      tool's "description" field text).
    claimed_report_verdict_snippet: a string the benchmark report claims is
      the outcome/content of that run — checked against what the real
      transcript actually contains near the matched entry.
    """
    hits = find_in_transcript(transcript_path, claimed_description_marker)
    if not hits:
        return VerdictResult(
            "REJECT",
            f"marker {claimed_description_marker!r} not found anywhere in "
            f"real transcript {transcript_path} — no harness-authored record "
            f"of this run existing at all.",
        )

    # Load the full transcript once, locate the tool_use block matching the
    # marker, then find its paired tool_result (by tool_use_id) — both must
    # be real, harness-written JSONL entries, not supplied by the claimant.
    with open(transcript_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    tool_use_id = None
    for lineno in hits:
        raw = lines[lineno - 1]
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        content = obj.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Agent"
                    and claimed_description_marker in json.dumps(block.get("input", {}))
                ):
                    tool_use_id = block.get("id")
                    break
        if tool_use_id:
            break

    if not tool_use_id:
        return VerdictResult(
            "REJECT",
            "marker string appears in transcript, but not as a real Agent "
            "tool_use block — insufficient evidence of a real sub-agent run.",
        )

    # Find the paired tool_result for this tool_use_id, real content only.
    result_text = None
    for raw in lines:
        if tool_use_id not in raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        content = obj.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and block.get("tool_use_id") == tool_use_id
                ):
                    c = block.get("content", "")
                    result_text = c if isinstance(c, str) else json.dumps(c)
                    break
        if result_text:
            break

    if result_text is None:
        return VerdictResult(
            "REJECT",
            "found the real tool_use call, but no matching real tool_result "
            "in the transcript — run may not have completed, or evidence "
            "is incomplete.",
        )

    # WHY: background agents in this harness return only a launch ack as the
    # immediate tool_result ("Async agent launched... agentId: XXXX"). The
    # real result arrives later as a harness-authored <task-notification>
    # entry (found by grepping this transcript directly, not assumed) keyed
    # by that agentId, not by tool_use_id. Fall through to it here so a
    # background agent's real content is checked, not just its launch ack.
    if "agentId:" in result_text:
        agent_id = result_text.split("agentId:")[1].strip().split()[0]
        for raw in lines:
            if f"<task-id>{agent_id}</task-id>" in raw:
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg_content = obj.get("message", {}).get("content", "")
                if isinstance(msg_content, str) and f"<task-id>{agent_id}</task-id>" in msg_content:
                    result_text = msg_content
                    break

    if claimed_report_verdict_snippet not in result_text:
        return VerdictResult(
            "REJECT",
            f"report claims {claimed_report_verdict_snippet!r}, but the real "
            f"harness-recorded tool_result does not contain this — report "
            f"contradicts the actual transcript content.",
        )

    return VerdictResult(
        "ACCEPT",
        "marker + real tool_use + real tool_result all found in the actual "
        "harness-written transcript, and report content matches.",
    )


def verify_fabricated_standalone_log(fabricated_log_entries: list[dict]) -> VerdictResult:
    """This function represents the NAIVE (flawed) design: verifying only
    that a self-supplied hash chain is internally consistent, with no
    independent check against the real transcript. Used deliberately in
    Test 4 to demonstrate why this check alone is worthless.
    """
    prev_hash = ""
    for entry in fabricated_log_entries:
        payload = json.dumps(entry, sort_keys=True)
        chain_hash = sha256(prev_hash + sha256(payload))
        entry["_chain_hash"] = chain_hash
        prev_hash = chain_hash
    # Internally self-consistent by construction -- an attacker who builds
    # this entirely offline before ever showing it to anyone will ALWAYS
    # pass this check. That is the point being demonstrated.
    return VerdictResult(
        "ACCEPT (naive check only)",
        "hash chain is internally self-consistent -- but this was never "
        "checked against anything the fabricator does not control.",
    )
