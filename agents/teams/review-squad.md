---
name: review-squad
description: Parallel code review — quality + security (both Claude), then a mandatory cross-model gate via Codex (different model) to catch bugs Claude-on-Claude review structurally cannot.
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
MUST run one cross-model review:
`Agent(codex:codex-rescue, prompt="Independent review of this diff — find bugs
Claude missed. <diff>")` (or `/codex-skeptic`). This is a real different model
(GPT/Codex), so it has no investment in Claude's code.
If Codex is unavailable (not installed/authed), note it explicitly and proceed
with the 2 Claude reviewers — never silently skip the gate.

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

## Coordination Protocol
1. reviewer + sec-auditor receive the same diff, run in parallel (no blocking)
2. Lead then runs the cross-model gate: `Agent(codex:codex-rescue, ...)` on the same diff
3. Lead merges all findings into single verdict:
   - If ANY (reviewer / sec-auditor / Codex) finds BLOCKED → verdict BLOCKED
   - If ANY finds NEEDS FIXES → verdict NEEDS FIXES
   - READY only if all agree (or Codex unavailable + both Claude agree, noted)
4. Codex findings carry extra weight: a cross-model HIGH that both Claude
   reviewers missed is exactly the blind-spot class this gate exists for —
   do not dismiss as "Claude already looked." Verify with a tool, then fix.

## Iteration Cap (Evaluator-Optimizer Guard)
- Max **3 review→fix→review cycles** per task
- After cycle 3 without LGTM: escalate to user with summary of unresolved findings
- Never run cycle 4 silently — limit burn is worse than a partial fix

## Token Budget
~2500-3500 tokens total (3 agents); ~7500-10500 for a full 3-cycle loop.
the Codex gate adds ~1000 tokens but runs on a separate model/quota (ChatGPT
login) — the Claude-side budget rises only modestly. Cross-model bug-catch
(see "Why" above) is worth the marginal cost on any PR with new logic.
