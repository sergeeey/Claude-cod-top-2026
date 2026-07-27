---
name: review-squad
description: Parallel code review — quality + security (both Claude), then a mandatory cross-model gate (Codex → Ollama fallback chain — a non-Claude model) to catch bugs Claude-on-Claude review structurally cannot.
lead: reviewer
teammates:
  - sec-auditor
strategy: parallel
---

## Purpose
Run code quality review + security audit in parallel (both Claude agents),
THEN a cross-model pass (different model) as a mandatory gate.
Lead (reviewer) checks spec compliance + code quality + adversarial challenges.
Teammate (sec-auditor) checks PII exposure, injection vulnerabilities, secrets.

## Cross-model gate (the third reviewer — different model, not a teammate)
reviewer + sec-auditor are BOTH Claude → they share Claude's blind spots, so
they can't be the independent check. After the parallel Claude pass, the lead
MUST run one cross-model review — following this **fallback chain**, in order,
until one tier succeeds. Stop at the first tier that returns a verdict:

1. **Codex (GPT)** — `Agent(codex:codex-rescue, prompt="Independent review of
   this diff — find bugs Claude missed. <diff>")` (or `/codex-skeptic`).
   Primary: a frontier non-Claude model.
2. **Local Ollama** — if Codex errors/unauthed, fall to a local non-Claude
   model: `mcp__ollama__ollama_review_code` (or `ollama_review_file`), e.g.
   `qwen2.5:14b` / `qwq:32b`. Still genuine cross-model — different weights,
   different blind spots, no Anthropic lineage, and no external auth to break.
3. **Noted 2-Claude degrade** — only if BOTH Codex and Ollama are unavailable,
   proceed with the 2 Claude reviewers AND state in the verdict:
   `cross-model gate DEGRADED — no non-Claude reviewer available`.

Never silently skip the gate. A single-provider gate is a single point of
failure: on 2026-06-07 Codex returned HTTP 400 ("not supported with ChatGPT
account") and the gate had nowhere to fall — that incident is why this is a
chain, not one call. The chain trips past a dead provider like a circuit
breaker (see hooks/mcp_circuit_breaker.py for the same pattern on MCP calls).

## Why a cross-model teammate (the lesson that created it)
reviewer + sec-auditor are both Claude → they share Claude's blind spots. A
2026-06-04 session shipped a HIGH bug (global string-replace that could corrupt
a URL/year) through multiple Claude self-reviews; Codex found it on the first
pass. Self-review structurally cannot catch what the model never thought to
question — a different model has no investment in the code. If Codex is
unavailable (not installed/authed), the squad degrades to 2 Claude reviewers —
note it explicitly, don't silently skip.

## When to Use
- Before merging any PR that touches auth, payment, or user data
- Before production deploys
- When routing-policy detects multi-file changes (3+ files)

## Release Gate (additional stage — production releases only, not every PR)

The parallel pass above (reviewer + sec-auditor) covers code quality and
real-time PII/injection protection, but neither runs the financial/compliance
checklist `security-guard` owns (known-issue lookup, National ID/hardcoded-
credential/open-endpoint checklist, explicit PASS/BLOCK verdict). Nothing
backed the "Before production deploys" line above until this gate existed
(coherence audit finding, 2026-07-17 — `security-guard` was a fully standalone
agent, invoked by no team, despite that whenToUse line existing since 2026-03-31).

Before an actual **production release** specifically — not every review-squad
invocation, most of which are routine PRs — also run:

`Agent(security-guard, prompt="Pre-release security audit: <diff/release scope>")`

A `BLOCK` verdict from security-guard carries the same weight as a BLOCKED
verdict from the cross-model gate above: do not release until it passes.

## Coordination Protocol
1. reviewer + sec-auditor receive the same diff, run in parallel (no blocking)
2. Lead then runs the cross-model gate via the fallback chain above
   (Codex → Ollama → noted 2-Claude degrade) on the same diff
3. Lead merges all findings into single verdict:
   - If ANY (reviewer / sec-auditor / cross-model) finds BLOCKED → verdict BLOCKED
   - If ANY finds NEEDS FIXES → verdict NEEDS FIXES
   - READY only if all agree (or gate DEGRADED + both Claude agree, noted)
4. Cross-model findings carry extra weight: a HIGH that both Claude reviewers
   missed is exactly the blind-spot class this gate exists for — do not dismiss
   as "Claude already looked." Verify with a tool, then fix.

## Iteration Cap (Evaluator-Optimizer Guard)
- Max **3 review→fix→review cycles** per task
- After cycle 3 without LGTM: escalate to user with summary of unresolved findings
- Never run cycle 4 silently — limit burn is worse than a partial fix

**Why 3, not "until it's clean" (MRR vs Recall trade-off — CONVCODEWORLD, Han
et al. 2025):** fewer cycles to converge (MRR-like) and eventually resolving
every finding no matter how many cycles it takes (Recall-like) are different
objectives that don't move together — a model can be fast-converging on most
tasks and still miss occasional harder findings, or vice versa. Capping at 3 is
a deliberate choice of bounded cost over exhaustive resolution, not an
admission that the loop "didn't get to finish." When cycle 3 ends without
LGTM, that's the correct signal to hand off to a human, not evidence the cap
should be raised.

## Token Budget
~2500-3500 tokens total (3 agents); ~7500-10500 for a full 3-cycle loop.
the cross-model gate adds ~1000 tokens but runs off the Claude budget: Codex on
a separate quota (ChatGPT login), or Ollama fully local (0 API cost). The
Claude-side budget rises only modestly. Cross-model bug-catch (see "Why" above)
is worth the marginal cost on any PR with new logic.
