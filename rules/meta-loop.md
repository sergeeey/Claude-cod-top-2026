# Meta-Loop — The Control Loop This Stack Already Runs

**Purpose.** This file does not introduce new machinery. It names the control loop that the
existing rules already implement piece by piece — `falsification-ladder.md`, `estimand-ops.md`,
`doubt-driven-development.md`, `perelman-audit.md`, `memory-protocol.md`,
`delegation-contract.md`, `integrity.md`, `research-methodology.md` — and gives it one canonical
shape so a session (or a future rule author) can see the whole loop instead of rediscovering one
node of it in isolation.

**Source.** Extracted 2026-09-07 from comparing this stack against an external "MethodOps"
proposal (8-stage state machine: CLASSIFY → CONTRACT → SUBSTRATE → ROUTE → EXECUTE → VERIFY →
ADVERSARIAL → DECIDE → {RECOMPOSE, NULL_RESULT→POSTMORTEM, REPLAN, NEEDS_HUMAN} → MEMORY →
METHOD_UPDATE). The comparison found most nodes already implemented, several MORE granular than
proposed (Substrate Gate, Recomposition Gate, Perelman's 5-verdict vocabulary). Two nodes were a
genuine, confirmed gap — closed below (§ CONTRACT, § CLASSIFY). This file is the missing
connective tissue, not a rewrite of what already works.

**Hard rule for this file itself:** when a node below already has a canonical implementation,
this file POINTS to it by exact name/section, it does not restate or re-derive it. Restating
invites the same drift `falsification-ladder.md` Step 2b's own correction note warns about
(a near-duplicate gate was almost built for something `docs/oracle-adequacy-gate.md` already
covered — caught only because an external review flagged it before it reached main). Don't repeat
that here: if a node's real implementation changes, this file's pointer should still resolve
correctly without itself needing to change.

---

## The Loop

```
GOAL
 │
 ▼
CLASSIFY ───────────── § below (NEW, lightweight)
 │
 ▼
CONTRACT ─────────────  delegation-contract.md (Agent-scoped)
 │                      estimand-ops.md L1 (research-scoped)
 │                      § below Task Passport (NEW, general-purpose gap)
 ▼
SUBSTRATE_CHECK ──────  falsification-ladder.md Step 2a
 │
 ▼
ROUTE ────────────────  CLAUDE.md § AGENTS + SessionStart dispatcher + skill catalog
 │
 ▼
EXECUTE ──────────────  CLAUDE.md § WORKFLOW (Plan-First, 80/20, Using Wheels First)
 │
 ▼
VERIFY ───────────────  falsification-ladder.md Steps 3-6 (controls/baseline/run)
 │                      audit-verification-gate.md (tool-verified evidence)
 │                      integrity.md § Verify-Output Principle
 ▼
ADVERSARIAL_CHECK ────  falsification-ladder.md Step 8a (Context Asymmetry Rule)
 │                      doubt-driven-development.md (design-time variant)
 │                      skeptic-triggers.md (when it auto-fires)
 ▼
DECIDE ───────────────  falsification-ladder.md Steps 8/10
 │                      perelman-audit.md § Promotion Rule (5 conditions, 8-verdict vocabulary)
 │
 ├── ACCEPT ──────────  RECOMPOSE (FL Step 8a Recomposition Gate) ──┐
 │                      + small structural param + ≥2 small cases:   │
 │                      research-methodology.md § Mechanism           │
 │                      Development Mode BEFORE next hypothesis       │
 │                                                                    │
 ├── REJECT/NULL ─────  null_results/ vs parked/ Protocol            │
 │                      + Kill Analysis + Revival Condition           │
 │                      → POSTMORTEM (§ below) ─────────────────────┤
 │                                                                    │
 ├── REPLAN ──────────  Adaptive Iteration Branch Rule                │
 │                      + Anti-Overfitting Gate (AOG-1..5)            │
 │                      → back to CONTRACT, not EXECUTE               │
 │                                                                    │
 └── NEEDS_HUMAN ─────  AskUserQuestion / Stuck Detection Tier 4     │
                         (CLAUDE.md § WORKFLOW)                       │
                                                                       ▼
                                                            MEMORY_UPDATE ── memory-protocol.md
                                                                       │
                                                                       ▼
                                                            METHOD_UPDATE ── § below (partial gap)
                                                                       │
                                                                       ▼
                                                                  next GOAL
```

---

## Node-by-node: what's real, what's new

| Node | Canonical implementation | Status |
|---|---|---|
| CLASSIFY | project-level: `CLAUDE.md` SessionStart `project_classifier` dispatcher. message-level: `routing-floor`/`resource-router` hooks (keyword-based) | **Partial — see § CLASSIFY below** |
| CONTRACT | `delegation-contract.md` (Agent() calls), `estimand-ops.md` L1 attributes (research claims) | **Partial — see § Task Passport below** |
| SUBSTRATE_CHECK | `falsification-ladder.md` Step 2a — READY / BLOCKED-INFRASTRUCTURE / UNTRUSTED-ENVIRONMENT, 8-point checklist, hard rule that infra failure is never evidence against the claim | Complete, do not duplicate |
| ROUTE | `CLAUDE.md` § AGENTS, § KNOWLEDGE STORES, skill catalog | Complete |
| EXECUTE | `CLAUDE.md` § WORKFLOW (80/20, Using Wheels First, Plan-First for 3+ files) | Complete |
| VERIFY | `falsification-ladder.md` Steps 3-6, `audit-verification-gate.md`, `integrity.md` § Verify-Output Principle | Complete |
| ADVERSARIAL_CHECK | `falsification-ladder.md` Step 8a + Context Asymmetry Rule; `doubt-driven-development.md` for design-time; `skeptic-triggers.md` for auto-fire calibration. The VERIFY-vs-ADVERSARIAL split itself is already named in `falsification-ladder.md` § Relationship to Existing Rules ("DDD = is this the right approach?, FL = does the artifact do what it claims?") | Complete — more precise than a binary split |
| DECIDE | `falsification-ladder.md` Steps 8/10; `perelman-audit.md` § Promotion Rule (5 conditions) and its 8-verdict vocabulary (VALIDATED / PARTIALLY_SUPPORTED / SCAFFOLD_ONLY / BLOCKED_BY_DEFINITION / BLOCKED_BY_EVIDENCE / BLOCKED_BY_EXTERNAL_INPUT / OVERCLAIM_RISK) | Complete — more granular than ACCEPT/REJECT |
| RECOMPOSE | `falsification-ladder.md` Step 8a § Recomposition Gate — fires whenever a claim has ≥2 independently-verified sub-claims; asks whether reassembly silently adds an untested assumption | Complete |
| MECHANISM_DEVELOPMENT (new node, on ACCEPT only) | `research-methodology.md` § Mechanism Development Mode (2026-09-09) — free-form (not schema-forced, per Structure-Bias Guard) reasoning pass BEFORE the next hypothesis, gated on all 3 trigger conditions (survived falsification + real structural parameter + ≥2 solved small cases). Routes to `boyko-bridge-ladder` for multi-level transitions, not a new agent | Complete as of 2026-09-09; n=0 real invocations yet |
| NULL_RESULT | `falisification-ladder.md` § null_results/ vs parked/ Protocol, mandatory Kill Analysis, mandatory Revival Condition (contingent-vs-theorem discriminator) | Complete, load-bearing, don't touch |
| POSTMORTEM | Demonstrated, not hypothetical: `falsification-ladder.md` Step 0a (Mechanism Claim Gate) was itself produced by this exact cycle — a retrospective read of 7 skeptic corrections found a 4/7 sub-pattern (unchecked mechanism-behavior sentences) and that finding became a permanent gate in the same file. `memory-protocol.md`'s pattern routing table (`[AVOID]`/`[REPEAT]`, `[×N]` escalation) is the standing mechanism for smaller-scale versions of the same cycle | Complete as a *practice*; see § METHOD_UPDATE for the one missing piece (a template) |
| REPLAN | `falsification-ladder.md` § Adaptive Iteration Branch Rule (user-suggested variants) + § Anti-Overfitting Gate AOG-1..5 (self-driven revision) + Minimal Relaxation Rule (one assumption at a time) | Complete |
| NEEDS_HUMAN | `CLAUDE.md` § WORKFLOW Stuck Detection Tier 4 (human escalation after 3 tiers); `AskUserQuestion` tool for genuine decision points | Complete |
| MEMORY_UPDATE | `memory-protocol.md` in full — routing table, canonical-path resolution, Checkpoint Fidelity, Parallel Workstreams, Unclaimed Work Ownership, Preview-Before-Write Gate | Complete, extensively |
| METHOD_UPDATE | `rules/pearl_registry/INDEX.md` — meta-level pearls *about the methodology stack itself*, human-gated, `next_check`-anchored | **Partial — see § METHOD_UPDATE below** |
| Calibration (cross-cutting) | `integrity.md` § Evidence Markers + § Confidence Scoring (HIGH/MEDIUM/LOW/SPECULATIVE, gated by number of independent sources) | Complete as the qualitative default. A numeric ECE-style calibration gate is explicitly NOT adopted stack-wide — reserve for a context with many repeated, scored predictions against ground truth, not per-task |
| Game-theoretic layer | Not implemented | **Correctly absent** — only relevant under multiple strategic actors with gameable incentives (adversarial security work, multi-agent competition), which is not this stack's normal operating mode. Do not build this speculatively; add it only if a task genuinely has that shape |

---

## § CLASSIFY — the real gap, closing it lightweight

**The incident that motivated this section, not a hypothetical:** on 2026-09-07 the
`routing-floor` hook fired `RESEARCH (matched: 'hypotheses')` on a chat message whose ONLY
research-flavored content was the word "hypotheses" inside a block of *pasted external text*
being discussed, not a live research claim. The message was a methodology comparison, not a
scientific hypothesis — L0 gating it would have been theater. Keyword-on-message-text routing
cannot distinguish "the user is asserting X" from "the user is quoting/discussing text that
contains the word X." This is the same class of failure this project's own `patterns.md` already
tracks under `[AVOID×7]`: "keyword/regex hook matches a trigger word without checking it's an
actual assertion, not a fragment of someone else's text."

**Fix, minimal, not a new hook or classifier model:** before deferring to a keyword-matched
routing hint, ask one question explicitly: *is the matched content something the user is
asserting right now about the world/codebase, or is it inside a quotation, pasted document, code
comment, or discussion-of-a-document?* If the latter, the hook's suggestion is advisory only and
may be silently overridden — state so briefly (as already modeled in this session) rather than
following it into an inapplicable gate. This is a judgment call at the point of use, not a rule
that needs its own file; codifying it here is enough to make the override legitimate and expected
rather than a rule violation.

---

## § Task Passport — general-purpose CONTRACT for work that is neither Agent-delegated nor research

`delegation-contract.md` covers Agent() calls. `estimand-ops.md` L1 covers research claims.
Neither covers a plain bugfix, feature, or exploration task done directly (not delegated) that
is NOT a scientific claim. `CLAUDE.md`'s own Plan-First rule (3+ files → a plan) is the closest
existing gate, but it doesn't ask about risk tier, reversibility, or side effects the way the
other two contracts do.

**When to use:** any task that would otherwise start with neither a delegation brief nor an
estimand — i.e., most ordinary engineering work above trivial size. Skip it for genuinely small,
reversible, single-file changes; per the Structure-Bias Guard already established in
`falsification-ladder.md`, this is an *output contract* for scoping, not something that should
constrain the reasoning that produces the plan.

```
Goal:            <one sentence, observable outcome>
Done when:       <the specific, checkable condition that ends this task>
Risk tier:       reversible-local | affects-shared-state | hard-to-reverse   (mirrors CLAUDE.md
                 § "Executing actions with care" — reuse that vocabulary, don't invent a new one)
Substrate:       <not yet checked — resolves via Substrate Gate before EXECUTE, not guessed here>
Side effects:    <what this is allowed to touch, and explicitly what it is not>
```

Four lines. Free-form prose is fine for "Goal" and "Done when" — this is a checklist of WHAT to
state, per `delegation-contract.md`'s own precedent, not a rigid schema to fill mechanically.

---

## § METHOD_UPDATE — the one node that is real but not yet templated

`pearl_registry/INDEX.md` (global, at `~/.claude/rules/pearl_registry/INDEX.md`) already captures
observations *about the stack itself* with `impact_score` and `next_check`. What it does NOT yet
have is a template for the specific sub-case of "this observation should become a NEW rule or
gate" — as opposed to a pearl that stays a pending observation indefinitely. Step 0a is proof this
already happens (postmortem → pattern → new gate, written directly into
`falsification-ladder.md`), but it happened as an ad hoc edit, not through a named checklist.

**Minimal template, for when a pearl_registry entry crosses into "this should become a rule":**

```
Proposed rule:        <one sentence — what would the new gate/check require>
Evidence for need:     <the specific incident(s) that motivated it — cite files/commits, not vibes>
Where it lives:        <which existing rule file it extends, or that it needs a new file>
Dogfood check:          did applying it retroactively to the motivating incident(s) actually
                        have caught the problem? (if this can't be answered "yes" with a specific
                        example, the rule is probably too vague to be enforceable)
```

This is deliberately not a heavier PROPOSE→VERIFY→PROMOTE pipeline with independent review gates
— that would be over-engineering a process that, so far, has fired maybe once every few dozen
sessions. Add ceremony here only if this template itself turns out to be too thin in practice —
same discipline as the Structure-Bias Guard applies to output contracts generally.

---

## Anti-patterns

| Anti-pattern | Why it's wrong |
|---|---|
| Building a new file/gate for a node that already has one | Re-derives what `falsification-ladder.md`/`perelman-audit.md`/etc. already do, risks drift (see Step 2b's own correction story) |
| Treating a keyword-hook's routing suggestion as binding | Hooks are advisory (`CLAUDE.md` itself: "PostToolUse/UserPromptSubmit hook can only inject context... it does not make it impossible to override") — but overriding it silently without saying so IS a violation; say so, as this file requires |
| Skipping CONTRACT because "it's just a small task" | The four-line Task Passport is deliberately cheap; skipping it is only valid for genuinely trivial, reversible, single-file work |
| Turning METHOD_UPDATE into a heavyweight review board | The template above is intentionally light; this stack's actual failure mode so far has been rules NOT getting written down, not too many rules being written carelessly |
| Applying EstimandOps L0 / Falsification Ladder machinery to a task that isn't a claim about the world | The exact false-positive this file's § CLASSIFY section documents — a methodology discussion is not a hypothesis |

---

## Quick Reference

```
New task arrives?
├── CLASSIFY: is this an assertion about the world, or discussion/quotation of one? (§ CLASSIFY)
├── CONTRACT: Agent-delegated? -> delegation-contract.md
│             Research claim?  -> estimand-ops.md L1
│             Otherwise, non-trivial? -> § Task Passport (4 lines)
├── SUBSTRATE_CHECK -> falsification-ladder.md Step 2a
├── ROUTE -> CLAUDE.md AGENTS / dispatcher / skills
├── EXECUTE -> CLAUDE.md WORKFLOW
├── VERIFY -> FL Steps 3-6 + audit-verification-gate.md
├── ADVERSARIAL_CHECK -> FL Step 8a (artifact) or DDD (design, before EXECUTE)
├── DECIDE -> FL Steps 8/10 + perelman-audit.md Promotion Rule
│   ├── ACCEPT -> RECOMPOSE (FL Step 8a Recomposition Gate)
│   │            + small structural param + solved small cases? -> research-methodology.md
│   │              § Mechanism Development Mode BEFORE next hypothesis (all 3 trigger conds)
│   ├── REJECT/NULL -> null_results/parked Protocol -> POSTMORTEM
│   ├── REPLAN -> Adaptive Iteration Branch Rule + AOG -> back to CONTRACT
│   └── NEEDS_HUMAN -> AskUserQuestion / Stuck Detection Tier 4
├── MEMORY_UPDATE -> memory-protocol.md
└── METHOD_UPDATE -> pearl_registry/INDEX.md, template in § METHOD_UPDATE if it becomes a rule
```

**Last updated:** 2026-09-07
**Status:** ACTIVE — router/index only; canonical content stays in the files it points to
**Source:** comparison against an external "MethodOps" 8-stage proposal, same-session
