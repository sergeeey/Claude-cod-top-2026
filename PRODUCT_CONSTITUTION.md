# Product Constitution — v1 (draft, 2026-07-16)

> The stable answer to "what is this, for whom, and what will it never do?" Every new
> component must point at a stage of the Core Loop it improves, or it does not belong.
> This is a draft: the internal sections are in force now; the **public-framing** section
> (§12) is a PROPOSAL awaiting the owner's yes/no — it is not yet reflected in README.

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

## 12. Proposed public framing (PROPOSAL — owner decision required)

> Not yet applied to README/positioning.md. Recorded here for a yes/no.

**Current public identity:** "Trust layer... none of this makes an agent more capable."
**Proposed:** "**Evidence-aware Goal Operating Layer for Claude Code** — turns a goal
into an explainable, capability-composed, budget-bounded, verified, remembered result."

Rationale: the code already ships goal orchestration (`/evolve-solution`), a scientific
method stack, dispatcher/routing, and memory — the "only a trust layer, makes nothing
more capable" framing contradicts the actual repository and undersells it. Trust/evidence
becomes the *control system* that makes more autonomy safe, not the whole product.

**This change is deliberately NOT made autonomously** — a project's public identity is
the owner's call. If accepted, it flows to: README hero, `docs/positioning.md` §1,
plugin/marketplace descriptions, and a synchronized release. Until then, the repo keeps
its current public framing and this section stands as the open proposal.
