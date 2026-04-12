---
name: scientific-research
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-12]
  Research project methodology: baseline-first, falsification gates, red team,
  kill criteria. Prevents 6-month sunk cost traps (ARCHCODE pattern).
  MUST USE when: ML experiment, scientific hypothesis, data analysis, model
  building, publication pipeline, any project with AUC/metrics/p-values.
  Triggers: research, hypothesis, model, AUC, baseline, experiment, paper,
  publication, dataset, ml, scientific, falsification, confound.
effort: max
tokens: ~400
---

# Scientific Research Methodology

## The Core Problem

AI assistants amplify confirmation bias. They build, validate, and scale
what you give them — but rarely say "stop, test the null hypothesis first."
This skill enforces the checks that prevent wasted months.

> ARCHCODE lesson: 6 months building 3D chromatin physics. Day-1 baseline
> (category → score) gave AUC=0.98. Physics added ~0.02. All scaling was
> built on a foundation that failed the simplest check.

---

## Day 1 Checklist (non-negotiable)

### 1. baseline.py — write it first, before anything else

```python
# 20 lines max. Trivial model. Run BEFORE building anything complex.
from sklearn.dummy import DummyClassifier
from sklearn.metrics import roc_auc_score

clf = DummyClassifier(strategy="most_frequent")
clf.fit(X_train, y_train)
auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])
print(f"Baseline AUC: {auc:.4f}")

# KILL CRITERION: if baseline AUC > 0.90 → your complex model
# must solve a DIFFERENT question, not the same one slightly better.
```

Record result in README immediately. This is your reference point forever.

### 2. KILL_CRITERIA.md — write before starting

```markdown
# Kill Criteria — [Project Name]

## Stop conditions (with dates)
- [ ] Week 1: If baseline AUC > 0.90 → reformulate hypothesis
- [ ] Week 2: If within-category AUC < 0.60 → claimed mechanism doesn't work
- [ ] Month 1: If unique claim not validated on subset → no unique claim exists
- [ ] Month 2: If no publication venue confirmed → start affiliation process NOW

## Gate review before scaling
- [ ] Baseline beaten on held-out subset?
- [ ] Within-category test passed?
- [ ] Unique claim tested (not just overall metric)?
If ANY = No → deepen, do NOT scale.
```

### 3. publication_target.md — week 1

```markdown
# Publication Target

## Primary venue: [journal/preprint]
- Requirements: [affiliation? endorsement? format?]
- Timeline: [submission deadline]

## Affiliation status
- [ ] Have institutional affiliation
- [ ] Applied to Ronin/IGDORE (60-day process — start NOW if needed)
- [ ] Have arXiv endorser
- [ ] Fallback: Zenodo DOI (no affiliation required)
```

---

## AUC Red Flags

| Range | Interpretation | Action |
|-------|---------------|--------|
| 0.50–0.65 | Weak signal | Check data quality |
| 0.65–0.85 | Realistic for biomedical | Proceed with caution |
| 0.85–0.95 | Good — verify no leakage | Run confound check |
| **0.95+** | **Almost certainly confound** | **STOP. Find the confounder first.** |
| 1.00 | Data leakage | Do not proceed |

---

## Falsification Protocol

### After every milestone (AUC result / draft ready / metric looks good):

**Step 1 — Trivial explanation test**
Before celebrating: can the simplest possible model explain this?
```python
# Test: does removing your claimed mechanism change anything?
# "Without physics → AUC=?" not "Without category → AUC=?"
# The correct ablation removes YOUR contribution, not the confounder.
```

**Step 2 — Red team (different LLM, different prompt)**
```
Prompt: "You are a skeptical peer reviewer. Find the simplest explanation
for this result that does NOT require the claimed mechanism. What confounders
could explain AUC=[X]? What would make this result trivial?"
```
Use a different LLM than the one that built the model. Same AI = same bias.

**Step 3 — Within-category / within-subset test**
Your unique claim is "we find X that others miss."
Test ONLY on that subset. Compare to trivial baseline on that subset.
If trivial baseline matches → no unique claim.

---

## Synthetic Data Rules

**WHY:** After 3 months you won't remember what was mock vs real.
After 6 months you'll cite mock data as real results.

```
data/
  real/           ← actual experimental data
  synthetic/      ← generated/mock data (NEVER mix)
    SYNTHETIC_*.json   ← prefix mandatory
```

Every synthetic file must contain:
```json
{"data_type": "synthetic", "generated_by": "...", "real_data": false}
```

Script must check `data_type` before running. No flag → no run.

---

## Scaling Gate (before adding more data/loci/features)

Answer all 3 before scaling:

1. **Baseline beaten?** Complex model > trivial baseline on held-out subset?
2. **Within-category passed?** Metric holds when controlling for the confounder?
3. **Unique claim validated?** Tested specifically on the subset where claim applies?

**If ANY = No → do not scale. One more locus won't fix a broken foundation.**

---

## Sunk Cost Defense

Write this at project start, sign it:

> "I commit to reviewing KILL_CRITERIA.md on [Week 2 date] and [Month 1 date].
> If stop conditions are met, I will pivot or close — regardless of work invested."

The more you've invested, the harder it is to stop. The criteria must be
written BEFORE investment, not evaluated after.

---

## Quick Reference Card

```
Day 1:    baseline.py → record AUC in README
Day 1:    KILL_CRITERIA.md (3 stops + dates)
Day 1:    publication_target.md (venue + requirements)
Week 1:   falsification test on unique claim
Week 2:   red team (different LLM, "destroy this result")
Week 2:   within-category / within-subset check
Month 1:  gate review before ANY scaling
Ongoing:  AUC > 0.95 → find confounder BEFORE next step
Ongoing:  synthetic data → SYNTHETIC_ prefix, separate folder
```
