# Falsification Ladder (FL) — Enforcement Protocol

## Core Principle
**Презумпция ложности любого сгенерированного артефакта.**
Claim is valid ONLY after: estimand defined → controls + baseline + stress-test + caveats + go/no-go.

Source: "Falsification Ladder for AI-Assisted Development" (Popper + TDD + CI/CD synthesis)  
Extended: EstimandOps 2.0 (ICH E9(R1), Binette & Reiter 2024) — design-time estimand layer added.

**Stack order (MANDATORY):**
```
Zero-Signal Gate                  ← Step -5: can a falsifiable predicate be formed? (MANDATORY, always first)
     ↓
AI-Hypothesis Pre-Gates           ← Steps -4/-3: source trace + novelty (for AI-generated claims)
     ↓
EstimandOps (estimand-ops.md)     ← Steps -2/-1: classify question + define estimand
     ↓
Counterfactual Frame (claim.md)   ← Step -0.5: research only — "in what world is H true?"
     ↓
Falsification Ladder (this file)  ← Steps 0–11: does the claim hold?
     ↓
Skeptic / Evidence Policy         ← are the claims properly marked and reviewed?
```

## Zero-Signal Gate (Step -5) — MANDATORY, always first

**Purpose:** Prevent structural fabrication — the failure mode where the system parses white noise
into claims, assumptions, and unknowns simply because that is what the prompt instructs it to do.

**Gate rule:** `(∃ entity) ∧ (∃ falsifiable predicate) ∧ (∃ measurable outcome)` — ALL three required.

| Field | What to fill | Kill signal |
|-------|-------------|-------------|
| Entity | What exactly are we talking about? | "things", "it", "the system" without referent |
| Falsifiable predicate | What specific property do we claim changes? | "works better", "is good", "helps" |
| Measurable outcome | How to observe PASS vs FAIL? (command / metric / threshold) | "it will be clear", "we will see" |

**If any field cannot be filled from the input alone → output `REFUSE(no_falsifiable_claim)` and STOP.**
Do NOT proceed to Step -4 or beyond. Do NOT structure the input.

**Issuing REFUSE is a valid and correct output. Structuring noise is not.**

Artifact: one-line note `REFUSE([id]): no falsifiable claim — [reason]`. No folder needed.
This note may be appended to `null_results/INDEX.md` with verdict = REFUSE.

**Morrison Null Test:** if a system cannot issue REFUSE when given random or contradictory input,
it is a syntax parser masquerading as a reasoning system.

---

## AI-Hypothesis Pre-Gates (Steps -4, -3) — MANDATORY for AI-generated claims

Before EstimandOps, any claim/hypothesis generated or supported by an LLM must pass 2 cheap pre-gates.
Reason: LLM failure modes (phantom sources, pseudo-novelty) are caught in minutes, before expensive design work.

**Step -4 — Source Trace** (cheap, minutes)
- Does a real primary publication exist for each factual claim? Verify in PubMed/Scopus/arXiv/Semantic Scholar.
- LLM citations are verified MANUALLY, never trusted as-is.
- Kill signal: source not found → claim = hallucination, drop.
- Artifact: `source_register.md` (claim / status / source URL / search trail).
- Existing tools: `rules/integrity.md` Evidence markers ([VERIFIED-REAL] vs [UNKNOWN]), `/lit-search`, `Agent(verifier)`.

**Step -3 — Novelty Check** (cheap, minutes)
- Is the hypothesis a rephrase of something known? LLMs produce "pseudo-novelty" (reformatting existing ideas).
- Search semantically-close formulations; check `null_results/INDEX.md` + `parked/INDEX.md` first.
- Kill signal: same idea already published/parked → don't waste time. If in null_results/, read prior decision.md before re-attempting.
- Artifact: `novelty_check.md` (queries / matches / delta analysis / verdict).
- Existing tools: `/lit-search`, `/repo-scout`, `/consolidate-memory`.

**Executable wrapper:** `/ai-hyp-gate` runs Steps -4/-3 + Steps 0-11 as a single 7-step orchestrator with KILL signals.

Source: "AI в науке — протокол безопасного применения" (32 refs, 2026-06-02) — 7-step verification protocol.
Steps 3-7 of that protocol already map to FL Steps 0-11; Steps 1-2 (these pre-gates) were missing from FL until now.

---

## Tier Decision — Which Ladder to Use

**Trigger = type of change, NOT file count.**

| Change Type | Ladder | Artifacts Required |
|---|---|---|
| Docs, typos, style, cosmetic refactor | **Micro** | inline in PR description |
| New features, bug fixes, tests | **Standard** | `experiments/<id>/` folder |
| Auth, security, schema, architecture | **Full** | `experiments/<id>/` + stress tests |
| Research, AI claims, hypotheses | **Full** | Full 11-step + `null_results/` entry |

**Rule:** When in doubt → upgrade tier. Downgrading requires explicit justification.

---

## Micro-Ladder (≤30 min, PR inline)

Four lines in PR description (EstimandOps L0 + L7 integrated):
```markdown
**Question type:** [ ] descriptive  [ ] predictive  [ ] causal
**Claim:** [what should be true after this change, for which population]
**Check:** [how verified — command or observation]
**Caveat / What this does NOT mean:** [known limitation or non-interpretation]
```

No folder needed. No separate files.

---

## Standard-Ladder (feature / bug fix)

Create `experiments/<id>/` using the template at `experiments/_template/`.

Minimum required files before marking DONE:
- `claim.md` — falsifiable statement
- `controls.md` — positive control + negative control
- `decision.md` — promote / repeat / reject / archive

Optional but recommended:
- `stress_tests.md`
- `caveats.md`

---

## Full-Ladder (arch / security / research)

All 14 steps (Zero-Signal Gate + EstimandOps pre-steps added). Additional 2 pre-gates (-4, -3) MANDATORY for AI-generated claims.
All files required:

| Step | Action | Artifact | Required for |
|---|---|---|---|
| **-4** | **Source Trace** — verify each fact-claim has primary source | `source_register.md` | AI-generated claims only |
| **-3** | **Novelty Check** — search literature + null_results/ + parked/ | `novelty_check.md` | AI-generated claims only |
| **-2** | **Classify question type** (descriptive / predictive / causal) | `claim.md` — L0 checkbox | All Full-Ladder |
| **-1** | **Define estimand** (population, intervention, comparator, endpoint, summary measure, MCID, ICE) | `estimand.md` | All Full-Ladder |
| 0 | Define falsifiable claim derived from estimand | `claim.md` | All Full-Ladder |
| 1 | Smallest testable hypothesis | `experiment.yaml` |
| 2 | Build minimal artifact | source diff + `manifest.md` |
| **2a** | **Verification Substrate Gate** — is the test infrastructure itself trustworthy, separate from whether the claim is true? See below. Must resolve to READY before Step 3. | `substrate_gate.md` |
| 3 | Positive control (known-good input) | `controls.md` |
| 4 | Negative control (known-bad input) | `controls.md` |
| 5 | Define baseline | `baselines/<id>.json` |
| 6 | Run test | `metrics/run.json` |
| 7 | Stress-test (adversarial / edge cases) | `stress_tests.md` |
| 8 | Classify result (promote/repeat/reject) | `result_summary.md` |
| **8a** | **If PROMOTE: run skeptic with context-asymmetry (claim.md + code only, NO reasoning chain).** Skeptic verdict is NOT a veto — it is input. See response matrix below. | `skeptic_verdict.md` |
| 9 | Document caveats + "what this does NOT mean" | `caveats.md` |
| 10 | Go/no-go decision | `decision.md` |
| 11 | Update project memory | `null_results/<id>.md` if rejected |

**Step 2a — Verification Substrate Gate (test could not run ≠ claim failed):**

Before any control or test executes, resolve one question that has nothing to do with whether
the claim is true: **can the current infrastructure even test it honestly right now?** This
gate exists because "the test didn't run" and "the test ran and disproved the claim" are
different facts with different consequences — conflating them either buries a real result
under a false excuse, or (the more common and more dangerous failure) lets an infrastructure
problem quietly masquerade as evidence about the claim. A hook registered on the wrong event,
a guard that's reachable but never actually enforced, a dependency silently missing — none of
these are findings about the hypothesis. They are findings about the substrate.

**Three outcomes, only one lets you proceed:**

| Verdict | Meaning | What happens to the claim's evidence status |
|---|---|---|
| `READY` | Environment reproducible, dependencies pinned, provenance known, protective tooling isn't distorting the run | Proceed to Step 3 |
| `BLOCKED-INFRASTRUCTURE` | Substrate itself can't run the test (broken deps, wrong hook wiring, missing tool) | **Unchanged.** Not FAIL, not REJECT — whatever it was before stays. Fix the substrate, re-run this gate, then retry Step 3. |
| `UNTRUSTED-ENVIRONMENT` | Substrate runs, but something about it can't be trusted (uncommitted changes of unknown scope, unverified provenance of a critical constant/function) | **Unchanged**, same as above, but the fix is trust/provenance work, not infrastructure repair |

**Checklist (all must pass for READY):**

| Check | What it verifies |
|---|---|
| Environment | Versions/platform pinned; the run is actually reproducible, not "worked once" |
| Code provenance | The source of every function/constant the test depends on is known — not assumed |
| Dependencies | A lockfile or equivalent pinning exists |
| Exactness | The critical verdict doesn't hinge only on floating-point rounding |
| Test-harness sanity | The testing apparatus itself has a working smoke test — this is a check on the harness, not the scientific positive/negative controls of Steps 3-4, which come after this gate |
| Artifacts | Output is persisted to a file/log, not asserted only in conversation |
| Security/integrity | Protective hooks/guards run as documented and don't silently no-op, block, or distort the actual test |
| Clean state | Uncommitted changes and the experiment's scope boundary are both known, not ambiguous |

**Hard rule:** a `BLOCKED-INFRASTRUCTURE` or `UNTRUSTED-ENVIRONMENT` verdict must never be recorded
as evidence against the claim. If a decision.md or result_summary.md ever reads "test failed"
when what actually happened was "test could not run" — that is a Substrate Gate violation,
fix the record before anything else.

**Additional requirement for question_type = causal:**
- Step -1 must include: DAG attached, 4 identifiability assumptions checked, identification strategy named
- Step -1 artifact: `estimand.md` (full canvas) + optionally `dag.md`
- Causal claim without DAG + identifiability = INVALID regardless of test results

---

**Step 8a — Skeptic Response Matrix (skeptic is NOT a veto):**

Skeptic's job: find weaknesses. YOUR job: respond to each concern.

| Skeptic verdict | Meaning | What to do | Idea status |
|---|---|---|---|
| `[CONFIRMED-REAL]` | Claim holds under attack | Promote freely | ✅ Survives intact |
| `[WEAKENED]` | Claim holds but narrower scope | Promote with `[WEAK]` marker + document caveat in caveats.md | ✅ Survives with marker |
| `[NEEDS-REAL-DATA]` | Can't confirm without real-world data | Promote as `[HYPOTHESIS]` pending validation | ✅ Survives as hypothesis |
| `[FALSIFIED]` | Specific concern found | For EACH concern: Fix / Accept-with-doc / Dismiss-with-reason → record in ADR | ⚠️ Respond, then re-assess |

**FALSIFIED ≠ KILLED.** It means: "this concern needs a response."
After responding, record in `decision.md → ## Skeptic Concerns`:
```
- Concern: [description]  →  **Dismissed** (reasoning: the skeptic assumed X, but our claim is about Y)
- Concern: [description]  →  **Accepted limitation** (documented in caveats.md)
- Concern: [description]  →  **Mitigated** (added guard Z to claim scope)
```

**True kill condition:** skeptic finds that the CORE predicate of the claim is false AND no response (fix/accept/dismiss) is viable. This is RARE. Most FALSIFIED concerns fall into "Dismissed" or "Accepted limitation."

**Shortcut when confident:** if you can predict skeptic concerns in advance and pre-answer them in the ADR, you may log `[SKEPTIC-PRE-ANSWERED]` and skip Step 8a. But write the pre-answers — no blank credit.

**Recomposition Gate (part of Step 8a when the claim was atomized into sub-claims):**
Each sub-claim passing its own independent check does NOT mean the sub-claims cohere
when reassembled into the full claim. Individually-true pieces can rest on mutually
exclusive or unstated shared assumptions that only surface at reassembly. Add this
question to the skeptic prompt whenever the claim has ≥2 independently-verified parts:
> "Do these sub-claims, each individually true, still combine validly to support the
> FULL claim as worded — or does stating the full claim silently add an assumption
> that was never itself tested?"
Kill signal: the recomposed wording is stronger than what any individual sub-claim,
or their conjunction, actually licenses (classic pattern: "A is real" + "B is real" →
worded as "A causes/validates B" without a test of that link).

---

## Structure-Bias Guard (anti-over-formalization)

**Problem this solves:** FL forces structured artifacts (claim.md, schemas, estimand.md, YAML)
on every step. Over-applying rigid format to a *reasoning* step degrades reasoning quality —
forcing JSON/XML output on math, logic, or causal-derivation tasks suppresses the scratchpad
tokens the model needs to think. The effect is task-dependent: heavy on reasoning, light on
classification/extraction. Source: "Let Me Speak Freely?" (arXiv 2408.02442).

**Rule:** Formal structure is for the OUTPUT CONTRACT (the final artifact), NOT for the
REASONING LAYER (deriving the hypothesis, working through a proof, causal analysis).

| Step type | Format discipline |
|-----------|-------------------|
| Reasoning / derivation (deriving claim, proof, DAG logic, causal chain) | Free-form first. Let the model think in prose/scratchpad, THEN serialize the conclusion into the artifact. |
| Output contract (claim.md fields, experiment.yaml, metrics/run.json) | Strict schema — structural validity matters here. |

**Anti-pattern:** wrapping a reasoning-heavy step in a rigid JSON schema and wondering why the
derivation got worse. Reason in prose, serialize the answer. Structure the SHAPE, not the THINKING.

Note: syntactic validity ≠ semantic truth ("JSON mode solves shape, not truth"). A schema-valid
artifact can be fully hallucinated — structural validators do NOT replace the evidence/skeptic layer.

---

## Context Asymmetry Rule (Skeptic Agent)

**When invoking skeptic for FL review:**

```markdown
DO give skeptic:
- claim.md (the falsifiable statement)
- The actual code/artifact being reviewed
- controls.md (if exists)

DO NOT give skeptic:
- Session history / reasoning chain
- Success logs from previous runs
- Agent's own confidence statements
- "Background context" about why approach was chosen
```

**Why:** Agreeableness bias — LLM exposed to reasoning chain tends to validate it.
Asymmetric context = independent falsification = stronger review.

**Skeptic prompt template:**
```
You are a falsification agent. Your job is NOT to confirm but to break.
Given: [claim.md contents]
Given: [code/artifact — raw, no framing]
Task: Generate 3 test cases that would FALSIFY this claim.
Then run them (or specify exact commands). Report: CONFIRMED / FALSIFIED / NEEDS-REAL-DATA.
Do NOT consider how the code was built or why. Only: does the claim hold?
```

**Builder Blindness Rule (symmetric to Context Asymmetry, opposite direction):**
Context Asymmetry protects the SKEPTIC from the builder's reasoning. This protects the task
from the BUILDER's foreknowledge — when roles are split (builder writes the implementation,
falsifier/checker later verifies it), the builder's prompt must contain the specification and
success criteria the claim itself defines, but NOT the specific test cases, edge conditions, or
falsification strategy the Falsifier will later use. A builder who knows exactly what will be
checked writes code shaped to pass that check, not code that solves the actual problem — the
same failure mode as a student who has seen the exam questions. This matters most exactly when
Micro/Standard-Ladder speed pressure tempts skipping the split and letting one agent both build
and know the acceptance test in advance.

**Independent Verification Strength Ladder (for Perelman condition 5 / external reconstruction):**
Not all "independent verification" is equally independent. When citing external reconstruction,
name which rung was actually used — "confirmed by another AI service" is not a strong claim by
itself, see the ranking below:

| Verification | Real independence |
|---|---|
| Same model, new prompt | Weak |
| Same model, isolated context | Weak–Medium |
| Different model | Medium |
| Independently-written code | Strong |
| Symbolic solver / Lean / Coq | Strong (for formal claims) |
| Blind replication by another group | Very strong |
| New physical/empirical experiment | Strongest (for empirical claims) |

Multiple models do not automatically become independent — they can inherit the same sources,
the same benchmark patterns, and the same problem framing. Sandbox isolation, genuinely
different models, and explicit disagreement analysis are worth more than simple voting across
several instances of a similar setup.

---

## null_results/ vs parked/ Protocol

**Verdict routing (critical distinction):**

| Verdict | Where | Meaning |
|---|---|---|
| REJECT | `null_results/<id>-<slug>.md` + `null_results/INDEX.md` | Claim falsified — do NOT retry without fundamentally different approach |
| ARCHIVE | `parked/<id>-<slug>.md` + `parked/INDEX.md` | Valid but deprioritized — revisit when conditions change |
| PROMOTE / REPEAT | stay in `experiments/<id>/` | Active or promoted — no archival |

**On REJECT:**
1. Copy filled-in `decision.md` to `null_results/<id>-<claim-slug>.md`
2. Add entry to `null_results/INDEX.md`: `| <id> | <date> | <slug> | REJECT | <why falsified in 10 words> |`
3. Never delete

**On ARCHIVE:**
1. Copy filled-in `decision.md` to `parked/<id>-<claim-slug>.md`
2. Add entry to `parked/INDEX.md` with: why parked + what would trigger revival

**Pre-work check:**
```bash
grep -i "keyword" null_results/INDEX.md  # falsified — don't repeat
grep -i "keyword" parked/INDEX.md        # valid but deferred — might resume
```

---

## Pearl Registry

Not every useful observation fits the REJECT/ARCHIVE/PROMOTE verdict shape above — sometimes
an experiment surfaces a side-finding that isn't about the current claim at all, but is real
and testable. Losing that because it didn't fit the current decision.md is a common failure
mode. The Pearl Registry is a lightweight, separate ledger for exactly those.

**Pearl Gate (run after any verdict):** ask "did this experiment surface an unexpected but
testable insight?" — an unexpected connection between domains, an anomaly that doesn't fit
the current claim but is falsifiable, or a side-observation that could become its own
experiment. If yes, add one row to `pearl_registry/INDEX.md` (`hooks/research_health_loop.py`
reads this file to flag entries whose `next_check` has lapsed):

```
| <date> | <source_experiment_id> | <observation> | <falsifiable_prediction> | <impact_score> | <trigger_condition> | <next_check> | pending |
```

| Field | What to write |
|---|---|
| `observation` | what was noticed — one line, concrete |
| `falsifiable_prediction` | what must be true if the observation is real |
| `impact_score` | 0–10, estimate NOW, don't wait for confirmation (table below) |
| `trigger_condition` | what event justifies picking this up |
| `next_check` | a real date or milestone for review — not "someday" |

**Impact Score (0–10) — assigned at write time, not after verification:**

| Score | Criterion |
|---|---|
| 0–2 | Local observation, useful only to this branch |
| 3–5 | Transferable to 1–2 nearby experiments in this project |
| 6–8 | Touches an assumption several branches depend on |
| 9–10 | Would change the structure of the main task or the whole project |

The score estimates reachable SCALE, not probability of being true — that's what
`pending`/`verified`/`refuted` already tracks. A high score sitting at `pending` is not a
contradiction: it means "expensive to verify, but expensive to ignore too."

**Hard rule:** a Pearl Registry entry without a concrete `falsifiable_prediction` AND a
`next_check` date is not a pearl, it's a todo list item — don't add it. A high `impact_score`
does not waive `next_check`; an unanchored "important" entry decays into noise exactly like an
unanchored ordinary one, just louder.

---

## Hindsight Distortion Gap Heuristic

**Source:** validated via a 5-case cross-domain pilot (2026-07-15,
`docs/scientific-discovery-engineering/pattern_cards/pattern_001_hindsight_distance.yaml`) —
not abstract design. 5/5 cases confirmed, 0 counter-examples, including one case
(Barbara McClintock's transposon discovery) deliberately chosen to try to break the
pattern. Confidence: MEDIUM-HIGH.

**The heuristic:** the risk that an account of *why* something happened is a
retrospective distortion (embellished, wrong mechanism, self-serving narrative) grows
with the time gap between the event and its first substantive documentation — **not**
with how long the result took to be *accepted*. These are two different gaps and must
not be conflated (McClintock: near-zero documentation gap, 30+ year acceptance delay,
correspondingly clean historical record — vs. Kekulé: ~25-year documentation gap told
at his own anniversary tribute, correspondingly contested account).

A single event can also carry **two separate gaps at once**: the *result* (what was
found) and the *story of the mechanism* (how it was found) don't have to share a
timeline. Watson & Crick's 1953 DNA structure had near-zero documentation gap for the
result, but the mechanism narrative ("the instant I saw Photo 51...") was first
published 15 years later (Watson's 1968 book) and was itself revised again decades
after that by independent scholarship. Trust the result at the gap the result was
documented at; trust the mechanism story at the gap the mechanism story was documented
at — don't let a fresh result launder an old, undocumented mechanism claim.

**Apply this inside the repo, not just to historical science:**

- A `decision.md` or post-mortem written the **same session** as the debugging work
  is more trustworthy about *why* a fix worked than one reconstructed from memory
  weeks later. This is already the implicit assumption behind `memory-protocol.md`'s
  "update activeContext.md after each commit" rule — this heuristic makes the
  reasoning explicit and gives it a name.
- When a sub-agent or a session's own retrospective explains *why* an approach was
  chosen, and that explanation is written well after the decision was made (not
  logged at decision time), discount it the same way this heuristic discounts
  Kekulé's 25-years-later dream story — plausible, not evidence.
- When auditing an external research artifact (see the `boyko-*` skill family) for
  fabrication risk: a document's own "the one gate we didn't run yet" marker
  (analogous to a raw result) can be genuine even when its narrative framing
  (analogous to the mechanism story) is embellished — check the two separately.

**Hard rule:** do not treat "this was accepted/adopted slowly" as evidence that a
narrative is likely distorted — check the actual gap between event and *first
recorded account*, not the gap between event and *acceptance*. Conflating the two is
the specific error this heuristic was built to catch (see McClintock case).

---

## Experiment ID Format

```
<YYYYMMDD>-<short-slug>
Example: 20260514-prompt-injection-detection
```

---

## Anti-Overfitting Gate (OSA integration)

**When a null result triggers hypothesis revision, run ALL 5 checks before proceeding.**
If "no" on ≥2 → mark variant as `[SPECULATIVE]`, not `[HYPOTHESIS]`. Do NOT promote.

| # | Check | Question | Kill signal |
|---|---|---|---|
| AOG-1 | Pre-registration | Was the modification predictable from theory BEFORE the null result? | "No" → post-hoc rationalization |
| AOG-2 | Specificity | Is the relaxed version at least as specific as the original? (compatible with same or fewer results?) | "No" → widening unfalsifiability |
| AOG-3 | Novel prediction | Does the variant produce ≥1 new testable prediction the original didn't have? | "No" → content-free revision |
| AOG-4 | Non-triviality | Does the hypothesis remain falsifiable? (not compatible with ALL possible results?) | "No" → the hypothesis is empty |
| AOG-5 | Independent motivation | Is there an independent basis for THIS modification, separate from wanting to save the hypothesis? | "No" → motivated relaxation |

**Minimal Relaxation Rule** (hard rule, no exceptions):
> When revising a hypothesis after null result, change **ONE assumption at a time** per new variant.
> Multi-assumption changes → new experiment ID + new claim.md. No bundling.

**Kill Analysis mandate** (required in every REJECT decision.md):
1. State EXPLICITLY what the null result killed: "H under conditions {A₁∩A₂∩A₃}"
2. State EXPLICITLY what was NOT killed: "Core mechanism X (independent theoretical basis), A₁, A₂"
3. Build Relaxation Map for surviving assumptions: Remove/Weaken/Replace × one assumption each

Without Kill Analysis, REJECT is incomplete. A vague "hypothesis falsified" loses information about surviving option space.

---

## Adaptive Iteration — Branch Rule (OSA integration)

**When the user proposes a new variant mid-flight** ("try this", "what about X") —
do NOT reset the investigation. Add it as a branch and check it against what is already dead.

1. Preserve the current option map — do not discard prior work.
2. Identify which assumption the variant changes (one, ideally — see Minimal Relaxation Rule above).
3. Check `null_results/INDEX.md` + `parked/INDEX.md` + killed branches: was this already tried?
4. If already killed → require a NEW condition that revives it (changed assumption, new data, fixed tooling). No blind retry.
5. If alive → define the cheapest test that promotes or kills it.
6. Compare expected information gain against current alive branches before executing.

Branch record (append to `decision.md` or experiment notes):

| Branch | User suggestion | Changed assumption | Already killed? | Revival condition | Cheapest test | Decision |
|---|---|---|---|---|---|---|

**Relation to Minimal Relaxation Rule:** that rule governs *your own* revision after a null result;
this rule governs *the user's* mid-flight suggestion. Both enforce the same discipline — one assumption
at a time, never silently re-run dead work.

---

## Cheapest Differentiating Test Protocol (OSA)

A cheapest test is NOT the fastest test. It maximizes **decision value per cost**.

**Evaluation criteria:**

| Criterion | Question | Weight |
|---|---|---|
| Differentiation | Does it distinguish between competing alive branches? | High |
| Kill power | Can it falsify the current formulation? | High |
| Rescue power | Can it surface a weaker non-circular formulation? | Medium |
| Specificity | Does it test this branch, not a vague neighborhood? | High |
| Non-circularity | Does it avoid assuming the desired result? | Critical |
| Reuse value | Will the result inform other alive branches? | Medium |
| Cost | Time / compute / token / human effort | Minimize |

**Selection rule:**
```
max(differentiation + kill_power + rescue_power + reuse_value − circularity_risk) / cost
```

A test that is cheap but non-differentiating is **not a valid cheapest test**.
A test that assumes the result it is testing is **circular** — discard regardless of cost.

**Kill signals for test candidates:**
- Test result is the same regardless of which branch is true → not differentiating, discard
- Test requires the conclusion to be true to run → circular, discard
- Test produces no new information about surviving assumptions → low reuse value, deprioritize

**Optional artifact for the Differentiation criterion:** when ≥2 hypotheses are
simultaneously alive, `experiments/_template/ach_matrix.md` (Analysis of
Competing Hypotheses — Heuer 1999 / Platt's Strong Inference 1964) makes
"differentiation" explicit as a hypotheses × evidence matrix instead of a felt
judgment. Template only — no hook, no promotion gate, kept lightweight by design.
Skip it for a single working hypothesis; use the Pearl Registry above to capture
a side-finding instead of forcing it through this matrix.

---

## Anti-Patterns (FL violations)

| Violation | Detection | Fix |
|---|---|---|
| **Structuring input without Zero-Signal Gate** | → claim.md filled but no entity/predicate/outcome table | REFUSE or restate input until gate passes |
| **Missing REFUSE on unfalsifiable input** | → Morrison Null Test: system found structure in white noise | Add Step -5 check, re-evaluate input |
| "All tests passed" without controls.md | → SKEPTIC-TRIGGER (skeptic-triggers.md rule 3) | Add controls first |
| F1=1.000 or 100% | → SKEPTIC-TRIGGER (rule 1 + 4) | Rerun on real data |
| decision.md written before controls.md | → invalid — regenerate in order | Follow step sequence |
| Micro-ladder for security change | → upgrade to Full, no exceptions | No downgrade |
| Skeptic given session history | → asymmetry violated, re-run skeptic clean | Strip context |
| **claim.md written before estimand** | → estimand not defined, claim is unmeasurable | Fill estimand.md first |
| **Causal claim without DAG** | → identifiability unknown | Draw DAG or downgrade to descriptive |
| **ICE handled as missing data** | → imputation of post-baseline event | Reclassify as ICE, choose strategy |
| **Descriptive result interpreted causally** | → "X is associated with Y → X causes Y" | Remove causal language or add causal layer |
| **Summary measure is HR or OR in heterogeneous pop** | → noncollapsible, drifts with covariates | Switch to risk difference or RMST |
| **MCID not defined** | → "statistically significant" without practical threshold | Define MCID before analysis |
| **AI-generated claim without source trace** | → claim.md cites no primary sources (no DOI/PMID/arXiv) | Run Step -4 mandatory. Verify each fact-claim via `/lit-search` or `Agent(verifier)`. |
| **Pseudo-novelty (LLM rephrase of known result)** | → similar published work found AFTER experiment started | Run Step -3 mandatory. Search `null_results/INDEX.md` + `parked/INDEX.md` + lit-search BEFORE design. |
| **Repeat of null_results without acknowledgment** | → grep null_results/INDEX.md matches current claim | Read prior decision.md. New attempt MUST address why previous failed (different method/data/scope). |
| **REJECT without Kill Analysis** | → decision.md says "falsified" but no "what survived" section | Add Kill Analysis: what killed, what NOT killed, Relaxation Map |
| **Multi-assumption revision** | → next attempt changes A₁ AND A₂ after null result | Minimal Relaxation Rule: split into separate variants V1, V2 with separate IDs |
| **No escape_route.md before expensive test** | → test cost > $100 or > 2 days without pre-specified action per outcome | Fill escape_route.md first. No exemptions for expensive experiments. |
| **User variant executed without branch check** | → re-ran a path already in null_results/ because the user suggested it | Adaptive Iteration Branch Rule: grep null_results + parked first; require a revival condition for killed branches |
| **Rescue bypasses AOG** | → branch promoted to `weak_alive` without AOG check | Rescue alone → `parked` only; AOG required before `weak_alive` |
| **Circular cheapest test** | → test assumes the result it is testing | Discard test; find differentiating alternative; use CDT Protocol |
| **Rescue applied to `hard_killed`** | → rescue review attempts to revive theorem-level contradiction | `hard_killed` is outside Rescue scope — requires new theorem-level input |
| **Hypothesis generation from brainstorm** | → new branches proposed without surviving assumptions as input | Hypothesis Generation Mode requires explicit Kill Analysis output as input |

---

## Relationship to Existing Rules (conflict resolution)

### FL vs Doubt-Driven Development (DDD)

DDD Step 1 requires passing to skeptic: Goal + Proposal + Reasoning + Alternatives.
FL Context Asymmetry says: do NOT give skeptic reasoning or context.

**Resolution:** These serve different purposes — use both in sequence:

```
1. DDD first: Red-team the DESIGN before building (skeptic gets full DDD context)
2. FL after:  Validate the ARTIFACT after building (skeptic gets only claim.md + code)
```

DDD skeptic = "Is this the right approach?" (design review, context-heavy)
FL skeptic   = "Does this artifact do what it claims?" (falsification, context-blind)

They are complementary, not contradictory. Both are required for Full-Ladder.

### FL vs integrity.md Submission Gate

integrity.md Submission Gate = external publication (preprints, releases, public posts).
FL decision.md = internal go/no-go (merge to main / deploy).

**Resolution:** FL decision.md is a prerequisite BEFORE Submission Gate, not a replacement.

```
FL decision.md (PROMOTE) → then → integrity.md Submission Gate (if external release)
```

For internal merges only: FL decision.md is the final gate. Submission Gate is not required.

### FL vs skeptic-triggers.md

stress_tests.md is "optional" in Standard-ladder, BUT:
**If Standard-ladder result shows ≥90% success OR "all tests passed" → stress_tests.md becomes REQUIRED.**
Skeptic-triggers Trigger 3 overrides the "optional" label.

| Existing rule | FL relationship |
|---|---|
| `integrity.md` — [VERIFIED] markers | FL adds physical artifact requirement on top |
| `skeptic-triggers.md` — auto-triggers | FL adds context asymmetry + Trigger 3 overrides optional stress_tests |
| `audit-verification-gate.md` — HIGH/MEDIUM gate | FL go/no-go is upstream of this gate |
| `doubt-driven-development.md` — DDD | DDD = design review (before build), FL = artifact validation (after build) |

### FL Rescue Layer vs Anti-Overfitting Gate (AOG)

Rescue Layer prevents premature deletion of promising directions.
AOG prevents ad hoc resurrection of killed hypotheses.

**Apparent conflict:** Rescue wants to preserve weak branches; AOG blocks motivated revision.

**Resolution (priority rule):**
```
Red Team → Rescue Review → AOG Check → Final Status
```

- Rescue may assign `parked` without AOG — preserving the branch, not promoting it.
- Rescue may NOT assign `weak_alive` or `alive` without AOG (≥3 of 5 checks pass).
- `hard_killed` is outside Rescue scope — only new theorem-level input can change it.
- Rescue saves directions. AOG decides whether a direction can be promoted to a branch.

**Key invariant:**
```
Red Team kills claims.
Rescue saves directions (→ parked).
AOG decides whether a direction can become a branch (→ weak_alive).
Cheapest differentiating test decides the next action.
```

---

## Quick Reference Card

```
ANY claim or experiment?  → Zero-Signal Gate FIRST (Step -5): entity + predicate + outcome?
                            If any missing → REFUSE(no_falsifiable_claim), STOP.
Before running ANY test?  → Substrate Gate (Step 2a): READY / BLOCKED-INFRASTRUCTURE /
                            UNTRUSTED-ENVIRONMENT. Infra failure is NEVER recorded as evidence
                            against the claim — "test could not run" ≠ "claim failed".
Routine change?          → Micro (PR inline: question_type + claim + check + caveat/not-mean)
Feature / bugfix?        → Standard (claim.md + experiment.yaml + controls + decision)
Auth/arch/research?      → Full (all 14 steps incl. estimand.md)
Research + causal?       → Full + estimand.md with DAG + 4 identifiability checks
>90% success on Standard → stress_tests.md required (overrides "optional")
Skeptic for design?      → DDD protocol (give full context: reasoning + alternatives)
Skeptic for artifact?    → FL protocol (give ONLY claim.md + code, NO history)
Estimand for design?     → EstimandOps protocol (Steps -2/-1 BEFORE claim.md)
AI-generated claim?      → Run pre-gates -4/-3 BEFORE estimand; executable via `/ai-hyp-gate`
Experiment REJECT?       → null_results/<id>.md + null_results/INDEX.md
                           + Kill Analysis: what killed, what NOT killed, Relaxation Map
Experiment PROMOTE?      → MANDATORY: run skeptic (Step 8a) — claim.md + code ONLY, no session history.
                           Skeptic is NOT a veto. FALSIFIED → respond per matrix (Dismiss/Accept/Mitigate).
                           True kill = core predicate false with no viable response (RARE).
Claim atomized into ≥2   → Recomposition Gate (part of Step 8a): do the independently-verified
sub-claims?                pieces still cohere when reassembled, or does recomposition silently
                           add an untested assumption?
Experiment ARCHIVE?      → parked/<id>.md + parked/INDEX.md
External release?        → FL decision first → then integrity.md Submission Gate
Hypothesis revision?     → Minimal Relaxation Rule: ONE assumption changed per new variant
                           + Anti-Overfitting Gate (AOG-1 through AOG-5) before promoting
User proposes a variant? → Adaptive Iteration Branch Rule: check null_results/parked first,
                           add as branch, don't reset the option map
Branch marked killed?    → Rescue Review (decision.md): formulation killed or whole branch?
                           → Final Status: hard_killed / killed / parked / weak_alive
Rescue → weak_alive?     → AOG required (≥3 of 5 pass) before promoting
Cheapest test needed?    → CDT Protocol: max(differentiation + kill_power + reuse) / cost; never circular
Parked branch revival?   → Revival Condition must be explicit + measurable
Research hypothesis?     → Counterfactual Frame FIRST (claim.md § Counterfactual Frame):
                           "In what world is H true? How many independent changes needed?"
Old post-mortem/decision.md, or narrative written long after the event?
                          → discount per Hindsight Distortion Gap Heuristic (gap to
                            FIRST RECORD, not gap to acceptance — don't conflate)

EstimandOps refs:
  Full protocol:         rules/estimand-ops.md
  Estimator lookup:      docs/estimand-to-estimator-map.md
  Canvas template:       experiments/_template/estimand.md

OSA integration refs:
  Kill Analysis / Rescue Review / Hypothesis Generation Mode: experiments/_template/decision.md
  Escape Route Map:           experiments/_template/escape_route.md
  Counterfactual Frame:       experiments/_template/claim.md
  Cheapest-test optional aid: experiments/_template/ach_matrix.md
```
