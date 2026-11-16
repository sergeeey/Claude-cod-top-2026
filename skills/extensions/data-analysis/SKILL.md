---
name: data-analysis
description: Generate statistical analysis code with 4-round review. Select appropriate statistical tests, interpret results, and produce analysis reports with p-values, effect sizes, and confidence intervals. Use when analyzing experimental data for a paper.
argument-hint: [data-source]
triggers: ["/data-analysis", "statistical analysis code", "analyzing experimental data", "statistical tests", "data without hypothesis", "hidden patterns in data", "скрытые закономерности", "данные без гипотезы"]
---

# Data Analysis

Generate rigorous statistical analysis code with multi-round review.

## Input

- `$0` — Data source (CSV, JSON, pickle, or experiment logs)
- `$1` — Research goal or hypothesis to test

## References

- 4-round code review prompts: `~/.claude/skills/data-analysis/references/review-prompts.md`

## Scripts

### Statistical summary and comparison
```bash
python ~/.claude/skills/data-analysis/scripts/stat_summary.py --input results.csv --compare method --metric accuracy --output summary.json
python ~/.claude/skills/data-analysis/scripts/stat_summary.py --input results.csv --describe
```

Detects data types, recommends tests, runs comparisons, outputs effect sizes and significance stars. Requires numpy, scipy.

### Format p-values
```bash
python ~/.claude/skills/data-analysis/scripts/format_pvalue.py --values "0.001 0.05 0.23" --format stars
python ~/.claude/skills/data-analysis/scripts/format_pvalue.py --csv results.csv --column pvalue --format latex
```

Formats p-values with stars, LaTeX notation, or plain text. Stdlib-only.

## Workflow

### Step 1: Generate Analysis Code
Structure the code with these sections:
1. `# IMPORT` — pandas, numpy, scipy, statsmodels, sklearn
2. `# LOAD DATA` — Load from original data files
3. `# DATASET PREPARATIONS` — Missing values, units, exclusion criteria
4. `# DESCRIPTIVE STATISTICS` — Summary tables if needed
5. `# PREPROCESSING` — Dummy variables, normalization
6. `# ANALYSIS` — Statistical tests per hypothesis
7. `# SAVE ADDITIONAL RESULTS` — Extra results to pickle

### Step 2: 4-Round Code Review
1. **Round 1 — Code Flaws**: Mathematical/statistical errors, wrong calculations, trivial tests
2. **Round 2 — Data Handling**: Missing values, units, preprocessing, test choice
3. **Round 3 — Per-Table**: Sensible values, measures of uncertainty, missing data
4. **Round 4 — Cross-Table**: Completeness, consistency, missing variables

### Step 3: Produce Results
- Every nominal value must have uncertainty (CI, STD, or p-value)
- Statistical tests must be appropriate for the data type
- Results must match actual data — never hallucinate

## Allowed Packages

`pandas`, `numpy`, `scipy`, `statsmodels`, `sklearn`, `pickle`

## Statistical Test Selection

| Data Type | Test |
|-----------|------|
| Two groups, normal | Independent t-test |
| Two groups, non-normal | Mann-Whitney U |
| Paired samples | Paired t-test / Wilcoxon |
| Multiple groups | ANOVA / Kruskal-Wallis |
| Categorical | Chi-square / Fisher's exact |
| Correlation | Pearson / Spearman |
| Regression | OLS / Logistic / Mixed effects |

## Rules

- Always report p-values for statistical tests
- Account for relevant confounding variables
- Use inherent package functionality (e.g., `formula = "y ~ a * b"` for interactions)
- Do not manually implement available statistical functions
- Access dataframes using string-based column names, not integer indices

## Exploratory discovery (no hypothesis yet)

Use when the user brings data and asks "what is interesting here" instead of a hypothesis.
Every step happens in this order; skipping the freeze makes the result exploratory-only.

1. **Freeze before search.** Split off a confirmation set BEFORE looking at the data.
   Independent rows: random split. Time series: chronological split with a gap (purge/embargo)
   at least as long as the longest window or lag. Grouped data (device, subject, region):
   split by group. No honest split possible -> status `EXPLORATORY_CANDIDATE` at best.
2. **Write the search scope down.** Method families, number of variants, correction for
   multiplicity (BH FDR inside the search; Bonferroni over the selected set at confirmation),
   stop rule. A p-value sweep is not a complete search; say how many tests were run.
3. **Baseline and control.** Compare each candidate with a simple baseline (constant, linear,
   seasonal naive). Run a shuffled-label/permutation control: the effect must vanish there.
   Plain shuffling is invalid for autocorrelated or grouped data: use first differences,
   block permutation, or within-group checks instead. If a pooled association disappears
   within groups or after differencing, the status is `ARTIFACT` for that association.
4. **Confirm once.** Test the frozen prediction on the confirmation set one time. Reusing it to
   pick among candidates turns it into search data and requires a new set.
5. **Report with a status per claim** (one status for each pair or effect you name; a leaked
   column is excluded and reported separately), one of: `NO_SIGNAL`, `EXPLORATORY_CANDIDATE`,
   `REPLICATED_ASSOCIATION`, `PREDICTIVE_SUPPORTED`, `MECHANISM_CANDIDATE`, `INCONCLUSIVE`,
   `ARTIFACT`, `BLOCKED`. Never `SCIENTIFIC_DISCOVERY` automatically: a replicated
   association is not causality and not novelty. Keep null results in the report.

Delegate, do not duplicate: leakage and measurement validity -> `boyko-construct-measurement-gate`;
anomalies and orphan data -> `narrow-discovery-engines`; questions before analysis -> `boyko-qze`;
attacking a finished claim -> `hypothesis-red-team`.

## Related Skills
- Upstream: [experiment-code](../experiment-code/), [experiment-design](../experiment-design/)
- Downstream: [table-generation](../table-generation/), [figure-generation](../figure-generation/), [backward-traceability](../backward-traceability/)
