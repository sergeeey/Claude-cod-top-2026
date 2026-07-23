#!/usr/bin/env python3
"""SubagentStop hook -- flags boyko-agent (agents/navigator.md) output that
is missing its own required Output Format sections.

WHY (2026-07-18, competitive analysis of harmonist/vexjoy-agent dogfooding):
boyko-agent's CTA Card / Task Contract / Output Format discipline is defined
entirely in its own prompt -- nothing mechanically checked that it was
actually followed. This repo's own architectural principle (decisions.md,
2026-03-30): "Hooks enforce policy, not instructions." A live dogfood run
before this fix hit exactly this gap: the agent's turn budget ran out
mid-investigation and it stopped with no CTA Card and no synthesis --
caught only because the orchestrator happened to notice and manually asked
it to continue. This hook makes that noticing automatic, mirroring the
existing iteration_guard.py pattern (message-content pattern match, no
dependency on subagent_type being present in the SubagentStop payload).

Detection, not enforcement: SubagentStop cannot block completion or force a
sub-agent to keep working (the same limitation PostToolUse has for denying
-- see mcp_response_guard.py's own docstring for the equivalent point). This
hook can only inject additionalContext for the orchestrator to see.

Identity check, not just message content (regression found via a live-data
test against this repo's own dogfood transcripts, 2026-07-18): an earlier
version of this hook recognized a boyko-agent stop only by the presence of
the literal "## Boyko Agent Brief" header. Tested against the actual
pre-fix failure's real last_assistant_message text -- which had NO header
at all, because the agent was cut off mid-tool-call before writing one --
and the header-only check would have silently ignored exactly the failure
this hook exists to catch. `agent_type` is present in the SubagentStop
payload (confirmed via agent_lifecycle.py's own `data.get("agent_type")`
usage) and is a reliable identity signal independent of how much output the
agent managed to produce before stopping. Checked first; the header is kept
only as a fallback for payload shapes where agent_type is absent.
"""

import os
import sys

from utils import emit_hook_result, parse_stdin

BRIEF_HEADER = "## Boyko Agent Brief"

# WHY both spellings: "navigator" is the legacy invocation name from before
# the boyko-agent rename (agents/navigator.md's own "Legacy implementation
# path" note) -- some cached prompts or older sessions could still pass it.
BOYKO_AGENT_TYPES = frozenset({"boyko-agent", "navigator"})

# WHY these 9, not "### Adjacent opportunities" too: navigator.md's own
# Output Format template explicitly allows omitting Adjacent opportunities
# ("omit when none are material") -- the other 9 markers have no such
# carve-out; "### Learning Proposal" must still appear as a header even
# when its content is the literal word "none".
REQUIRED_MARKERS: tuple[str, ...] = (
    "**Session goal:**",
    "**Pipeline:**",
    "**Confidence:**",
    "### Route trace",
    "### CTA Card",
    "### Discriminating test",
    "### Priorities",
    "### Evidence status",
    "### Learning Proposal",
)


def missing_sections(message: str) -> list[str]:
    """Return the required markers absent from a boyko-agent brief."""
    return [marker for marker in REQUIRED_MARKERS if marker not in message]


# WHY these three (2026-07-23, gap found by a real dogfood run of
# agents/navigator.md's Reconciliation Protocol / CTA-Card acceptance-gate
# additions): missing_sections() above only checks that the "### CTA Card"
# HEADER is present, not that the specific fields navigator.md's own
# template requires inside that section actually appear. A real
# boyko-agent run (2026-07-22, recorded in tests/boyko_eval/results/)
# produced a full brief with every required header present but silently
# omitted all three of these fields -- structurally compliant per
# missing_sections(), protocol-incomplete per the actual CTA Card template.
# WHY tests/boyko_eval/grader.py imports THIS constant rather than defining
# its own (DRY, single source of truth): this hook is the canonical,
# production-facing definition; grader.py is offline test tooling that
# reuses it, matching the existing direction of that import
# (grader.py already imports missing_sections from this file).
CTA_ACCEPTANCE_FIELDS: tuple[str, ...] = ("Done when:", "Scope limits:", "Verifier:")


def missing_cta_fields(message: str) -> list[str]:
    """Return CTA_ACCEPTANCE_FIELDS entries absent from a boyko-agent brief.

    WHY only checked when "### CTA Card" itself is present: if the CTA Card
    section is missing entirely, missing_sections() above already reports
    that -- reporting missing CTA_ACCEPTANCE_FIELDS on top of a missing
    section header would be a redundant, confusing second warning for the
    same underlying gap.
    """
    if "### CTA Card" not in message:
        return []
    return [field for field in CTA_ACCEPTANCE_FIELDS if field not in message]


def main() -> None:
    # WHY this guard even though this hook never calls Claude or reads
    # memory (hooks/CLAUDE.md's stated trigger for it): matches the sibling
    # Agent-lifecycle hook (iteration_guard.py) this file's pattern mirrors,
    # for consistency within the same hook family.
    if os.environ.get("CLAUDE_INVOKED_BY"):
        sys.exit(0)

    data = parse_stdin()
    if not data:
        return

    agent_type = str(data.get("agent_type", "")).strip().lower()
    message = data.get("last_assistant_message", "")

    is_boyko = agent_type in BOYKO_AGENT_TYPES or BRIEF_HEADER in message
    if not is_boyko:
        return  # neither identity nor content signal -- not a boyko-agent stop

    missing = missing_sections(message)
    missing_cta = missing_cta_fields(message)
    if not missing and not missing_cta:
        return

    if BRIEF_HEADER not in message:
        warning = (
            "[boyko-protocol-guard] boyko-agent stopped with NO recognizable "
            "output at all (no '## Boyko Agent Brief' header, no Output "
            "Format sections) -- this looks like it was cut off mid-work "
            "(e.g. turn budget exhausted during a tool call) rather than "
            "completing its own protocol. Treat this result as empty, not "
            "as a finished brief. Consider resuming it (SendMessage) rather "
            "than acting on it as-is."
        )
    elif missing:
        warning = (
            f"[boyko-protocol-guard] boyko-agent stopped with '{BRIEF_HEADER}' "
            f"present but missing required Output Format section(s): "
            f"{', '.join(missing)}. This usually means it ran out of its turn "
            "budget mid-investigation rather than completing its own protocol "
            "-- treat this result as a partial, unsynthesized brief, not a "
            "finished one. Consider resuming it (SendMessage) rather than "
            "acting on it as-is."
        )
    else:
        # WHY a distinct third message (2026-07-23): all 9 required sections
        # are present -- this is NOT the "cut off mid-work" failure mode the
        # two messages above describe. It is a structurally-complete brief
        # that silently skipped part of its own CTA Card template.
        warning = (
            f"[boyko-protocol-guard] boyko-agent stopped with '{BRIEF_HEADER}' "
            "present and all required Output Format sections present, but the "
            f"CTA Card is missing acceptance-gate field(s): {', '.join(missing_cta)}. "
            "This is structurally compliant but protocol-incomplete -- these "
            "fields exist specifically so the orchestrator knows what 'done' "
            "means, what is out of scope, and who verifies the result. Treat "
            "this brief as missing that information, not as a finished one."
        )
    emit_hook_result("SubagentStop", warning)


if __name__ == "__main__":
    main()
