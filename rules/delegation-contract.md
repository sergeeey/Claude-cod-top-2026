# Delegation Contract — Structuring Non-Trivial Agent() Calls

## Purpose

The Agent tool's own guidance already says to brief a subagent "like a smart colleague
who just walked into the room." That is correct for most delegations — free prose,
explaining context and intent, is how a person would actually be briefed. This rule adds
ONE thing on top, for the specific case where a delegation is non-trivial: a short,
explicit checklist of fields the prose should actually cover, so a rich brief doesn't
silently omit the one thing (scope boundary, acceptance test, stop condition) that turns
a vague request into 40 minutes of the wrong work.

**Source:** identified as a real gap during a 2026-09-02 comparison against an external
"Claude Code multi-agent orchestration" research document — this repo's Context Asymmetry
Rule (`falsification-ladder.md`), Oracle hierarchy, and evidence policy were already ahead
of that document's equivalents; formal delegation structure was the one concrete, adoptable
idea it had that this repo did not.

## When to use

A delegation is non-trivial when at least one of these is true:

- The Agent will write or edit files (not just read/search).
- The task has a scope boundary that matters (touch these paths, not those).
- There's a specific way to tell success from plausible-sounding failure.
- The Agent runs in the background or its result will be trusted without re-verification.

For a quick read-only lookup ("find where X is defined"), the checklist is overhead —
free prose is correct and this rule does not apply.

## The checklist (fold into the prose brief, don't force YAML)

Per the Structure-Bias Guard (`falsification-ladder.md`): this is an **input/scope
contract**, not the agent's reasoning — so state it as clear prose sentences inside the
`prompt`, not as a rigid schema the agent must parse. The fields:

| Field | Question it answers | Omit only if... |
|---|---|---|
| **Objective** | What observable outcome is needed? | never — always state this |
| **Scope / owned paths** | What files/dirs may it touch? What's explicitly out of bounds? | task is pure read-only |
| **Context refs** | Which files/facts are authoritative, so it doesn't have to rediscover them? | task is small enough to self-explore cheaply |
| **Acceptance criteria** | How would a DIFFERENT reader tell success from a plausible-sounding failure? | task has no side effects to verify |
| **Stop / escalation condition** | When should it stop and report back instead of continuing to try? | task is bounded to one clear action |

## Worked example

**Thin (avoid for non-trivial work):**
> "Look at the backend and fix the problems."

**Structured (same idea, as prose — not a YAML block):**
> "Find why the two auth integration tests are failing. If the root cause is in
> `src/auth/**`, fix it there — do not touch database migrations or the public API shape.
> Read `artifacts/failing-tests.txt` first; it already has the stack traces. Before
> reporting done: run the existing auth tests AND add one regression test that would have
> caught this failure, and paste the actual command output, not a summary. If the failure
> persists after two materially different fix attempts, stop and report what you tried
> instead of a third attempt."

## Relationship to existing rules — this does not replace any of them

| Existing rule | What it already covers | What this rule adds |
|---|---|---|
| `context-loading.md` | WHICH shared-memory files an agent should read before acting | WHAT the calling prompt itself should state explicitly |
| `falsification-ladder.md` § Builder Blindness Rule | The builder must NOT see the falsifier's specific test cases | The builder SHOULD see explicit scope + acceptance criteria — these are different concerns, not in tension. (Builder Blindness's own "success criteria" and this checklist's "Acceptance criteria" name the same thing — one rule says give it, the other says don't also give away the falsifier's specific tests.) |
| `audit-verification-gate.md` | How to verify an agent's claims AFTER it reports | How to state the acceptance bar BEFORE it starts, so "done" has a checkable meaning |
| `autonomy-budget.md` | Risk-tier ceiling on what a loop/agent may DO | Scope/stop fields inside one delegation, orthogonal to the tier |

## Anti-pattern

Do not add a rigid pre-flight form that must be filled for every Agent() call — most
calls are read-only reconnaissance or small enough that free prose already covers all
five fields naturally. Forcing the checklist onto trivial delegations is the exact
over-formalization the Structure-Bias Guard warns against, just relocated to the input
side instead of the output side.

**Last updated:** 2026-09-02
**Status:** ACTIVE
