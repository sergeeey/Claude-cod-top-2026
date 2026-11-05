# Product Constitution — v2 (owner-approved, 2026-11-05)

> The stable answer to "what is this, for whom, and what will it never do?"
> v2 rewrites §1 (North Star and Mission), §4 (Core Operating Loop), §9 (Non-goals),
> §10 (Definition of Done) and §11 (decision rule), and adds §13 (architectural
> principles) and §14 (Boyko as Goal Orchestrator). §2, §3, §5–§8 are unchanged.
> §12 (public framing) is unchanged; updating README and plugin descriptions to v2 is a
> separate owner decision.
>
> Why v2: an owner audit on 2026-11-05 found the project had drifted from its own
> decisions. The skill catalog grew from 49 (May 2026, "smaller but sharper") to 146
> extension skills; always-on rules reached about 132k characters; about 46% of the hook
> trigger log was test-fixture noise; and the navigator the owner had named as the primary
> goal on 2026-07-22 (Boyko Agent) had not been changed since 2026-07-28. v1 had a rule
> for adding components and no rule for removing them.

## 1. North Star and Mission

### 1.1 North Star

Build for Claude Code one adaptive, evidence-governed system for reaching goals: the
person states the result they want, and the system works out the path, uses the
capabilities that are actually available, organizes execution, verifies the result and
keeps the progress made.

The system reduces the need to hand-manage tools, agents and intermediate steps, without
taking away the person's control over the original goal, material decisions and the
limits of autonomy.

The success criterion is not a completed action or a finished agent reply. It is the
user's goal reached, confirmed by sufficient independent evidence.

### 1.2 Mission

Turn Claude Code from a set of separate agents, skills, rules and tools into one coherent
system that carries out user missions. To do that, the system must:

1. **Understand intent.** Turn the request into a clear goal, checkable success criteria,
   constraints and stop conditions. Ask only about uncertainties that could materially
   change the decision.
2. **Find capabilities and non-obvious paths.** Determine which existing tools, skills,
   agents and methods are actually available and sufficient. Surface options, risks and
   shorter paths the user did not ask about. Prefer reuse to building something new.
3. **Choose the path.** Build the smallest sufficient plan, weighing result, cost, risk,
   reversibility and quality of evidence.
4. **Organize execution.** Use suitable executors through the available orchestrator. The
   user should not have to pick and wire internal components by hand.
5. **Verify the result.** Separate finishing a step from reaching the final goal. Use
   independent checks, reproducible tests and real evidence.
6. **Keep the mission continuous.** Hold the goal, constraints, state, evidence and next
   step across separate conversation turns by leaving a checkable recovery point.
   Automatic continuation is used only after the mechanism for it has itself been
   verified, and only within the available runtime, budget and permissions.
7. **Evolve only when needed, and shed what does not help.** When a missing capability is
   confirmed, choose between a temporary solution, improving an existing component or
   creating a permanent one. Keep only changes whose benefit is shown. Remove or archive
   components whose use or benefit is not shown (§11).

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

## 4. Core Operating Loop

```
Intent → Goal Contract → Capability Discovery → Plan → Execute → Verify → Decide → Remember
                                   ↑_________________ REPLAN _________________|
```

After Verify, the system takes exactly one decision:

| Decision | Meaning |
|---|---|
| `DONE` | the final goal is reached and the result is confirmed |
| `CONTINUE` | the goal is not reached; the next step is known and permitted |
| `REPLAN` | the current path does not work; find another way while keeping the original intent |
| `BLOCKED` | no further action is possible without a missing resource, permission or critical information |
| `STOPPED` | stopped by the user, a safety limit, an exhausted budget or another set condition |

**Invariant:** `turn_completed ≠ goal_completed`. A finished model reply, a finished
subagent, a finished local stage or a set of passing tests does not by itself complete
the mission.

| Stage | Backed by today | Status (2026-11-05) |
|---|---|---|
| Intent → Goal Contract | `boyko-goal-compass` (INTAKE, PR #544), dispatcher, estimand-ops | goal contract skill is in review, not yet in `main`; not evaluated on real tasks |
| Capability Discovery | `skills/registry.yaml`, Boyko Agent | only 19 of 162 registry entries carry a machine-readable `capability:` block |
| Plan | routing-policy, autonomy-budget, Boyko Agent | described; end-to-end use unmeasured |
| Execute | main session, builder/tester agents, hooks | works; handoff from Boyko to executors is unproven |
| Verify | integrity, reviewer, skeptic, tests | strongest stage; `boyko_protocol_guard` checks answer format, not goal reached |
| Decide | — | not implemented as an explicit step |
| Remember | activeContext, decisions, null_results, research catalog | exists; catalog verdicts are parsed heuristically |

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

## 9. Non-goals

- Do not chase the largest number of agents, skills, hooks or integrations.
- Do not build our own agent framework where the existing runtime is sufficient.
- Do not promise unlimited or fully unsupervised autonomy.
- Do not count session length, tool calls or lines of code as usefulness.
- Do not replace real results with synthetic scores or agent self-reports.
- Do not expand infrastructure before a specific limitation it must remove is confirmed.
- Do not auto-execute Red/Black actions (deploy, publish, transfer funds, mass-delete).
- Do not be a team product, a SaaS or a marketplace listing (current Scope Fence NOT-NOW).

## 10. Definition of Done

The project fulfils its mission when, on a set of real tasks fixed in advance, the system:

1. Accepts the goal through one entry point, without the user choosing internal tools.
2. Finds and uses available capabilities within the permissions it was given.
3. Takes multi-step tasks to a confirmed result, or records a justified stop.
4. Saves and restores the state of an unfinished mission without silently changing its
   original terms.
5. Shows measured benefit against **plain Claude Code without this add-on**, on goal
   success, user interventions, cost and quality of evidence.

Item 5 is a causal claim ("the add-on improves the result"). Its experiment is
pre-registered before it runs: the same tasks in both arms, the number of tasks, the
metrics and the thresholds. A result that does not beat the plain baseline counts against
the add-on, not as a draw.

A working installer, green CI, test coverage and technically sound components are
required engineering conditions. They are not evidence that the product goal is reached.

## 11. Decision rule: adding, changing and removing components

Before adding a component or materially changing one, answer:

1. Which user goal, or which stage of reaching it, does this improve?
2. What confirmed shortcoming of the current system requires it?
3. Can the same result be reached with what already exists?
4. What is the smallest reversible experiment?
5. Which observation would show the benefit, and which would make us drop it?

If a component does not improve reaching a checkable result, it is not a priority.

**Removal rule.** A component with no measured use or benefit over 90 days goes to review:
keep, archive (`rules-cold/`, an archive branch or note) or remove. The decision and its
reason are recorded. Missing data is not proof of uselessness, so the default for a
component that may be valuable but is unmeasured is "measure first", not "remove". A
component that is measured to cost more than it gives is removed.

**Overhead budget.** The add-on must not make plain Claude Code worse. Its overhead —
context injected into every session, hook latency, false-positive rate — is measured and
kept within a stated budget. As of 2026-11-05 the always-on rules are about 132k
characters and about 46% of the hook trigger log is test-fixture noise; both are known
debts against this budget.

## 12. Public framing (ACCEPTED + APPLIED 2026-07-16)

> Owner-approved. Applied to README hero, `docs/positioning.md` §1/§3/§6, and the
> plugin/marketplace descriptions. The synchronized release was cut the same day
> (v3.10.0, 2026-07-16). Updating this framing to v2 (§1) is a separate owner decision.

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

## 13. Architectural principles

- **The user owns the goal.** The system may propose a sharper wording or an alternative,
  but must not quietly change the result the user wants.
- **The entry point is not the executor.** Goal navigation and capability selection
  (Boyko) can live in a main-session skill, a specialized subagent, or both; the choice
  follows measured effectiveness, not the component's name.
- **Tools serve the goal.** The count of skills, agents, hooks, rules and integrations is
  not a measure of success.
- **Existing capabilities first.** A new tool is built only when existing ones are shown
  not to deliver the result at acceptable cost and risk.
- **Autonomy is bounded by permission.** The system acts on its own inside the agreed
  area, but a goal statement alone never grants irreversible, external or sensitive
  actions.
- **Verification is independent of the executor.** An agent's own report is not enough
  evidence that the work is done.
- **Continuing must not become endless activity.** No progress, repeated failures,
  exhausted resources or a broken constraint lead to REPLAN, BLOCKED or STOPPED.
- **Measured benefit beats complexity.** Every material architectural change shows an
  improvement in user outcome, reliability or cost.

## 14. Boyko — Goal Orchestrator

Boyko is the intelligent manager of user missions. It understands what the person intends,
knows how to discover and apply the system's capabilities, finds non-obvious paths to the
goal, organizes the work of specialized executors and checks that a verifiable result is
produced. Its job is not to do everything itself, but to make sure the system does what is
needed, does not grow more complex without reason and does not lose the original goal.

In short: the person decides what they want to achieve; Boyko decides how best to
organize the system to achieve it.

| Quality | What it means in practice |
|---|---|
| Understands | intent, context and result criteria, not just keywords of the request |
| Knows | how to find available tools, agents, skills and when each applies |
| Proactive | notices non-obvious options, risks and better paths |
| Manages | chooses executors, sequences the work and tracks it |
| Responsible | does not confuse a tool being available with permission to use it |
| Verifies | requires evidence that the result is reached, not only an executor's report |
| Learns | uses confirmed experience and does not repeat known mistakes |

**Proactive is not self-directed.** Boyko surfaces options the user did not see, but does
not change the goal or start new projects without a request or the authority to do so.

**Boyko as a function is not Boyko as a subagent.** Today `agents/navigator.md`
(`boyko-agent`) can call only explorer, verifier, skill-suggester, reviewer and tester,
and must not edit code itself. In Claude Code the main session holds the conversation and
the full tool set. The working hypothesis, to be tested before any refactor:

- the main session is the real entry point and the executing orchestrator;
- Boyko is the mission-management method the main session follows;
- the Boyko subagent is the researcher and planner where an isolated context helps.

**State on 2026-11-05.** `boyko-agent` accounted for 13 of about 2,586 recorded agent
calls; `agents/navigator.md` was last changed on 2026-07-28; 19 of 162 registry entries
carry `capability:` metadata; `tests/boyko_eval` has 10 scenarios across 5 of 8 planned
categories, and delegation (category C) is not covered.

**First experiment.** One real multi-tool task with a goal contract written before the
run, executed two ways: (a) the Boyko subagent plans and the main session executes;
(b) the main session follows Boyko's method directly. Compare result reached, steps,
where the run stopped and who verified what. If (a) reaches the result, no new
architecture is needed; if it breaks at the handoff, change the entry point, not the
catalog.
