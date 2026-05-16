# Examples — Combinatorial Creativity Skill

Эти примеры используются для калибровки ожидаемого качества вывода.
Агент читает этот файл перед первым запуском скила.

---

## Example 1: Scientific Hypotheses (Bioinformatics)

**User request:**
> Generate 5 hypotheses about structural penetrance of HBB variants. Use GWAS, AlphaFold, ClinVar, CRISPR screens, and population genetics as existing approaches.

**Expected behavior:**
1. Detect domain: Scientific Hypothesis Mode
2. Build matrix with the 5 approaches as rows, columns: data type / mechanism / validation method / falsifiability / confounders
3. Identify missing combinations (gap analysis)
4. Generate 3–5 hypotheses with full scientific fields
5. Score each 0–10 with rubric breakdown
6. Recommend strongest minimal experiment

**Expected matrix:**
| Approach | Data type | Mechanism | Validation | Falsifiability | Confounder |
|----------|-----------|-----------|-----------|----------------|------------|
| GWAS | Population SNPs | Association | Replication | ✅ | LD, population stratification |
| AlphaFold | 3D structure | Physical folding | Experimental validation | ✅ | Static model, no dynamics |
| ClinVar | Clinical variants | Phenotype annotation | Clinical audit | ⚠️ partial | Reporting bias |
| CRISPR screens | Functional perturbation | Direct causal | Orthogonal assay | ✅ | Off-target effects |
| Population genetics | Allele frequencies | Selection pressure | Cross-population | ✅ | Demographic history |

**Required output per hypothesis:**
```
### Hypothesis
### Mechanism
### Prediction
### Falsifiability: This would be weakened if...
### Required Data
### Minimal Experiment
### Main Confounders
### Score: X/10
### Status: TEST_NOW / REFINE_FIRST / INSUFFICIENT_DATA
```

---

## Example 2: Startup Thesis Generation

**User request:**
> Generate startup ideas in bioinformatics using these examples: 23andMe, Insitro, Recursion, AlphaFold (Isomorphic Labs).

**Expected behavior:**
1. Detect domain: Startup / Product Mode
2. Build matrix with 4 companies as rows
3. Columns: user pain / data input / value mechanism / monetization / distribution / defensibility
4. Gap analysis across all columns
5. Generate 3–5 startup theses with labels [Interpolation] / [Extrapolation] / [Recombination]
6. Score each 0–10

**Expected matrix:**
| Company | User pain | Data input | Value mechanism | Monetization | Distribution | Defensibility |
|---------|-----------|-----------|----------------|--------------|-------------|--------------|
| 23andMe | Unknown ancestry + health risk | Consumer saliva | Risk scores + ancestry | DTC + pharma data | Consumer marketing | Data moat |
| Insitro | Drug discovery too slow | ML + biology | Predict drug efficacy | Pharma partnership | B2B enterprise | Proprietary dataset |
| Recursion | Target identification | High-content imaging | Biological foundation model | Pharma licensing | B2B | Scale of data |
| Isomorphic | Protein-drug binding | Structure prediction | Molecular design | Pharma deals | B2B | AlphaFold IP |

**Gap analysis would surface:**
- No company uses real-world EHR + genomics at consumer scale → [Recombination]
- No company addresses rare disease + patient community → [Extrapolation]

---

## Example 3: Product Feature Generation

**User request:**
> Generate new features for an AI research assistant. Use these as examples: Perplexity, Elicit, ChatGPT Deep Research, Claude Projects, Semantic Scholar.

**Expected dimensions:**
- input type (query / document / structured data)
- retrieval method (semantic / citation graph / web)
- synthesis method (summarize / compare / argue)
- citation handling (inline / reference list / none)
- user workflow stage (discover / analyze / write / review)
- trust mechanism (sources shown / confidence score / none)
- collaboration mode (solo / team / public)

**Generated ideas — label examples:**
- `[Interpolation]` — fills gap between Elicit (structured) and Perplexity (web): structured + live web
- `[Recombination]` — combines Claude Projects' memory with Semantic Scholar's citation graph
- `[Extrapolation]` — extends trust mechanism beyond current range: adversarial source detection

---

## Example 4: Predictive Gate in Action

**User request:**
> Is gold currently in a bubble? Generate hypotheses about what happens to XAU next.

**Expected behavior:**
1. Detect domain: Predictive / Time-Series Gate fires
2. Check available signals before generating ideas:
   - LPPLS: available (PhaseBreak model, tc = 2026-07-06, R²=0.978)
   - HMM: check if available
   - Hurst exponent: check if computed
   - EWS (variance/autocorrelation): check if computed
3. Count independent signals:
   - < 3 → INSUFFICIENT_DATA, do not rank hypotheses
   - ≥ 3 → proceed with scores

**Gate output example:**
```
Predictive Gate check:
- LPPLS: ✅ available (tc = 2026-07-06, R²=0.978)
- HMM: ❓ not found
- Hurst exponent: ❓ not found
- EWS: ❓ not found
Independent signals confirmed: 1/3 minimum
→ Status: INSUFFICIENT_DATA
→ Cannot responsibly rank bubble hypotheses without ≥3 signals.
→ Recommendation: run Hurst + HMM on XAU data before scoring.
```

---

## Example 5: Rejection Case

**User request:**
> Just give me 20 wild ideas for my project.

**Expected response (do NOT free brainstorm):**
```
I won't generate raw ideas without structure — unstructured brainstorming 
produces decorative output that looks creative but can't be validated or ranked.

Instead, I'll build a compact matrix first:
1. What's the project domain? (product / research / startup / strategy)
2. Give me 4–6 existing examples in this space.

Then I'll generate 5 non-obvious ideas from the matrix gaps — each with a 
score and a 3-day validation test.

This takes 2 minutes more and produces ideas worth acting on.
```

---

## Calibration Checklist

Before accepting skill output as high quality, verify:
- [ ] Matrix present and complete
- [ ] Every idea has a `[label]` (Interpolation / Extrapolation / Recombination)
- [ ] Every idea traceable to specific matrix cells
- [ ] Score 0–10 with rubric (not just a number)
- [ ] Scientific ideas have Falsifiability field
- [ ] Predictive ideas went through the Gate
- [ ] Next Test is specific (3-day horizon, concrete action)
- [ ] Recommendation is direct (not "it depends")
