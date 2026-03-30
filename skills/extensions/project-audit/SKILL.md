---
name: project-audit
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-30]
  Independent 3-layer audit of any GitHub repository.
  Finds: fabrications, circular logic, mock-as-real, overclaims, dead code, contradictions.
  Also evaluates: real potential, unoccupied niches, strategic recommendations.
  Triggers: audit, проверь проект, check repo, due diligence, review project,
  is this legit, проверь на обман, аудит репозитория, evaluate project.
  USE when given a GitHub URL to analyze, or when evaluating any external codebase.
effort: max
---

# Project Audit Skill v2.0

## Overview

3-layer independent audit methodology for any GitHub repository.
Tested on scientific, SaaS, and open-source projects.

```
Layer 1: First pass    → 4 parallel agents find main issues
Layer 2: Verifier      → anti-confirmation bias, challenges Layer 1
Layer 3: Audit-of-audit → catches own hallucinations and blind spots
```

## How to Invoke

```
/audit https://github.com/user/repo.git
```

Or naturally: "проверь этот проект: <URL>" / "audit this repo: <URL>"

---

## PHASE 1: Clone & Overview (2 min)

1. Clone the repository
2. Show file structure (`ls -la`, directory tree)
3. Count commits, branches, authors (`git log --all --oneline | wc -l`, `git shortlog -sn --all`)
4. Identify tech stack

**Goal:** Understand scale and structure without making conclusions.

---

## PHASE 2: Claims vs Reality (4 parallel agents, 3-5 min)

Launch ALL 4 agents simultaneously in a single message.

### Agent 1 — README & Documentation
- What does the project CLAIM (domain, thesis, metrics, results)?
- Who are the authors? Publications, affiliations?
- What specific numbers/metrics are claimed?
- Links to publications, peer review?
- Red flags: exaggerations, impossible metrics, self-referential validation

### Agent 2 — Code & Data
- Do scripts perform REAL computation or generate hardcoded/fake results?
- Is there mock data presented as real?
- Are tests real or stubs?
- Is data genuine or synthetic?
- Are results computed or pre-written?
- Search for: hardcoded values, random generators without disclosure, pre-written conclusions

### Agent 3 — Git History
- How many real authors? (`git shortlog -sn --all`)
- Any Co-Authored-By: Claude/GPT/Copilot?
- Commit patterns: realistic or suspicious (36 commits/day, pairs < 5 min)?
- Organic history or manufactured?
- Timeline: when started, how it evolved?

### Agent 4 — External Verification
- Do links from README/manuscript resolve? Do DOIs work?
- Does the project exist on Zenodo/arXiv/bioRxiv/PyPI/npm?
- Does the author have publication history? (Google Scholar, PubMed, web search)
- Are mentioned APIs/tools real or fabricated?
- Are claimed partners/affiliations confirmed?

---

## PHASE 2.5: Cross-Verification (mandatory, after Phase 2)

Launch a separate verifier agent. It does NOT see Phase 2 results. It checks from scratch.

### Anti-Confirmation Bias
1. Take 3 most "green" conclusions from Phase 2 → try to DISPROVE them
2. Take 3 most "red" conclusions → try to find JUSTIFICATION
3. If you can't disprove/justify → conclusion is robust

### Blind Spot Checklist
- **License:** What type? Compatible with dependencies? GPL in commercial?
- **Dependencies:** Vulnerabilities? (`npm audit` / `pip-audit`)
- **Bus factor:** How many people understand the code? Author leaves = project dead?
- **Scalability:** Works on real data or only demo?
- **Reproducibility:** Can results be reproduced from scratch? (`docker build && run`)
- **Hidden costs:** Paid APIs, GPU, licenses required?
- **Data freshness:** Is data current or stale?
- **Edge cases:** What happens on empty/huge/invalid inputs?

### Cross-File Contradiction Scan
- Take 5 key numerical claims (metrics, counts, versions)
- Find each number in EVERY file where it appears (grep)
- If number differs in any place → red flag

### "What If" Tests
- What if you remove the main component — does the rest work?
- What if you feed garbage data — fails gracefully or silently lies?
- What if you run tests — do they pass? (`npm test` / `pytest`)

### Community & Ecosystem Check
- Stars/forks/issues/PRs on GitHub — is there a live community?
- Are there real bug reports from users (not from author)?
- Is the project mentioned anywhere outside the repo? (web search)
- Is there a roadmap / CHANGELOG / releases?
- Last commit date — alive or abandoned?

**Output:** List of CONFIRMED conclusions + ERRORS from first pass + NEW FINDINGS.

---

## PHASE 3: Deep Checks (5-7 min)

1. **Circular logic:** Is the result predetermined by input? Remove key component — what's left?
2. **Consistency check:** Same numbers in README, manuscript, code, configs? Contradictions?
3. **PDF vs Source:** If there's a preprint — does it match current code? Outdated/falsified claims?
4. **Self-audit:** Does the project have its own audits, falsification reports? What did they find?
5. **TODO/TONIGHT files:** Unfinished work?
6. **Config vs Claims:** Parameters in configs match documentation?
7. **Build test:** Does `tsc --noEmit` / `npm run build` / `pytest` pass?
8. **Validation results:** Read result/validation JSON files (not just code)
9. **Physical constants:** For scientific projects — compare constants with literature

---

## PHASE 4: Potential Assessment (5-7 min)

Not just criticism — find real value:

1. **Technical assets:** What actually works in the box? (engine, pipeline, UI)
2. **Competitive landscape:** What analogs exist? How is this different? (web search)
3. **Unoccupied niches:** Applications the author didn't see?
4. **Ladder strategy:** MVP in 2-4 weeks → 2-3 months → 6 months → 12 months

---

## PHASE 5: Final Report (5 tables)

### Table 1: What's REAL [VERIFIED]
| Component | Evidence |
|-----------|----------|

### Table 2: What's FALSE or CRITICAL PROBLEM
| Problem | Evidence | Severity |
|---------|----------|----------|

### Table 3: Status Map (green / yellow / red)
- **GREEN:** Proven, works, can be used
- **YELLOW:** Can be saved if reworked
- **RED:** Remove, no chance to prove

### Table 4: Potential
| Direction | Competition | Effort | Chance | Time to MVP |
|-----------|-------------|--------|--------|-------------|

### Table 5: Scores (1-10)
- Technical implementation
- Scientific/business validity
- Data integrity
- Product readiness
- Validation

### Classification
One of: **fraud** / **self-deception** / **incomplete work** / **real product**

### Recommendations
Specific actionable steps.

---

## PHASE 6: Audit of the Audit (final pass)

After writing the report, launch one more agent that reads ONLY the report and checks:

### Own Hallucinations
- Are there claims without [VERIFIED] marker? Find each → verify → mark or remove.

### Missed Positives
- Is the report too negative? Re-read "green" section — is everything good actually mentioned?

### 10 Common Blind Spots

| Blind Spot | How to Check |
|------------|-------------|
| PDF ≠ Source | Compare PDF with current code |
| Mock as Real | Grep: mock, fake, synthetic, demo, placeholder |
| Circular logic | Is there ablation? What without key component? |
| Dead features | Grep each README feature in src/ |
| License trap | Check dependency licenses |
| Stale data | Check file dates in data/ |
| Hidden API keys | Grep: API_KEY, SECRET, TOKEN in code |
| Single point of failure | `git shortlog -sn` |
| Test theater | What do tests REALLY check? |
| Vanity metrics | Issues from non-author |

### Report Consistency
- Does "green" section contradict "red"? Same thing can't be both good and bad.

### Actionability
- Is every recommendation a specific step? No "improve quality" without details.

---

## Timing

Full audit = one session. Use parallel agents maximally.

```
Phase 1 → Phase 2 (parallel) → Phase 2.5 (verifier) → Phase 3 → Phase 4 → Phase 5 → Phase 6
```

---

## Evidence Rules

1. **Evidence markers:** Every claim tagged [VERIFIED], [INFERRED], [NOT FOUND], [UNKNOWN]
2. **File:line:** Specific files and lines for each finding
3. **Don't trust docs:** README can lie. Code doesn't. Check code.
4. **Find contradictions:** Compare claims across different files
5. **Spot-check:** After 10+ facts — random verification of 3 with a tool
6. **Objectivity:** Praise what's genuinely good. Criticize what's genuinely bad.
7. **Save report:** Save to AUDIT_REPORT_{{DATE}}.md and commit

---

## Variants (add to the end of prompt)

| Goal | What to Add |
|------|-------------|
| Investment evaluation | + "Evaluate unit economics, TAM, competitive moat" |
| Hiring due diligence | + "Check if author actually wrote code, not just AI" |
| Scientific review | + "Major/Minor concerns in journal review format" |
| Acquisition | + "Technical debt, rework cost, IP risks" |
| Education | + "Didactic value: can you learn from this code?" |
| Open-source contribution | + "Worth contributing? Community, roadmap, maintainers?" |
| Security audit | + "OWASP top 10, hardcoded secrets, dependency vulnerabilities" |

---

## Proven Results

Tested on ARCHCODE (genomics simulator, 275 commits):
- **Pass 1:** 14 findings (circular AUC, fabricated FRAP, phantom references)
- **Pass 2:** 15 NEW findings (curve-fitting disguised as simulation, F1=0 loop validation, broken build)
- **3 first-pass conclusions corrected** by verifier
- **8 cross-file numerical contradictions** found
- **Total:** 29 unique findings, 240+ line report
