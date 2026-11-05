# Product Constitution — v1 (draft, 2026-07-16)

> The stable answer to "what is this, for whom, and what will it never do?" Every new
> component must point at a stage of the Core Loop it improves, or it does not belong.
> The internal sections are in force. The **public-framing** (§12) was **owner-approved
> and applied on 2026-07-16** — README, `docs/positioning.md`, and the plugin/marketplace
> descriptions now carry the "Evidence-aware Goal Operating Layer" identity.

## 1. North Star

Give Claude Code a human goal; the system turns it into a **verified, useful outcome**
with an explainable route, bounded authority, and evidence that the real-world or
repository state meets the agreed acceptance criteria. It reuses existing capabilities
before adding new ones and preserves a recoverable mission state when work is incomplete.

**The unit of success is a verified human goal, not a completed model turn, agent
handoff, tool call, commit, or passing self-authored test.** More capability is valuable
only when it improves outcomes against plain Claude Code without unacceptable overhead.

Boyko names the goal-navigation methodology, not a mandated central subagent.
The entrypoint and executor architecture remain experimental choices to be decided by
comparative evidence, not by this Constitution.

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
Human Intent → Goal Contract → Observe → Capability Selection → Plan
     → Authorize → Execute → Observe Effect → Verify → Decide → Remember
                                                   |
                         NOT DONE: replan or persist recovery checkpoint
```

| Stage | What happens | Backed by (examples) |
|-------|--------------|----------------------|
| Goal Contract | intent → falsifiable outcome, acceptance criteria, constraints, authority, non-goals | dispatcher, routing-policy, estimand-ops |
| Observe | establish available evidence, current state, missing data, and tool reachability | explorer, registry, contextual inspection |
| Capability Selection | prefer existing skills/agents/tools by declared output and observed availability | registry `capability:` fields, dispatcher |
| Plan | choose the simplest adequate route; surface up to three genuinely decision-changing adjacent opportunities without silently replacing the user's goal | routing-policy, boyko-agent |
| Authorize | check scope, permission, risk, and reversible execution before action | autonomy-budget, permission and scope guards |
| Execute | perform permitted work through the appropriate executor | builder/tester agents, hooks |
| Observe Effect | collect actual effects, not merely a tool's success message | runtime observations, diff, logs, tests |
| Verify | independently check outcome against Mission DoD, including remaining unknowns | integrity, skeptical review, verification gates |
| Decide | record DONE / CONTINUE / REPLAN / BLOCKED / STOPPED with the supporting evidence | mission result / orchestrator |
| Remember | persist validated learning and a checkpoint for incomplete missions | null_results, pearl_registry, activeContext |

`turn_completed != goal_completed`. A model final response, successful tool call,
agent handoff, or locally green test never by itself closes a mission.

**Current capability boundary:** preservation of an inspectable recovery checkpoint
is required for incomplete work. Autonomous continuation across model turns, sessions,
or crashes is **not a shipped capability claim**; it may be enabled only after a
bounded end-to-end test demonstrates that the available runtime can resume, honor
permissions and budgets, avoid spin loops, and preserve the original goal. Until then,
report the next action and recovery instructions without promising background execution.

A high-value overlooked route may be *suggested* when it changes expected user
outcome, cost, risk, or the decisive test. The user retains authority over goal changes.

## 5. Autonomy model

`.claude/rules/autonomy-budget.md` governs. Green (read-only) auto-runs; Yellow (edits)
runs with tests+evidence; Red (production/security/irreversible) is proposal-only; Black
(money/legal/mass-delete) is human-only. A component's `risk_tier` is declared, not
assumed.

## 6. Evidence model

`rules/integrity.md` governs. Every factual/validation claim carries a marker; validation
claims need `[VERIFIED-REAL]`; synthetic evidence must not pass as production truth — the
validation-theater hook flags it with a warning (PostToolUse cannot block). External ideas enter through `docs/research-sources.yaml` and cannot become
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
- Build a new general-purpose agent framework, runtime, scheduler, or memory database
  without measured evidence that the existing Claude Code substrate cannot meet the goal.
- Claim untested cross-turn autonomy, continuous operation, or verified completion
  based on a prompt or protocol alone.
- Optimize agent activity, tool counts, or elaborate plans instead of user outcomes.
- Replace a memory system, a skill marketplace, or a multi-agent framework by default —
  this layer composes and verifies existing capabilities first.
- Be a team product, a SaaS, or a marketplace listing (current Scope Fence NOT-NOW).

## 10. What counts as a successful outcome

A mission succeeds only when the **user's predeclared Goal Contract / Mission DoD**
is met and independently supported by inspectable evidence of the observed effect.
An explainable plan, executed actions, honest residual unknowns, and a reusable
procedure are supporting outputs, not substitutes for the outcome. "It passed
the tests I wrote this session" is insufficient.

**Primary baseline: plain Claude Code**, without this project's extra hooks, rules,
skills, or agents, under otherwise matched conditions. Before claiming this layer
adds value, pre-register the task set, task count, success criteria, outcome
verification, cost/overhead metrics, and decision threshold; execute the same tasks
in both arms with comparable models, permissions, environments, and budgets.
Control task order or other major confounders where feasible. Record failures,
inconclusive results, and uncertainty rather than asserting causal gain from
anecdotes or proxy counts.

Report both value and **cost of the layer**: goal completion, intervention burden,
token/context overhead, latency (including hook delay), erroneous blocks/false
positives, tool or agent calls, and recovery effort. The layer must not
**materially regress plain Claude Code** on predeclared guardrail metrics; where
trade-offs are unavoidable, identify and obtain explicit acceptance of them.
Thresholds are set per experiment **before** the run, not invented here.

A repository-wide green CI, install success, test coverage, or larger catalog
is an engineering prerequisite or inventory fact, never standalone product success.

## 11. Contribution, measurement, and retirement gate

Before adding or changing any hook / skill / agent / rule, answer:

1. Which **Core Loop stage or demonstrated user outcome** does it improve?
2. What confirmed failure case or need justifies it?
3. Why cannot plain Claude Code or an existing project component already cover it?
4. What are its inputs, outputs, authority boundary, context/token cost,
   latency, failure modes, risk tier, and rollback path?
5. What predeclared test compares its outcome and overhead against the baseline?
6. What evidence would cause us to reject, revert, archive, or delete it?

**Removal is part of governance, not an exception.** A component with no measured
use **or** no demonstrated benefit over a rolling 90-day review window must be
reviewed for **KEEP / ARCHIVE / DELETE**, with the decision and evidence recorded.
The 90-day trigger is a **review trigger, not automatic deletion**: retain a
rare but safety-critical component when evidence justifies its expected value;
distinguish no observations from proof of uselessness; and check dependencies,
risk, and rollback before retirement.

For every material overhead claim, measure loaded rules/context, hook latency,
noise and false-positive rate on an explicit observation window. If overhead
or regressions exceed the predeclared guardrail, simplify, scope, disable, or
remove the responsible component before expanding the catalog.

A proposed change without a stage, a measured need, and a falsifiable comparison
does not earn permanent inclusion. A repeated assertion that "more skills = more
capability" is not evidence.

## 12. Public framing (ACCEPTED + APPLIED 2026-07-16)

> Owner-approved. Applied to README hero, `docs/positioning.md` §1/§3/§6, and the
> plugin/marketplace descriptions. The synchronized release was cut the same day
> (v3.10.0, 2026-07-16).

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
(count strings preserved for the CI gate). **Release:** cut as v3.10.0 on 2026-07-16 (version bump + tag +
GitHub release).
