# Evidence Markers — Canonical Reference

## Purpose
Single source of truth for all evidence markers. Supersedes partial lists in integrity.md, audit-verification-gate.md, and rationalizations.md. When in doubt, check here.

## Core Markers (from integrity.md)

| Marker | Meaning | Confidence cap |
|--------|---------|----------------|
| `[VERIFIED]` | Confirmed with a tool: Read, Bash, pytest output | HIGH if ≥2 sources |
| `[DOCS]` | From official documentation | MEDIUM (docs may lag code) |
| `[CODE]` | From project source code | HIGH |
| `[MEMORY]` | From prior experience / training data | LOW (re-verify before acting) |
| `[INFERRED]` | Logical conclusion from verified facts — state the chain | MEDIUM |
| `[WEAK]` | Indirect data, analogy, single source | LOW |
| `[CONFLICTING]` | Sources contradict — list both | n/a |
| `[UNKNOWN]` | No confirmation — explicitly say "verification required" | n/a |

## Validation Markers (from audit-verification-gate.md)

| Marker | Meaning | When to use |
|--------|---------|-------------|
| `[VERIFIED-REAL]` | Tested on real-world data, sources cited (URLs, file paths, dataset names) | Hypothesis validation claims |
| `[VERIFIED-SYNTHETIC]` | Tested on synthetic/mock data — valid for unit tests, NOT for hypothesis validation | Unit tests only |
| `[VERIFIED-INLINE]` | Quick sanity check via embedded data — low confidence | Internal sanity checks |
| `[NEEDS-REAL-DATA]` | Claim plausible but not yet tested on real data | Pending validation |

## Tool-Specific Verification Markers (from audit-verification-gate.md)

| Marker | Confirmed by |
|--------|-------------|
| `[VERIFIED-pytest]` | pytest run output |
| `[VERIFIED-grep]` | grep/Grep search result |
| `[VERIFIED-bash]` | Bash command output |
| `[VERIFIED-read]` | File Read tool result |

## Confidence Scoring

| Level | Threshold | Condition |
|-------|-----------|-----------|
| HIGH | ≥0.80 | ≥2 independent sources confirm |
| MEDIUM | 0.60–0.79 | 1 source + logical inference |
| LOW | 0.40–0.59 | Indirect data or single source |
| SPECULATIVE | <0.40 | Conjecture — do not use in decisions |

**Hard cap:** `[MEMORY]` alone → max LOW. Fewer than 2 sources → max MEDIUM.

**For literature/evidence synthesis specifically** (not single-fact verification): source-count is
a coarse proxy. When grading the certainty of a body of evidence rather than one claim, **GRADE**
(Grading of Recommendations Assessment, Development and Evaluation — the standard used by Cochrane
and WHO) rates down for 5 *named* reasons instead of just counting sources: risk of bias,
inconsistency (results disagree across sources), indirectness (the evidence answers a different
question than the one asked), imprecision (wide confidence intervals), and publication bias. Citing
"indirectness" or "inconsistency" as the specific reason a synthesis is LOW is more actionable than
"only 1 source" — use GRADE's 5 domains as the reasoning, this table's levels as the label.

## Usage Rules

1. Mark: numbers, versions, URLs, config options, security recommendations.
2. `[UNKNOWN]` is always better than a false `[INFERRED]`.
3. Sub-agent `[VERIFIED]` = your `[INFERRED]`. Re-verify with a tool before escalating.
4. Validation claims MUST carry `[VERIFIED-REAL]`. `[VERIFIED-SYNTHETIC]` only valid for unit tests.

## Related Files
- `rules/integrity.md` — full anti-hallucination protocol
- `rules/audit-verification-gate.md` — agent report verification gate
- `rules/rationalizations.md` — common excuses and counters
