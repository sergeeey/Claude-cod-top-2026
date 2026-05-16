---
name: combinatorial-creativity
sub_type: pipeline
version: "1.2"
last_tested: "2026-05-14"
context: fork
effort: medium
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-05-13]
  Матричная генерация идей: научные гипотезы, стартап-тезисы, направления исследований,
  продуктовые фичи, стратегические варианты. Запрет на свободный брейнсторминг — только
  матрица → пробелы → идеи. Рубрика оценки 0–10. Ворота фальсифицируемости для науки.
  Триггеры: сгенерируй идеи, гипотезы, направления исследований, стартап-тезис,
  новые фичи, чего нам не хватает, сгенерируй варианты, generate ideas, hypotheses.
  НЕ для: прямых фактических вопросов, поиска информации, code review.
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : combinatorial-creativity
TL;DR  : Матричная генерация идей: матрица → пробелы → гипотезы → Score 0-10. Без матрицы = нет идей.
Вызов  : /combinatorial-creativity, generate ideas, hypotheses, what are we missing, startup thesis
НЕ для : Прямые фактические ответы, поиск информации, code review
-->

# Skill: Matrix Combinatorial Creativity

## Before First Use
Read `.claude/skills/combinatorial-creativity/examples.md` to calibrate expected output quality.

## Purpose
Generate non-trivial, testable ideas by decomposing existing examples into comparable dimensions,
identifying missing values, and recombining patterns.

Core principle:
> Proven patterns + new values + explicit validation = useful creative possibilities.

**Hard rule:** Do not brainstorm freely. Every idea must be traceable to a matrix, a pattern,
and a novelty mechanism. No matrix → no ideas.

---

## When to Use
Apply this skill when the user asks for:
- new ideas, hypotheses, research directions
- startup concepts or product features
- experimental designs or strategic options
- "what are we missing?" analysis
- "generate N variants" requests
- novel combinations from existing examples

If the user asks a direct factual question → do not use this skill.

---

## Domain Detection (Step 0 — before everything else)

Before running the algorithm, detect the domain:

| Domain signals | Mode | Extra gate |
|---------------|------|-----------|
| scientific, biology, genomics, hypothesis, experiment | Scientific Hypothesis Mode | Falsifiability required |
| startup, product, market, monetize, users | Startup / Product Mode | Pain + Defensibility required |
| prediction, market, bubble, crash, time series, regime | Predictive Gate | ≥3 signals required |
| any other | Standard Mode | Score + Next Test required |

State the detected mode before Step 1.
If Predictive Gate fires → apply it **before Step 5** (before generating ideas).

---

## Algorithm

### Step 1 — Define the Category
Identify the object being generated.

Examples:
- scientific hypothesis
- bioinformatics workflow
- product feature
- startup thesis
- research experiment
- strategy
- diagnostic method
- AI agent workflow

If ambiguous → choose the safest useful interpretation and state it briefly.

---

### Step 2 — Select Existing Examples
Choose or ask for 4–7 existing examples. Examples become matrix rows.

If examples are provided by the user → use them.
If missing → infer reasonable examples and mark as assumptions:

```
Assumption: I will use the following existing examples as matrix rows: ...
```

**Do not generate ideas until examples exist.**

---

### Step 3 — Define Comparable Dimensions
Create 3–7 matrix columns. Each column must represent a **comparable dimension**, not a decorative label.

**Good columns:**
- data type, mechanism, validation method
- unit of analysis, model class
- monetization model, evidence level
- scalability, falsifiability
- minimal experiment, confounders

**Bad columns (forbidden):**
- "coolness", "vibe", "innovative", "hardcore"
- arbitrary adjectives without a scale
- tone: noir / absurd / strict / wild

If a column contains incomparable labels → normalize into a scale or relation:
```
Bad:  Tone: noir / absurd / strict
Good: Tone realism: low / medium / high
```

**Measurability Validator (apply before building matrix):**

Check each column against the novelty mechanism it will support:

| Column type | [Interpolation] | [Extrapolation] | [Recombination] |
|-------------|----------------|----------------|----------------|
| Numeric scale (0–100, low/med/high) | ✅ Valid | ✅ Valid | ✅ Valid |
| Categorical (types, names, classes) | ❌ Invalid | ❌ Invalid | ✅ Valid |
| Boolean (yes/no) | ❌ Invalid | ❌ Invalid | ✅ Valid |

**Rule:** If you plan to generate an [Interpolation] or [Extrapolation] idea from a column → that column MUST have a numeric or ordinal scale. Categorical column + [Interpolation] claim = logical contradiction → reject and reframe.

```
Bad:  Core Mechanism: "Radio stabilization" / "Anderson localization"  → cannot interpolate
Good: Degree of determinism: 0=fully stochastic, 100=fully deterministic  → interpolatable
```

Always add a **Data Availability** column to the matrix:
```
Data Availability: 0 = data does not exist / 100 = already in hand
```
Ideas where Data Availability = 0 across all validation steps → classify as DEFER, not TEST_NOW.

---

### Step 4 — Build the Matrix
Always output a markdown table **before** generating ideas.

**Standard minimum:**
| Example | Dimension 1 | Dimension 2 | Dimension 3 | Data Availability (0–100) | Evidence / Validation |
|---------|------------|------------|------------|--------------------------|----------------------|

**Scientific hypothesis mode — required columns:**
| Example | Core mechanism | Degree of determinism (0–100) | Data source | Validation method | Data Availability (0–100) | Falsifiability | Major confounder |

**Startup / Product mode — required columns:**
| Example | User pain | Data/input | Value mechanism | Monetization | Distribution | Defensibility | Data Availability (0–100) |

---

### Step 5 — Identify Gaps

After the matrix, analyze each column using three novelty mechanisms:

**Interpolation** — a missing value between existing known values
**Extrapolation** — a value beyond the current range
**Recombination** — a new combination of existing values across rows

Output format:
```
## Gap Analysis
- Dimension A:
  - Existing range: [X → Y]
  - Missing intermediate values: [Z]
  - Possible extreme values: [W]
- Dimension B:
  - Existing range: [...]
  - Missing combinations: [...]
```

---

### Step 5.5 — Prior Art Gate (Scientific mode only)
**Apply before generating ideas when domain = scientific.**
**This is a mandatory blocking step — Step 6 cannot start until Step 5.5 output is present.**

For each candidate idea from gap analysis, run a prior art check:

**Search protocol (in order):**
1. **If WebSearch is available** → execute a real arXiv / Google Scholar search before writing output.
   Tag result: `[PRIOR ART: SEARCHED]`
2. **If WebSearch is NOT available** → use training knowledge, but mark explicitly:
   `[PRIOR ART: FROM TRAINING DATA — not verified by real search]`
   Do NOT simulate search confidence. `[UNKNOWN] > false [INFERRED]`.

```
Prior Art Check per idea:
- Mechanism name → search arXiv / Google Scholar
- Year of first appearance: [UNKNOWN if not found]
- If mechanism pre-dates 2015 → Novelty score capped at 1/2
- If mechanism is well-established (textbook) → Novelty score capped at 0/2
- Keywords to search: ["mechanism name" + "key domain terms"]
```

**Novelty Deflation Rule:**
- Pre-2015 mechanism known in literature → Novelty ≤ 1 (not 2) → tag: `[KNOWN]`
- Textbook result (e.g., Anderson 1958, Hurst 1951) → Novelty = 0 → tag: `[CLASSIC]`
- Genuinely unexplored combination → Novelty = 2 ✅ → tag: `[NOVEL]`

**If prior art is UNKNOWN:** mark `[PRIOR ART: NOT CHECKED]` explicitly.
Do NOT assume novelty without evidence. `[UNKNOWN] > false [INFERRED]`.

**Required output format (must appear before Step 6):**
```
## 5.5 Prior Art Check
- Idea 1: [mechanism X] → first described [year/UNKNOWN] → [NOVEL/KNOWN/CLASSIC] → Novelty cap: [N/2]
  arXiv query: ["mechanism keywords"]
- Idea 2: [mechanism Y] → [PRIOR ART: NOT CHECKED] → Novelty = UNKNOWN
  arXiv query: ["mechanism keywords"]
```

**If this block is absent → Step 6 output is incomplete. Do not skip.**

---

### Step 6 — Generate New Variants
Generate 3–5 ideas (unless user requested a different number).

Each idea must include:
- `[Interpolation]`, `[Extrapolation]`, or `[Recombination]` label **in the idea heading** — not in a footnote, not in a summary. Missing label = incomplete step.
- short name
- core idea
- matrix origin (which cells it combines)
- why it is non-obvious
- validation path
- score 0–10

**Label enforcement rule:**
```
### Idea 1 — [Recombination] Clinical Trial Fraud Early-Warning   ← label MUST be here
```
Not acceptable:
```
### Idea 1 — Clinical Trial Fraud Early-Warning   ← label missing → step incomplete
```

**Do not output ideas that cannot be traced back to the matrix.**

**Column–mechanism consistency check (before writing each idea):**
- If label = [Interpolation] → confirm the source column has a numeric/ordinal scale
- If label = [Recombination] → confirm ≥2 different matrix rows contributed
- If label = [Extrapolation] → confirm the value is beyond the observed range, not just a different category

---

## Scoring Rubric (0–10, all ideas)

| Criterion | Weight | Meaning |
|-----------|--------|---------|
| Novelty | 2 | Meaningfully different from existing examples? |
| Plausibility | 2 | Fits known constraints and mechanisms? |
| Testability | 2 | Can it be validated or falsified? |
| Leverage | 2 | Could produce strategic or scientific value if true? |
| Cost-efficiency | 1 | Can it be tested without excessive resources? |
| Robustness | 1 | Resilient to obvious confounders or failure modes? |

**Score interpretation:**
- 9–10 → unusually strong; worth prioritizing
- 7–8 → promising; worth testing
- 5–6 → interesting but needs refinement
- 3–4 → weak or too speculative
- 0–2 → discard

> **Scientific note:** Score 9–10 = candidate for minimal experiment.
> Do NOT submit or publish based on matrix score alone — requires real data validation.

**Novelty Deflation Guard (automatic):**
- Mechanism known pre-2015 in literature → Novelty score capped at 1/2
- Textbook/classic result → Novelty score capped at 0/2
- Combined score above 8 with Novelty=0 → impossible; cap total at 8

---

## Scientific Hypothesis Mode

When generating scientific hypotheses, add these fields to **every** idea:

```
### Hypothesis
### Mechanism
### Prediction
### Falsifiability
This hypothesis would be weakened or rejected if...
### Required Data
### Minimal Experiment
### Main Confounders
### Score: X/10
```

**Rules:**
- A hypothesis without falsifiability is **not acceptable** → reject it
- A hypothesis without a minimal experiment is **incomplete**
- If evidence is insufficient → say `INSUFFICIENT_DATA`, not `POSSIBLE`
- Prefer small validation loops over grand speculative claims
- High score ≠ evidence; score is plausibility, not confirmation

---

## High-Risk Research Mode

For uncertain or high-stakes research, classify each idea:

| Status | Meaning |
|--------|---------|
| `TEST_NOW` | Cheap, clear, falsifiable test exists |
| `REFINE_FIRST` | Promising but requires sharper formulation |
| `INSUFFICIENT_DATA` | Too little evidence to responsibly rank |
| `DEFER` | Interesting but too costly or speculative |
| `DISCARD` | Weak, redundant, or not testable |

Do not overstate confidence. `INSUFFICIENT_DATA` > false `POSSIBLE`.

---

## Predictive / Time-Series Gate

**Apply only if** the idea involves: prediction, markets, time series, bubbles, crashes,
early-warning signals, or regime shifts.

**Do not apply** to bioinformatics, product features, or conceptual tasks.

Check whether the idea can be evaluated using at least **3** of these independently:
- LPPLS / DS-LPPLS
- HMM / regime detection
- Hurst exponent
- MFDFA
- Early-warning signals (variance, autocorrelation)
- Out-of-sample validation

**Signal rule:**
```
< 3 independent signals available → classify as INSUFFICIENT_DATA
≥ 3 signals available → proceed with score
```

---

## Output Format

```
## 0. Domain Detected: [mode]

## 1. Category

## 2. Existing Examples + Assumptions

## 3. Matrix
| Example | ... |

## 4. Pattern Analysis

## 5. Gap Analysis

## 5.5 Prior Art Check (scientific mode)
- Idea 1: [mechanism] → [year/UNKNOWN] → Novelty cap: [N]
- ...

## 6. Generated Ideas (TEST_NOW + REFINE_FIRST only)

**DEFER and DISCARD ideas are moved to Appendix — not shown here.**

### Idea 1 — [Interpolation / Recombination / Extrapolation]
- Core idea:
- Matrix origin: [row X col A] × [row Y col B]
- Why non-obvious:
- Prior art: [checked / NOT CHECKED]
- Validation:
- Main risk:
- Score: X/10 (Novelty: N/2 after deflation check)
- Status: TEST_NOW or REFINE_FIRST only

## 7. Recommendation
→ Strongest idea and why.
→ Prior art check needed before coding? [YES/NO]

## 8. Next Test (3-day horizon)
→ Concrete action to validate the top idea.
→ arXiv search query to verify novelty: ["mechanism keywords"]

## Appendix: Filtered Ideas
### DEFER ideas (too costly/speculative now)
[listed briefly, no full breakdown]

### DISCARD ideas (weak/redundant)
[listed briefly with one-line reason]
```

---

## Quality Rules

**Never:**
- generate ideas without a matrix
- use vague dimensions without normalization
- present decorative creativity as strategic insight
- claim scientific validity without a validation path
- confuse plausibility with evidence
- apply Predictive Gate to non-prediction tasks
- produce more ideas when fewer stronger ideas are better
- use a categorical column as source for [Interpolation] or [Extrapolation]
- skip Step 5.5 Prior Art block — its absence makes Step 6 output incomplete
- write an idea heading without `[Interpolation]` / `[Extrapolation]` / `[Recombination]` label
- classify an idea as TEST_NOW when Data Availability = 0

**Always:**
- make assumptions explicit
- separate facts from hypotheses
- prefer falsifiable ideas
- include a score with rubric breakdown
- include a next test
- identify confounders for scientific work
- recommend the strongest option and explain why

---

## Gotchas

- Matrix = mandatory. If user resists → explain why free brainstorming produces decorative output
- "User Context" does not belong here — keep in CLAUDE.md per project
- Score 9–10 on a matrix ≠ evidence. Score is plausibility assessment only
- Predictive Gate fires on domain keywords, not user intent — verify before applying
