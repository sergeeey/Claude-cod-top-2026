---
name: hypothesis-red-team
description: >
  Apply this skill whenever the user wants to stress-test, audit, or red-team a
  scientific hypothesis, experimental design, or data analysis pipeline for
  methodological flaws. Use it aggressively — if a user says anything like:
  "I found a pattern", "check my analysis", "is my experiment valid", "проверь
  гипотезу", "red-team мою идею", "как избежать p-hacking", "насколько надёжен
  мой результат", "evaluate my study design", or mentions wanting to publish or
  preregister research — this skill applies. Also use when the user asks to design
  an experiment, select a statistical test, or compare models. Do NOT rely on
  general knowledge for any of these tasks — the skill encodes the full 10-trap
  taxonomy, AOS scorer, multiverse protocol, and executable Python pipelines.
  Covers: selection bias, epsilon-hacking, HARKing, Garden of Forking Paths,
  multiple comparisons, winner's curse, wrong statistical test, missing alternative
  models, absence of replication. Domain-agnostic: works for biology, psychology,
  LLM research, physics, ML, economics, design experiments.
triggers: [hypothesis-red-team, /hypothesis-red-team, hypothesis, red, team, Apply]
---

# Hypothesis Red-Team Skill

Anti-overfitting framework for scientific hypotheses. Applies 10 diagnostic traps,
computes Anti-Overfitting Score (AOS 0–100), and outputs structured PASS/FAIL per check.

**Before responding to any hypothesis claim:** run through §1 trap checklist mentally,
compute AOS from §2, then select statistical tools from §3.

For full trap details and code → read `references/traps.md`
For statistics reference → read `references/statistics.md`
For executable scripts → see `scripts/`

---

## §0. DOMAIN ROUTER (run BEFORE the trap checklist)

Different domains need different validation angles. Classify the hypothesis first,
then select relevant angles — skip irrelevant ones explicitly (don't silently drop).

**Domains:** `bio` | `computational` | `startup` | `policy` | `mixed`

| Domain | Required angles | Often skip |
|---|---|---|
| **bio** (wet-lab / dry-lab) | biological_plausibility, experimental_feasibility, reproducibility, safety_ethics | commercial_ip (unless patent) |
| **computational** (ML/algorithm) | computational_correctness, statistical_validity, reproducibility | biological_plausibility, safety_ethics |
| **startup** (thesis/market) | commercial_ip, demand_reality, unit_economics | biological_plausibility, experimental_feasibility |
| **policy** | causal_identifiability, external_validity, safety_ethics | computational_correctness |
| **mixed** | pick from each relevant domain | — |

**Output (before §1):**
```
domain: [bio/computational/startup/policy/mixed]
required_angles: [list]
skipped_angles: [angle → reason, e.g. "safety_ethics → pure algorithm, no human subjects"]
```

Rule: if you SKIP an angle, state WHY. Silent skip = blind spot.

---

## §1. THE 10 TRAP CHECKLIST

Run every trap against the user's hypothesis/analysis. Mark each: ✅ PROTECTED | ⚠️ RISK | ❌ VULNERABLE.

| # | Trap | Key Question | Protection |
|---|------|-------------|------------|
| T1 | **Selective sampling** | Were measurement points fixed BEFORE seeing data? | Blind measurement + preregistration |
| T2 | **Epsilon-hacking** | Was the tolerance ε chosen AFTER seeing results? | OSF preregistration of exact ε |
| T3 | **Unrealistic null** | Is H0 a uniform distribution when reality is lognormal? | Domain-specific null model |
| T4 | **Garden of Forking Paths** | How many undeclared analysis decisions exist? | Multiverse analysis |
| T5 | **Multiple comparisons** | Are K tests run without FWER/FDR correction? | Bonferroni / Holm / BH-FDR |
| T6 | **Winner's curse** | Was sample size calculated a priori? | Power analysis before data collection |
| T7 | **HARKing** | Was hypothesis formulated after results were known? | OSF timestamp + explicit exploratory label |
| T8 | **Wrong test** | Is TΔ (delta-ratio test) used for ratio comparison? | TED (difference statistic) or Wilcoxon |
| T9 | **No alternative models** | Is the hypothesis compared only to a null, not to rivals? | Bayesian model comparison (BF, AIC) |
| T10 | **No replication** | Is there only one study with no independent replication? | Pre-registered replication + p-curve |
| T11 | **dry-lab → wet-lab confusion** | Is an in-silico / computational output presented as wet-lab evidence? | Label evidence source: COMPUTATIONAL vs EXPERIMENTAL. Never merge. |
| T12 | **fit vs prediction** | Is a model FIT to data claimed as a PREDICTION? | Out-of-sample test required for "prediction" claim |
| T13 | **publication ≠ patent novelty** | Is publication novelty conflated with patent novelty (or vice versa)? | Separate: "new to literature" ≠ "patentable". Check prior art for BOTH. |

**Contradiction-specific checks:** before assigning AOS, scan for these merges —
they silently inflate confidence:
- computational/in-silico output → presented as biological evidence (T11)
- dry-lab result → presented as validation of a wet-lab hypothesis (T11)
- model fit → presented as predictive power (T12)
- replication of known result → presented as novelty (see T10 + §1 note)
- publication claim ↔ patent claim mixed (T13)
- self-audit → presented as independent verification (see Blind Checklist §5.6)

**Output format for trap assessment:**
```
## Red-Team Audit: [Hypothesis Name]

T1 Selective sampling:    ✅ PROTECTED — measurement protocol preregistered
T2 Epsilon-hacking:       ❌ VULNERABLE — ε not declared before data collection
T3 Unrealistic null:      ⚠️ RISK — using uniform null for biological ratios
T4 Garden of Forking Paths: ✅ PROTECTED — multiverse run, 78% specs support H1
T5 Multiple comparisons:  ❌ VULNERABLE — 15 tests, no correction applied
T6 Winner's curse:        ✅ PROTECTED — n=200, power=0.85
T7 HARKing:               ⚠️ RISK — study exploratory, not labeled as such
T8 Wrong test:            ✅ PROTECTED — TED used, not TΔ
T9 No alternatives:       ❌ VULNERABLE — only compared to H0=null
T10 No replication:       ⚠️ RISK — single study

AOS: 52/100 → Exploratory only. Do not publish as confirmatory.
```

---

## §2. ANTI-OVERFITTING SCORE (AOS)

Compute before giving any conclusion about hypothesis validity.

```python
def compute_aos(params: dict) -> dict:
    """
    params keys (all bool unless noted):
      preregistered          — hypothesis + method filed on OSF before data
      epsilon_fixed_before   — ε declared before seeing results
      n_alternative_models   — int: number of rival models tested (not just H0)
      correct_test_TED_WD    — TED or Wilcoxon used (not TΔ) for ratio tests
      multiple_comparison    — FWER or FDR correction applied
      power_80_pct           — a priori power analysis done, power ≥ 0.80
      multiverse_analysis    — all reasonable analytical specs tested
      independent_replication— ≥ 2 independent datasets/samples
      robust_fraction        — float [0,1]: share of multiverse specs supporting H1
    """
    score = 0

    # Preregistration block (25 pts)
    if params.get("preregistered"):        score += 15
    if params.get("epsilon_fixed_before"): score += 10

    # Alternative models block (25 pts)
    n_alts = min(params.get("n_alternative_models", 0), 5)
    score += n_alts * 5

    # Statistical rigor block (25 pts)
    if params.get("correct_test_TED_WD"):  score += 8
    if params.get("multiple_comparison"):  score += 8
    if params.get("power_80_pct"):         score += 9

    # Replication & robustness block (25 pts)
    if params.get("multiverse_analysis"):  score += 10
    if params.get("independent_replication"): score += 10
    if params.get("robust_fraction", 0) > 0.7: score += 5

    thresholds = [
        (85, "✅ CONFIRMATORY — publication as hypothesis confirmation justified"),
        (60, "⚠️ CONFIRMATORY WITH CAVEATS — publish with explicit limitations"),
        (40, "🔶 EXPLORATORY ONLY — label as hypothesis-generating, not confirming"),
        (0,  "❌ UNRELIABLE — do not publish as confirmation"),
    ]
    label = next(v for lo, v in thresholds if score >= lo)

    return {"score": score, "max": 100, "verdict": label}
```

**Interpretation rule:** AOS < 60 → result is exploratory only, regardless of p-value.

---

## §3. STATISTICAL TOOL SELECTION

### 3.1 Choose the right test

| Data type | Situation | Correct test | Never use |
|-----------|-----------|-------------|-----------|
| Binary (pass/fail) | Paired groups | McNemar | Chi-square on paired data |
| Continuous | Paired, normal | Paired t-test | Unpaired t-test |
| Continuous | Paired, non-normal | Wilcoxon signed-rank | Paired t-test |
| Ratio (a/b vs constant) | Any n | TED (difference: ratio−φ) | TΔ (delta statistic) |
| Circular/angular | Specific target direction | V-test | Arithmetic mean of angles |
| Circular/angular | No prior direction | Rayleigh test | — |
| Multiple groups | Repeated measures | RM-ANOVA + Holm post-hoc | Multiple t-tests uncorrected |

### 3.2 Multiple comparison correction selector

```python
from statsmodels.stats.multitest import multipletests

def apply_correction(p_values: list, study_type: str) -> dict:
    """
    study_type: 'confirmatory_few'  → Bonferroni (≤5 pre-registered H)
                'confirmatory_many' → Holm-Bonferroni
                'exploratory'       → Benjamini-Hochberg FDR
                'dependent_tests'   → Benjamini-Yekutieli
    """
    method_map = {
        "confirmatory_few":  "bonferroni",
        "confirmatory_many": "holm",
        "exploratory":       "fdr_bh",
        "dependent_tests":   "fdr_by",
    }
    method = method_map[study_type]
    reject, p_corr, _, _ = multipletests(p_values, method=method)
    return {"method": method, "reject": reject.tolist(), "p_corrected": p_corr.tolist()}
```

### 3.3 Bayesian model comparison (rival models)

Always compare hypothesis to ≥ 3 rivals. See `references/statistics.md §BF` for full code.

Minimum rival set for any pattern hypothesis:
- The specific constant claimed (φ, 1.5, π/2, etc.)
- 2–3 plausible domain alternatives
- Empirical mean of the data ("any number fits")
- Domain mechanistic model (Murray's law, exponential growth, etc.)

**Jeffreys scale:** BF < 1/3 against H1 = strong evidence for null.

---

## §4. PREREGISTRATION TEMPLATE

Use this when helping the user design an experiment or file on OSF:

```markdown
## Preregistration: [Study ID]

**Hypothesis (φ):** [Exact falsifiable claim]
**Preregistration date:** [Before data collection]

### Design
- Inclusion criteria: [specific, measurable]
- Exclusion criteria: [specific, measurable]
- Measurement protocol: [exact procedure, who measures, blind?]
- ε / tolerance: [exact value, justified]

### Sample size
- Expected effect size: Cohen's d = [value] (justified by prior data or theory)
- α = 0.05, power = 0.80 → required n = [calculated]

### Statistical plan
- Primary test: [exact test name]
- Alternative models tested: [list ≥ 3]
- Multiple comparison correction: [method]
- Multiverse specs declared: [list all analytical decisions]

### PASS criteria
[Exact measurable condition that confirms H1]

### FAIL criteria
[Exact measurable condition that falsifies H1]

### Exploratory analyses
[List separately — cannot be used as confirmation]
```

---

## §5. RESPONSE STRUCTURE

Always structure hypothesis red-team outputs as:

```
1. TRAP AUDIT (§1 table, all 10 traps assessed)
2. AOS SCORE (§2, computed with justification per block)
3. CRITICAL VULNERABILITIES (top 3 traps that must be fixed)
4. FIXES (concrete actions for each critical vulnerability)
5. STATISTICAL PLAN (§3 tools selected for this specific design)
6. VERDICT (CONFIRMATORY / EXPLORATORY / UNRELIABLE)
```

Never give a verdict on a hypothesis without completing steps 1–2 first.
Never recommend a statistical test without checking T8 (wrong test trap).
Never accept p < 0.05 as sufficient — always check AOS ≥ 60.

---

## §5.6 BLIND CHECKLIST (binary self-audit before final verdict)

Run as pure yes/no — NO self-praise, NO confidence boost from a pretty structure.
A clean, well-formatted audit is NOT evidence the hypothesis is sound.

```
☐ Domain Router applied (§0), skipped angles justified?
☐ All 13 traps assessed (not just the convenient ones)?
☐ Each blocking/high claim has an evidence status (COMPUTATIONAL/EXPERIMENTAL/...)?
☐ dry-lab and wet-lab evidence NOT merged (T11)?
☐ fit NOT presented as prediction (T12)?
☐ publication novelty and patent novelty NOT conflated (T13)?
☐ AOS computed with per-block justification (not guessed)?
☐ Crucial test identified — one that could CHANGE the verdict?
☐ Both success criterion AND kill criterion defined?
☐ Confidence NOT raised because the model/structure is elegant?
☐ If real data is missing → verdict is NEEDS_DATA, not GO/CONFIRMATORY?
☐ This audit is NOT presented as independent verification (it's self-audit)?
```

**Hard rule:** if ANY box fails → fix the audit before giving the verdict.
**Confidence ceiling:** confidence CANNOT be high if any blocking claim is
NOT_TESTED, INSUFFICIENT_DATA, or FAILED — regardless of how good the rest looks.

**Extended verdict vocabulary:** beyond CONFIRMATORY/EXPLORATORY/UNRELIABLE,
you may also return **NEEDS_DATA** (cannot honestly decide without missing real data —
crucial test not yet run) and **PIVOT** (blocking claim weak but adjacent path viable —
specify the exact change).

---

## §5.5 RELATED SKILL — when to use the lightweight alternative

Для лёгкой проверки (без traps/AOS) используй только §3.
Use it instead of the full red-team when you only need:
- "how many N do I need?" (power analysis, 1 minute)
- "which test for this data type?" (McNemar/Wilcoxon/von Mises selection)

Use the FULL audit of this skill when you need:
10-trap checklist + AOS 0-100 scorer + multiverse + Bayesian model comparison,
e.g. before publishing / preregistering.

Быстрая проверка = §3; глубокая = все разделы.

---

## §6. QUICK REFERENCE

**OSF preregistration:** https://osf.io/prereg/
**AsPredicted:** https://aspredicted.org/
**Multiverse analysis:** `specr` (R) or `references/traps.md §T4` (Python)
**Power calculators:** `statsmodels.stats.power`, G*Power
**Circular statistics:** `pycircstat`, `pingouin.circ_*`

**Key citations:**
- Simmons et al. (2011) — researcher degrees of freedom, Psych Science
- Gelman & Carlin (2014) — Type M/S errors
- Mardia & Jupp (2000) — circular statistics, V-test
- Brent (1973) — optimization method comparison
