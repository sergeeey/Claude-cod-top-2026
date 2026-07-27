# Strong Inference — Full Reference Contract

> This is the **reasoning/rationale layer** behind `hypothesis-arbiter`'s SKILL.md protocol.
> SKILL.md is what to DO at runtime; this document is WHY it works and HOW it breaks. Read this
> when: disputing whether the method was applied correctly, designing a benchmark to test it,
> onboarding someone to the method, or diagnosing a failure mode not obvious from the runtime steps.

---

## 1. Identity & provenance

| field | value |
|---|---|
| mechanism | competing mechanistically-distinct hypotheses + a discriminating (crucial) test |
| primary sources | Platt, J. R. (1964). "Strong Inference." *Science* 146(3642): 347–353. Chamberlin, T. C. (1890). "The Method of Multiple Working Hypotheses." *Science* (old series) 15(366): 92–96; reprinted 1965, *Science* 148: 754–759. |

**Adaptation for an LLM-agent context:** Platt's Strong Inference is a procedure for a human
scientist. Deployed as an agent skill, the failure modes differ — a single model can generate
"competing" hypotheses that quietly share a hidden assumption, and the same context that generated
a hypothesis is a biased judge of its survival. The core predicate is unchanged: **a test that
cannot exclude at least one live hypothesis is not a strong test.**

---

## 2. What it estimates (question type)

Strong Inference answers **causal / mechanism** questions — "which of these mechanisms produced
the observation?" It is not a descriptive summarizer or a predictive model. If the real question is
"what is X" (descriptive) or "what will X be" (predictive), this method is the wrong tool.

---

## 3. Oracle design (the load-bearing part)

A method is never better than its evaluator.

```yaml
target_construct: "which mechanism actually produced the observation"
observable_proxy: "the crucial test's measurable outcome"
gameability: "an agent can propose a test whose result it already knows -> not discriminating"
positive_control: "a case with a KNOWN mechanism -> the method must recover it"
negative_control: "a case where NO mechanism among the candidates is correct -> the method must
                   report 'none survive', not force a winner"
independence: "hypothesis quality must NOT be scored by the same agent/context that generated
               them (single-agent confirmation bias) -> delegate to skeptic with context asymmetry"
```

**Hard rule:** the crucial test's oracle must be external to the hypotheses. If the test's result
is knowable from the hypotheses alone (no new observation), the test is circular — discard it.

---

## 4. Pre-registered outcome map (why it must come before the test)

Writing "if result A then H2 dies, if result B then H1 dies" **after** seeing the result is
indistinguishable from making up a story to fit whatever happened. Pre-registration is the only
thing that turns a test from "explains the data" into "predicted the data." This is the single
biggest lever against post-hoc rationalization in the whole protocol.

**Infrastructure failure is not evidence.** If the test could not run honestly (data unavailable,
tool broken, the checking apparatus itself distorted the result), that is a fact about the
substrate, not about any hypothesis. Recording it as a kill is a category error that silently
corrupts every downstream confidence score.

---

## 5. Duhem–Quine limitation (mandatory qualifier)

A crucial test never refutes a single hypothesis in isolation. It refutes the conjunction
`H ∧ (measurement apparatus) ∧ (preprocessing) ∧ (auxiliary assumptions) ∧ (statistical model)`.
Therefore every kill verdict is phrased:

> "H1 is **incompatible with** result R **under** assumptions A1–An and verified substrate S1."

Never bare "H1 is refuted." The difference is what lets a later cycle rescue H1 by challenging an
auxiliary assumption instead of the mechanism — without that qualifier, a correct hypothesis killed
by a bad auxiliary assumption is lost permanently instead of being revivable.

---

## 6. Failure modes (adversarial — what breaks this method)

| failure | detection | guard |
|---|---|---|
| **correlated candidates** — the "competing" H all share a hidden assumption (classic single-model trap) | do any two H die to the SAME test for the SAME reason? | force each H to name a *different* causal pathway; generate from different framings or a second model |
| **fake crucial experiment** — the test doesn't actually discriminate | does every outcome branch kill ≥1 H? | outcome-map completeness check |
| **weak/strawman H₀** | is H₀ falsifiable and plausible, not a strawman? | explicit H₀ requirement |
| **candidate padding** — many H, but only 2 are mechanistically real | prune to the mechanistically-distinct set | max one candidate per mechanism-family |
| **missing true hypothesis** — the correct mechanism isn't in the candidate set at all | negative control: if none survive, was the set incomplete? | report "none survive"; regenerate from a different angle, don't force a winner |
| **result-first outcome map** — map written after seeing the result | is the outcome map dated/recorded before the test ran? | pre-registration discipline (§4) |

---

## 7. Composition with other methods

```yaml
prerequisites: [claim-decomposer]           # atomize the observation into checkable atoms first
combines_well_with: [estimand-bridge, ach_matrix.md (sibling reference), pre-mortem]
alternatives: [sci-hypothesis]              # single-hypothesis case, no competition needed
conflicts_with: [free-form brainstorming after an outcome map is already pre-registered]
required_after: [skeptic]                   # independent falsification of the surviving hypothesis
```

---

## 8. Benchmark methodology (how to actually test whether this method beats a plain guess)

**Question a benchmark must answer:** does following this protocol produce measurably better
mechanism identification than a single-guess baseline, at acceptable cost? A deep-spec on paper
does not prove this — it only makes the claim precise enough to test.

**Design (lexicographic, not a single blended score):**
- **Population:** a task set with a KNOWN correct mechanism per task (so correctness is checkable),
  including at least one negative-control task (the "anomaly" is actually noise) and one task whose
  true mechanism sits outside an obvious candidate set (tests "missing true hypothesis").
- **Arms:** plain single-answer baseline vs. this protocol followed strictly.
- **Primary metric (absolute, not a ratio):** mechanism-identification accuracy against the known
  ground truth. Define a minimum practically important difference (MCID) BEFORE running — e.g.
  "the rigorous arm must beat baseline by at least N tasks out of the set to justify the overhead."
- **Oracle:** a grader blind to which arm produced which answer, and never one of the arms itself.
- **Sensitivity check:** re-run with candidate order shuffled (guards against order effects biasing
  which hypothesis gets picked).

**What a benchmark does NOT prove, even if it wins:** it does not prove the method helps on
*descriptive* tasks (wrong estimand class for this method); it does not generalize past the tested
task family; a tie or a loss is a real, honest result — not a reason to keep re-tuning until it
wins (that crosses into the overfitting a real evaluation is supposed to prevent).

---

## 9. Maturity discipline (do not skip this when reporting results)

A method's demonstrated track record and its theoretical elegance are different claims. Keep them
separate: "this protocol is well-specified and has clear failure modes" is not the same claim as
"this protocol has been shown to outperform simpler alternatives on real tasks." Only make the
second claim after an actual benchmark run produced and saved a real artifact — never from the
existence of this document alone.

---

**Related (global rules, available in any project):** `falsification-ladder.md` (Substrate Gate,
Context Asymmetry, Cheapest Differentiating Test Protocol) · `estimand-ops.md` (L0 question
classification, MCID) · sibling reference `ach_matrix.md` (prediction-matrix template) · `skeptic`
skill (verifier, invoke with context asymmetry).
