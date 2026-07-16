# null_result: LLM-judge suppression for the prompt-injection response guard

**ID:** 20260716-llm-judge-response-guard
**Date:** 2026-07-16
**Verdict:** REJECT (by red-team, before any implementation)
**Source:** `docs/rfcs/RFC-002-response-guard-classifier.md` (design kept there with the full verdict)

## Claim that was rejected

"A two-stage guard — fast regex pre-filter, then a local LLM-judge that downgrades
warn→silent only on confident 'this text describes attacks, not directs the agent' — can
cut the response guard's false-positive rate without adding false-negatives, safely,
because PostToolUse only warns (never blocks) so a fooled judge's worst case is bounded."

## How it was falsified (context-blind sec-auditor red-team, no code written)

The premise is structurally unsound, not tunable:

1. **Capability-asymmetric judge (CRITICAL).** The judge is a small local model; the
   reading agent is Claude. Any payload the judge is too weak to recognize as directive
   but Claude is strong enough to follow → guaranteed downgrade then guaranteed injection.
   The capability gap IS the exploit (demonstrated: English frame + Russian imperative;
   base64 "illustrative sample" the judge rates descriptive and Claude decodes-and-follows).
2. **The judge is itself injectable, prompt+delimiter public (CRITICAL).** Open source →
   attacker knows the exact judge prompt and delimiter. A competent injection returns a
   clean, confident false; "any deviation → true" only catches malformed output.
3. **"Bounded suppressed warning" is FALSE (CRITICAL).** In PostToolUse the warning cannot
   block, so it is the ENTIRE control, not a layer above others. Suppressing it removes the
   only defense; the bound is the agent's full tool scope (exfil, exec, credential theft,
   MCP lateral movement). The design strictly ADDS a false-negative class in the worst
   category (system_override / jailbreak / role_injection).
4. **Routing inverts the risk gradient (HIGH).** Canonical effective injections land
   exactly and only in the descriptive-ambiguous categories eligible for downgrade;
   attackers keep payloads operational-token-free. The benign-noisy case (a blog printing
   `curl | bash`) hits an operational category and can never be quieted.
5. **Ollama endpoint = downgrade oracle + exfil channel + DoS (HIGH).** Repo-committed
   enable-flag + off-box URL turns "clone repo" into an attacker-controlled verdict oracle;
   descriptive-trigger flooding → synchronous-inference DoS.

## Do NOT

- Re-attempt any scheme where a model (especially one weaker than the reading agent)
  can REMOVE / suppress a warning in a warn-only PostToolUse guard. That is the wall.
- Treat "PostToolUse only warns" as license to suppress — the warning IS the control.
- Put a network/inference call in the security control's hot path with a repo-overridable
  endpoint.

## The salvageable direction (auditor-endorsed — a DIFFERENT approach, RFC-003)

Never remove a warning; reduce noise deterministically: downgrade SEVERITY (not to silent)
when a hit sits in a fenced/quoted/citation span, keep every warning visible, audit-log
every downgrade, and accept that over-warning on body prose is the SAFE failure mode. This
is model-free and cannot create a false-negative. It is a partial, safe FP reduction — the
correct trade for a warn-only control. Its own RFC + FL run, not this one.

## Meta-lesson

Doubt-driven-development worked as designed: an independent context-blind red-team killed
an unsound SECURITY design at the design phase, before a line of vulnerable code — cheap.
The two guard attempts together (regex overfit, LLM-judge unsound) establish that the
response-guard FP/FN problem is not safely solvable by pattern-completeness OR by semantic
suppression; the safe move is to make the necessary over-warning less intrusive, not to
remove it.
