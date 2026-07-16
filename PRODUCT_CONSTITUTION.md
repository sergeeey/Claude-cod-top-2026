# Product Constitution — v1 (draft, 2026-07-16)

> The stable answer to "what is this, for whom, and what will it never do?" Every new
> component must point at a stage of the Core Loop it improves, or it does not belong.
> The internal sections are in force. The **public-framing** (§12) was **owner-approved
> and applied on 2026-07-16** — README, `docs/positioning.md`, and the plugin/marketplace
> descriptions now carry the "Evidence-aware Goal Operating Layer" identity.

## 1. North Star

Give Claude Code a goal; it produces an **explainable plan**, composes the right
capabilities, executes within a **bounded autonomy budget**, **verifies** the result,
and **remembers** what worked — so that more capability can be handed to the agent
*without* handing it more unchecked trust.

## 2. Target user

A single practitioner (initially the author) who uses Claude Code for real work —
software engineering AND scientific hypothesis-testing — and who is willing to trade a
little speed for results they can *check*. Not a team-collaboration product yet; not a
turnkey consumer tool.

## 3. Core problem

Agentic coding tools are trusted on their own say-so: an agent writes a test, runs it on
data it generated, and reports success. The gap is not capability — it is **checkable
capability**. This project's whole reason to exist is closing that gap while still
letting the agent do more.

## 4. Core Loop (every component maps to a stage here)

```
Goal  →  Plan  →  Capability-Selection  →  Execute  →  Verify  →  Remember
                         ↑___________________ Replan __________________|
```

| Stage | What happens | Backed by (examples) |
|-------|--------------|----------------------|
| Goal | fuzzy intent → falsifiable goal + success criteria + non-goals | dispatcher, routing-policy, estimand-ops |
| Plan | goal → task DAG, risk-tiered | routing-policy, autonomy-budget |
| Capability-Selection | pick skills/agents by what they *provide* | registry `capability:` fields, dispatcher |
| Execute | do the work within budget | builder/tester agents, hooks |
| Verify | audit the result before trusting it | integrity, skeptic-triggers, validation-theater guard, FL |
| Remember | keep what worked, record what didn't | null_results, pearl_registry, research-sources, activeContext |

## 5. Autonomy model

`.claude/rules/autonomy-budget.md` governs. Green (read-only) auto-runs; Yellow (edits)
runs with tests+evidence; Red (production/security/irreversible) is proposal-only; Black
(money/legal/mass-delete) is human-only. A component's `risk_tier` is declared, not
assumed.

## 6. Evidence model

`rules/integrity.md` governs. Every factual/validation claim carries a marker; validation
claims need `[VERIFIED-REAL]`; synthetic evidence can never silently pass as production
truth. External ideas enter through `docs/research-sources.yaml` and cannot become
internal "proven" facts without a named in-repo experiment.

## 7. Stable packs (mature, safe to depend on)

core-orchestration (dispatcher, routing-policy, context) · trust-and-evidence (integrity,
validation-theater guard, skeptic-triggers, oracle/promotion gates) · software-engineering
(builder, tester, reviewer, CI/debug) · memory-and-learning (sessions, null_results,
pearls).

## 8. Experimental packs (real but not yet load-bearing)

scientific-discovery (sci-hypothesis, hypothesis-arbiter, boyko-*, consilience,
proof-ladder) · self-development (release-scout, research-sources) · claim-pipeline
(claim-decomposer + RFC-001). These are promising, not proven — treat their output as a
draft to verify, not an answer.

## 9. Non-goals (things this project will NOT do)

- Auto-execute Red/Black actions (deploy, publish, transfer funds, mass-delete).
- Present synthetic/calibration numbers as real-world validation.
- Grow the catalog for its own sake — count is not capability (see §11).
- Replace a memory system, a skill marketplace, or a multi-agent framework — it layers
  verification on top of whatever you use.
- Be a team product, a SaaS, or a marketplace listing (current Scope Fence NOT-NOW).

## 10. What counts as a successful outcome

Goal achieved AND the achievement is checkable: an explainable plan, an executed result,
evidence a third party could inspect, honest residual gaps, and a reusable procedure
captured. "It passed the tests I wrote this session" is not success — it is the failure
mode this project is built to catch.

## 11. Contribution gate (the one rule for new components)

Before adding any hook / skill / agent / rule, answer:

1. Which **Core Loop stage** does it improve? (No stage → it's noise. Don't add it.)
2. What confirmed failure case or need justifies it?
3. Why doesn't an existing component cover it?
4. Inputs / outputs / cost / risk_tier?
5. How is its output verified?
6. How would you remove it without breaking the system?

A component that cannot answer #1 does not get added — this is the antidote to the
"more blocks than system" drift that prompted this Constitution.

## 12. Public framing (ACCEPTED + APPLIED 2026-07-16)

> Owner-approved. Applied to README hero, `docs/positioning.md` §1/§3/§6, and the
> plugin/marketplace descriptions. A synchronized release tag is the one remaining
> follow-up (owner's call on timing/version).

**Public identity:** "**Evidence-aware Goal Operating Layer for Claude Code** — turns a
goal into an explainable, capability-composed, budget-bounded, verified, remembered
result."

Rationale: the code already ships goal orchestration (`/evolve-solution`), a scientific
method stack, dispatcher/routing, and memory — the prior "only a trust layer, makes
nothing more capable" framing contradicted the actual repository and undersold it.
Trust/evidence is repositioned as the *control system* that makes more autonomy safe, not
the whole product.

**What changed:** README hero now leads with the goal loop and keeps the Validation
Theater story as the Verify stage's justification; positioning.md §1 category, §3 closing
line, and §6 one-liner updated; plugin.json + both marketplace.json descriptions updated
(count strings preserved for the CI gate). **Still pending (owner):** cut the synchronized
release (version bump + tag + GitHub release) — a publish action, not done autonomously.
