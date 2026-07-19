# Strong Inference — Methodology Deep Specification (Reference Contract)

> **Status:** reference contract v1 (first deep-spec of the methodology-library program).
> **Implements / is implemented by:** the `hypothesis-arbiter` skill (registry `kind: methodology`,
> `maturity: wired`). This contract is the specification; the skill is the runtime.
> **Maturity gate:** `hypothesis-arbiter` stays `maturity: wired` until the § Benchmark below is
> actually RUN and a `maturity_evidence` artifact exists (per `check_architecture` gate 10). A
> contract on paper does not promote a method — that is the anti-theater rule applied to ourselves.

This document is the **output contract** for the methodology. Per the Structure-Bias Guard
(`falsification-ladder.md`), the *reasoning* the method performs is free-form; only the artifacts
it must produce are schematized here.

---

## 1. Identity & provenance

| field | value |
|---|---|
| canonical name | Strong Inference |
| mechanism | competing mechanistically-distinct hypotheses + a discriminating (crucial) test |
| primary sources | Platt, J. R. (1964). "Strong Inference." *Science* 146(3642): 347–353. `[VERIFIED-MEMORY, HIGH]` — exact DOI/pages verification-required before external citation · Chamberlin, T. C. (1890). "The Method of Multiple Working Hypotheses." *Science* (old series) 15(366): 92–96; reprinted 1965, *Science* 148: 754–759. `[VERIFIED-MEMORY, HIGH]` |
| lineage in this repo | grew from the pattern "extract the skill from the win" — `hypothesis-arbiter` already routes SPAWN→KILL-DESIGN→IN-SILICO→RED-TEAM→ARBITRATE; this contract makes that procedure reproducible and falsifiable rather than tacit. |

**Difference from the original:** Platt's Strong Inference is a *procedure for a human scientist*.
This contract adapts it to an LLM-agent context where the failure modes differ (a single model can
generate correlated "competing" hypotheses that share a hidden assumption — see § 11). The core
predicate is unchanged: **a test that cannot exclude at least one live hypothesis is not a strong
test.**

---

## 2. What it estimates (question type)

Strong Inference is a tool for **causal / mechanism** questions — "which of these mechanisms
produced the observation?" Per EstimandOps L0 it is **NOT** a descriptive summarizer or a
predictive model. If the question is "what is X" (descriptive) or "what will X be" (predictive),
Strong Inference is the wrong tool — see § 3 contraindications.

---

## 3. Applicability

**Suitable when ALL hold:**
- ≥2 mechanistically-distinct explanations are genuinely plausible;
- an **observable outcome exists that differs across those explanations** (a real oracle, § 7);
- the cost of committing to the wrong mechanism is high enough to justify a discriminating test.

**Contraindications (do NOT use — routes to the named alternative):**
| condition | why | use instead |
|---|---|---|
| exact deterministic lookup ("what does flag X do?") | nothing to discriminate | `Grep` / read the code |
| only one mechanically-possible path | no competition | `sci-hypothesis` (single hypothesis) |
| no observable outcome distinguishes the candidates | test cannot be crucial → circular | gather data first; `estimand-bridge` |
| the dispute is about a single idea's internal validity | not competing mechanisms | `skeptic` / `claim-decomposer` |
| purely descriptive/predictive question | wrong estimand class | `analyst` / `data-analysis` |

---

## 4. Contract (inputs → outputs)

```yaml
accepts:
  required: [observation, scope]        # a surprising/ambiguous observation + its boundary
  optional: [prior_hypotheses, known_null_results, domain_model]
produces:
  - hypothesis_set        # >=2 mechanistically-distinct H, plus an explicit H0
  - prediction_matrix     # H x observable -> what each H uniquely predicts
  - crucial_test          # the test whose result excludes >=1 H
  - outcome_map           # pre-registered: result -> which H dies/survives (BEFORE running)
  - verdict               # killed / weakened / surviving-set, WITH the auxiliary assumptions
requires: [claim.atoms]   # observation decomposed into atoms first (claim-decomposer)
side_effects: []
```

If a `required` input is missing, the method MUST request it, emit `[UNKNOWN]`, or stop — it must
never silently fill the gap with a guess.

---

## 5. Protocol (12 steps — each with a completion criterion)

Free-form reasoning is expected *inside* each step; the numbered gate is the completion criterion.

1. **Fix the observation.** State it concretely. *Done when:* one sentence, no interpretation.
2. **Separate observation from interpretation.** *Done when:* the "what happened" and the "why I
   think it happened" are two distinct lines.
3. **State H0** (the null / boring explanation: noise, artifact, already-known cause). *Done when:*
   H0 is falsifiable, not a strawman.
4. **Generate ≥2 alternatives that differ in MECHANISM, not wording.** *Done when:* each H names a
   different causal pathway. (See § 11 failure mode "correlated candidates".)
5. **Write each H's unique predictions.** *Done when:* the prediction_matrix has ≥1 cell where two
   H predict *different* observable outcomes.
6. **Find the crucial test** — the one whose result excludes ≥1 H regardless of which H is true.
   *Done when:* every branch of the test's outcome kills at least one H. If no such test exists →
   stop (§ 9), the hypotheses are not yet discriminable.
7. **Verify the measurement substrate** (Substrate Gate, `falsification-ladder.md` § 2a). *Done
   when:* the test can actually run honestly (deps, provenance, no tooling distortion). A test that
   *could not run* is NOT evidence against any H.
8. **Write the outcome_map BEFORE running** (§ 8). *Done when:* every possible result is
   pre-mapped to an action. Writing it after seeing the result is rationalization.
9. **Run the crucial test.**
10. **Update:** kill / weaken / strengthen each H per the pre-registered map.
11. **Apply the Duhem–Quine qualifier** (§ 10): the verdict is "H incompatible with result *under
    assumptions A1..An and substrate S*", never "H refuted" bare.
12. **Do NOT declare a winner if ≥2 mechanistically-distinct H remain compatible.** *Done when:*
    either one H survives, or the surviving-set is reported honestly as unresolved.

---

## 6. Artifacts

```
methodology_runs/<id>/
  observation.md        # steps 1-2
  hypotheses.yaml       # H0 + alternatives, each with its mechanism
  prediction_matrix.md  # H x observable
  crucial_test.md       # the discriminating test + substrate check
  outcome_map.yaml      # pre-registered result -> action
  verdict.md            # killed/weakened/surviving + assumptions + Duhem-Quine qualifier
```

The `ach_matrix.md` template (`experiments/_template/`) is the recommended form for the
prediction_matrix when ≥3 hypotheses are simultaneously alive (Heuer's Analysis of Competing
Hypotheses — the diagnosticity view of the same matrix).

---

## 7. Oracle (the load-bearing part — a method is never better than its evaluator)

```yaml
oracle:
  target_construct: "which mechanism actually produced the observation"
  observable_proxy: "the crucial test's measurable outcome"
  gameability: "an agent can propose a test whose result it already knows -> not discriminating"
  positive_control: "a case with a KNOWN mechanism -> the method must recover it"
  negative_control: "a case where NO mechanism among the candidates is correct -> the method must
                     report 'none survive', not force a winner"
  independence: "hypothesis quality must NOT be scored by the same agent that generated them
                 (single-agent confirmation bias) -> delegate to skeptic / a second model"
```

**Hard rule:** the crucial test's oracle must be *external to the hypotheses*. If the test's result
is knowable from the hypotheses alone (no new observation), the test is circular — discard it (this
is the Cheapest Differentiating Test Protocol's non-circularity kill signal).

---

## 8. Outcome map (pre-registered, mandatory)

Written at step 8, BEFORE running:

```yaml
outcomes:
  - result: A
    action: {kill: [H2], strengthen: [H1]}
  - result: B
    action: {weaken: [H1], retain: [H2, H3]}
  - result: infrastructure_failure          # Substrate Gate
    action: {reject_no_hypothesis: true, status: substrate_blocked}   # NEVER counts against any H
```

---

## 9. Kill / stop conditions

| condition | action |
|---|---|
| success | one H survives, OR surviving-set honestly reported |
| no discriminating test exists (step 6 fails) | STOP — gather data / redefine; not a failure, an information state |
| budget exceeded | stop, report surviving-set + what test would resolve it |
| oracle invalid (§ 7) | stop — a method cannot outrun a broken evaluator |
| only same-mechanism candidates (step 4 fails) | STOP — this is `sci-hypothesis`, not Strong Inference |

---

## 10. Duhem–Quine limitation (mandatory qualifier)

A crucial test never refutes a single hypothesis in isolation. It refutes the conjunction
`H ∧ (measurement apparatus) ∧ (preprocessing) ∧ (auxiliary assumptions) ∧ (statistical model)`.
Therefore every verdict is phrased:

> "H1 is **incompatible with** result R **under** assumptions A1–A6 and verified substrate S1."

Never: "H1 is refuted." The difference is what lets a later run rescue H1 by challenging an
auxiliary assumption instead of the mechanism.

---

## 11. Failure modes (adversarial — what breaks this method)

| failure | detection | guard |
|---|---|---|
| **correlated candidates** — the "competing" H all share a hidden assumption (classic single-model trap) | do any two H die to the SAME test for the SAME reason? | force each H to name a *different* causal pathway (step 4); generate H from different framings / a second model |
| **fake crucial experiment** — the test doesn't actually discriminate | does every outcome branch kill ≥1 H? | step 6 completion criterion |
| **weak/strawman H0** | is H0 falsifiable and plausible? | step 3 completion criterion |
| **candidate padding** — many H, but only 2 are real | prune to mechanistically-distinct set | max_same_family = 1 |
| **missing true hypothesis** — the correct mechanism isn't in the set | negative control (§ 7): if none survive, the set was incomplete | report "none survive"; regenerate, don't force |
| **result-first outcome map** — map written after seeing the result | is `outcome_map.yaml` older than `metrics/run.json`? | step 8 ordering |

---

## 12. Composition

```yaml
prerequisites: [claim-decomposer]              # atomize the observation first
combines_well_with: [estimand-bridge, ach_matrix, pre-mortem]
alternatives: [sci-hypothesis]                 # single-hypothesis case
conflicts_with: [free-form brainstorming after an outcome map is pre-registered]
required_after: [skeptic]                      # independent falsification of the surviving H
```

---

## 13. Verifier

Per `falsification-ladder.md` § Context Asymmetry: the surviving hypothesis is handed to `skeptic`
with **only** claim + evidence, no reasoning chain. The skeptic's job is to break the crucial
test's discriminating power (find a third mechanism, or an auxiliary assumption that dissolves the
result). Verifier verdict is input, not veto (§ 8a response matrix).

---

## 14. Benchmark plan (B6 — DESIGNED HERE, NOT YET RUN)

**This section is a plan. No results exist yet. `hypothesis-arbiter.maturity` therefore stays
`wired`, not `dogfooded` — gate 10 enforces that a `dogfooded` claim carry a real
`maturity_evidence` artifact, and none exists until this benchmark actually runs.**

**Question the benchmark answers:** does the Strong-Inference procedure produce *better mechanism
identification* than a single-guess baseline, at acceptable cost?

**Design (lexicographic, per `estimand-ops.md`):**
- **Population:** 8–12 tasks with a KNOWN correct mechanism (so correctness is checkable), spanning:
  a deterministic-fix bug, an ambiguity-heavy bug, a genuine causal question, a false-positive
  "anomaly" that is actually noise (negative control), and a case whose true mechanism is outside
  an obvious candidate set (tests "missing true hypothesis").
- **Arms:** (A) plain model, single answer · (B) `hypothesis-arbiter` current · (C) this deep-spec
  followed strictly.
- **Primary metric (absolute, not ratio):** mechanism-identification accuracy — did the arm name
  the true mechanism? **MCID:** arm C must beat arm A by ≥1 task out of 10 to justify the overhead.
- **Secondary:** produced ≥2 mechanistically-distinct H · chose a genuinely discriminating test ·
  false-elimination rate · cost (tool calls / tokens) · human-correction rate.
- **Oracle:** blind grader with the known mechanism hidden from the arms; per § 7 the grader is NOT
  any arm.
- **Sensitivity:** re-run with the candidate order shuffled (guards against order effects).

**What this benchmark does NOT prove (pre-registered):** it does not prove Strong Inference helps
on *descriptive* tasks (wrong estimand); it does not generalize beyond the tested task family; a
tie or loss is a real result that keeps `maturity: wired` — not a reason to re-tune until it wins
(that would be the overfitting the AOG gate forbids).

---

## 15. Maturity promotion path (closes the loop)

```
now:       hypothesis-arbiter  maturity: wired      (registered + invocable, effectiveness unproven)
after B6:  IF arm C beats arm A by >= MCID on real tasks with a saved artifact
           -> maturity: dogfooded
              maturity_evidence: benchmarks/strong-inference/run-<id>.json
           ELSE stays wired (honest); the null result goes to null_results/ with a Kill Analysis.
```

This is the point of the whole infrastructure layer: gate 10 makes it **impossible to declare
Strong Inference "proven" without the artifact**. The deep-spec is step one; the benchmark is what
earns the maturity.

---

**Related:** `hypothesis-arbiter` (runtime) · `falsification-ladder.md` (Substrate Gate, Context
Asymmetry, CDT Protocol) · `estimand-ops.md` (L0, MCID) · `experiments/_template/ach_matrix.md`
(prediction matrix form) · `skeptic` (verifier).
