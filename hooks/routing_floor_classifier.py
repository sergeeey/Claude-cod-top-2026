#!/usr/bin/env python3
"""UserPromptSubmit hook: deterministically classify a task's SAFETY-FLOOR tier and
inject the mandatory routing floor for it — so the floor is enforced by code, not by the
LLM remembering to read routing-policy.

WHY (architecture: routing was soft governance): dispatcher/routing-policy DOCUMENT a
Safety Floor ("security/PII/payments review is mandatory regardless of project type;
destructive/migration ops need tests; research needs the EstimandOps L0 gate"), but
whether that floor is applied was a discretionary LLM decision. This hook is the
`project_classifier` pattern extended to the TASK tier: it runs as code, detects the tier
deterministically from the prompt, and injects the floor EVERY time — the classification
can no longer be forgotten.

HONEST SCOPE: this is *deterministic enforcement of the classification*, not a hard block.
Semantic routing (which skill fits) stays soft — that is inherent. The tool-level hard
blocks (permission_policy deny-list, security_verify on Edit|Write) remain the actual
gate; this hook makes the routing FLOOR that feeds them deterministic instead of
discretionary, closing the "routing is prompt-only" gap without any risk of breaking a
legitimate flow (it only injects context, never blocks).

Fires on: UserPromptSubmit. Non-blocking, fail-open, recursion-guarded.

The SECURITY/DESTRUCTIVE/RESEARCH signal regexes themselves (and their WHY comments)
live in lib/classification_signals.py, shared with hooks/resource_router.py's T3 tier —
see that module's own docstring for why the duplication was extracted.
"""

import os
import sys
from collections.abc import Callable
from typing import TypedDict

# Recursion guard — this hook must never re-enter when Claude spawns subagents.
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

import re

from lib.classification_signals import (
    is_likely_quoted_occurrence,
    match_destructive_signal,
    match_research_signal,
    match_security_signal,
)
from lib.runtime import emit_hook_result, hook_main, parse_stdin, strip_non_user_content
from lib.state import log_route_decision

# WHY \r?\n, not a bare "\n\n" (skeptic-found, 2026-09-12, confirmed by direct
# execution before fixing): Design 3's first cut used `prompt.rfind("\n\n")`
# and fell back to the WHOLE prompt when that returned -1. A CRLF-pasted
# document (Windows editors, many log/export tools) separates paragraphs with
# "\r\n\r\n", which contains no bare "\n\n" substring -- rfind returned -1,
# tail_region became the entire prompt, and `matcher(tail_region)` collapsed
# to the exact same call as `matcher(prompt)` at the top of this loop (already
# known truthy to have reached this line), making `not matcher(tail_region)`
# always False. Suppression was silently disabled for ANY prompt lacking a
# bare "\n\n" -- reopening the original incident class for CRLF pastes.
# Reproduced: a CRLF-formatted postmortem doc with a benign trailing question
# fired SECURITY instead of being suppressed. Fixed two ways at once: match
# `\r?\n` so CRLF paragraph breaks are found, and fall back to an EMPTY tail
# region (not the whole prompt) when no paragraph break exists at all -- an
# empty region never independently matches anything, so "can't find a last
# paragraph" now correctly biases toward suppression, matching this file's
# own asymmetric-cost convention (a missed injection is cheap, a false one is
# the expensive, actually-observed failure) instead of silently disabling the
# check.
_PARAGRAPH_BREAK_RE = re.compile(r"(?:\r?\n){2,}")

# Each tier: (name, signal matcher, the mandatory floor text). Signals are bilingual.
_TIERS: list[tuple[str, Callable[[str], re.Match[str] | None], str]] = [
    (
        "SECURITY",
        match_security_signal,
        "SECURITY-TIER task detected. Safety Floor is MANDATORY regardless of project "
        "type (even MVP): run the reviewer + security-audit path, never builder-solo; "
        "no secrets in code/logs; confirm before any irreversible action. This tier is "
        "set deterministically by hooks/routing_floor_classifier.py — not a suggestion.",
    ),
    (
        "DESTRUCTIVE",
        match_destructive_signal,
        "DESTRUCTIVE/MIGRATION-TIER task detected. Safety Floor: a test is MANDATORY "
        "(even for MVP), take a checkpoint first, and confirm the irreversible step with "
        "the user. Deterministically classified — do not downgrade.",
    ),
    (
        "RESEARCH",
        match_research_signal,
        "RESEARCH/HYPOTHESIS-TIER task detected. MANDATORY first step: EstimandOps L0 gate "
        "(classify Descriptive / Predictive / Causal) BEFORE choosing a Falsification "
        "Ladder tier — never offer L0 as one menu option among many. Deterministic tier.",
    ),
]


class ClassificationResult(TypedDict):
    injected_tiers: list[str]
    all_matches: dict[str, str]
    suppressed_tiers: list[str]
    messages: list[str]


def classify(prompt: str) -> ClassificationResult:
    """Run the SAFETY-FLOOR tier classification for one prompt.

    Pulled out of main() so scripts/routing_replay.py can exercise the exact
    same candidate logic the live hook runs, instead of a hand-copied second
    version -- this file's own docstring and lib/classification_signals.py's
    docstring both document two real drift incidents (PR #383/#386, #392)
    caused by exactly that kind of duplication.

    Returns a dict with:
      - "injected_tiers": tier names whose floor text would actually fire
      - "all_matches": tier name -> matched substring, for every tier that
        matched at all (before suppression)
      - "suppressed_tiers": tier names that matched but were suppressed as a
        likely quoted/pasted occurrence
      - "messages": the floor text lines for injected tiers (what main()
        would pass to emit_hook_result)
    """
    all_matches: dict[str, str] = {}
    injected_tiers: list[str] = []
    suppressed_tiers: list[str] = []
    messages: list[str] = []
    for name, matcher, floor in _TIERS:
        m = matcher(prompt)
        if not m:
            continue
        all_matches[name] = m.group(0)
        # WHY re-check the matcher against ONLY THE PROMPT'S OWN LAST
        # PARAGRAPH (fixed 2026-09-12, third iteration -- see the two
        # rejected designs below, both caught by real evidence before
        # shipping further): every incident actually observed so far --
        # the original 4 in one session, plus a fresh real-task evaluation
        # the same night -- has the SAME shape: one coherent pasted document,
        # ending in either a benign question or a live directive, with NO
        # further document structure after that trailing text. The live
        # text, when it exists, IS the prompt's last paragraph.
        #
        # Design 1 (shipped first, in the same PR): fixed last-400-char
        # window. Missed a live directive sitting in the MIDDLE of a long
        # prompt with more pasted content trailing it -- `matcher(prompt)`
        # only ever returns the FIRST (leftmost, buried) match, so nothing
        # ever re-checked the region between it and the last 400 characters.
        # Found by skeptic review, fixed same PR.
        #
        # Design 2 (the skeptic-review fix): re-check from the next paragraph
        # break after the FIRST match to the end of the prompt. This fixed
        # design 1's bug but broke on a REAL 3-task evaluation the same
        # night: a realistic postmortem-shaped document that restates its
        # own topic in a LATER, separate section (a normal thing for a real
        # document to do -- "Root cause: ...credential..." followed later by
        # "Open questions: ...credential rotation...") was no longer
        # suppressed, because that later section's restatement looked
        # exactly like design 2's definition of "independent live signal."
        # This is a real document doing what real documents do, not a live
        # directive -- see scripts/routing_replay_cases.jsonl's
        # "reg-topic-restated-in-later-section" case for the reproduction.
        #
        # Design 3 (this one): only the prompt's OWN final paragraph counts
        # as a possible live signal, regardless of where the buried match
        # sits. This matches every incident actually observed to date.
        # KNOWN, ACCEPTED GAP (not fixed by this design, and not yet
        # observed in real usage): a live directive followed by STILL MORE
        # pasted content after it (design 1's original reproducer) is once
        # again suppressed, because by construction nothing tier-relevant is
        # left in the prompt's true last paragraph. Full structured record
        # (behavior/reason/risk/accepted_because/expires_when/
        # replacement_strategy) lives on the
        # "reg-live-ask-mid-prompt-followed-by-more-content" case's
        # `known_regression` field in scripts/routing_replay_cases.jsonl --
        # not restated here so there is exactly one place to keep it current.
        # Plain-assertion regression pin (deliberately not an xfail --
        # weakened_test_guard.py blocks disabling a test as a fix; this
        # asserts the CURRENT intentional behavior instead) in
        # tests/test_routing_floor_classifier.py's
        # test_live_ask_followed_by_more_pasted_content_is_a_documented_limitation.
        paragraph_breaks = list(_PARAGRAPH_BREAK_RE.finditer(prompt))
        tail_region = prompt[paragraph_breaks[-1].end() :] if paragraph_breaks else ""
        if is_likely_quoted_occurrence(prompt, m) and not matcher(tail_region):
            suppressed_tiers.append(name)
            continue
        injected_tiers.append(name)
        messages.append(f"[routing-floor] {name} (matched: {m.group(0)!r}) — {floor}")

    return {
        "injected_tiers": injected_tiers,
        "all_matches": all_matches,
        "suppressed_tiers": suppressed_tiers,
        "messages": messages,
    }


def main() -> None:
    try:
        data = parse_stdin()
    except Exception:
        sys.exit(0)

    # WHY strip: agent completion notifications arrive through this same event; classifying
    # their text produced 2/3 of this hook's false firings in the Y-17 pilot (2026-09-06).
    prompt = strip_non_user_content(str(data.get("prompt", "") or ""))
    if not prompt:
        sys.exit(0)

    result = classify(prompt)
    injected_tiers = result["injected_tiers"]
    all_matches = result["all_matches"]
    suppressed_tiers = result["suppressed_tiers"]
    matched = result["messages"]

    log_route_decision(
        classifier="routing_floor_classifier",
        matched_tiers=injected_tiers,
        matches=all_matches,
        prompt_len=len(prompt),
        session_id=data.get("session_id"),
        suppressed_tiers=suppressed_tiers,
    )

    if matched:
        emit_hook_result("UserPromptSubmit", "\n".join(matched))
    sys.exit(0)


if __name__ == "__main__":
    hook_main(main)
