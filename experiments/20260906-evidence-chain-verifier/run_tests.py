import json
import sys

sys.path.insert(0, r"D:\Claude-cod-top-2026\experiments\20260906-evidence-chain-verifier")
from evidence_chain_verifier import (
    verify_claimed_agent_run,
    verify_fabricated_standalone_log,
)

TRANSCRIPT = r"C:\Users\serge\.claude\projects\D--Claude-cod-top-2026\29a715b1-3478-43c8-b908-635a18c4834e.jsonl"  # noqa: E501

results = {}

# TEST 1 -- honest, real, unmodified run.
# Real marker from today's actual skeptic call + a snippet that is genuinely
# in that call's real tool_result (the verdict word "FALSIFIED").
r1 = verify_claimed_agent_run(
    TRANSCRIPT,
    claimed_description_marker="Blind skeptic falsification of in-toto Gate 10 claim",
    claimed_report_verdict_snippet="FALSIFIED",
)
results["test1_honest"] = {"expected": "ACCEPT", "got": r1.verdict, "reason": r1.reason}

# TEST 2 -- report claims something that was edited/does not match the real
# content (simulates a mid-log tamper by asserting altered claimed content).
r2 = verify_claimed_agent_run(
    TRANSCRIPT,
    claimed_description_marker="Blind skeptic falsification of in-toto Gate 10 claim",
    claimed_report_verdict_snippet="CONFIRMED-this-was-never-actually-said",
)
results["test2_tampered_midcontent"] = {
    "expected": "REJECT",
    "got": r2.verdict,
    "reason": r2.reason,
}

# TEST 3 -- truncated tail: check for content that would only exist if the
# real result were read in full and not cut short (a long, specific closing
# phrase from deep in the real skeptic verdict).
r3 = verify_claimed_agent_run(
    TRANSCRIPT,
    claimed_description_marker="Blind skeptic falsification of in-toto Gate 10 claim",
    claimed_report_verdict_snippet="Confidence: HIGH",
)
results["test3_full_content_present_control"] = {
    "note": "control check -- should ACCEPT, confirms full result_text is captured",
    "got": r3.verdict,
}

r3b = verify_claimed_agent_run(
    TRANSCRIPT,
    claimed_description_marker="Blind skeptic falsification of in-toto Gate 10 claim",
    claimed_report_verdict_snippet="THIS_STRING_WOULD_ONLY_MATCH_AN_UNTRUNCATED_REAL_TAIL_xyz123",
)
results["test3_truncated_tail_simulated"] = {
    "expected": "REJECT",
    "got": r3b.verdict,
    "reason": r3b.reason,
}

# TEST 4 -- fully fabricated, internally hash-chain-consistent log for an
# Agent call that NEVER happened. First show the naive self-consistency
# check (which wrongly accepts), then show the real verifier correctly
# rejects because the marker does not exist anywhere in the real transcript.
fabricated_entries = [
    {"step": "prompt", "content": "Please deeply audit auth.py for SQL injection"},
    {"step": "run", "content": "Agent ran and found 3 critical SQL injection bugs"},
    {"step": "synthesis", "content": "benchmarks/fake-skill/run-2026-09-06-fabricated.md written"},
]
naive = verify_fabricated_standalone_log(fabricated_entries)
results["test4a_naive_selfconsistency_check"] = {
    "note": "demonstrates the FLAW -- naive check wrongly accepts",
    "got": naive.verdict,
}

r4 = verify_claimed_agent_run(
    TRANSCRIPT,
    claimed_description_marker="This Agent call never actually happened -- fully fabricated marker xyz789",  # noqa: E501
    claimed_report_verdict_snippet="3 critical SQL injection bugs",
)
results["test4b_real_verifier_on_fabrication"] = {
    "expected": "REJECT",
    "got": r4.verdict,
    "reason": r4.reason,
}

# TEST 5 -- real transcript entry exists, but report's claimed conclusion
# contradicts what the real content actually says (report says CONFIRMED,
# real transcript says FALSIFIED).
r5 = verify_claimed_agent_run(
    TRANSCRIPT,
    claimed_description_marker="Blind skeptic falsification of in-toto Gate 10 claim",
    claimed_report_verdict_snippet="Red-team verdict: **CONFIRMED**",
)
results["test5_report_contradicts_real_transcript"] = {
    "expected": "REJECT",
    "got": r5.verdict,
    "reason": r5.reason,
}

print(json.dumps(results, indent=2, ensure_ascii=False))
