# Rationalizations Table — Anti-Excuse Protocol

## Purpose
This file documents **common excuses engineers (and AI agents) use to skip best practices** — and why each excuse is wrong. Every rationalization is countered with quantified tradeoffs and concrete actions.

**Why this matters:**  
Knowing a rule ≠ following a rule. Rationalization is the gap. This table closes it by preempting pushback with evidence.

**Source:** Pattern from [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills), applied to our harness integrity rules.

---

## Core Rationalizations (by frequency)

### 1. Verification & Evidence

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "I already know this API, no need to read the file" | [MEMORY] does not replace [VERIFIED]. APIs change. Training data lags. | Read the file. Always. Takes 10 sec. | 30 min debug when API changed 2 months ago |
| "I'm 90% sure, no need to re-check" | 10% errors = hundreds of bugs per year | [UNKNOWN] > false [INFERRED]. Mark it. | 1 production incident costs 10× dev time |
| "I checked this in a previous message" | Context compaction may have removed it. File state could have changed. | Re-verify with a tool (Read/Grep/Bash). | Silent failure: wrong assumption baked into code |
| "Sub-agents already verified this" | Agents read READMEs/docs, not code. Their [VERIFIED] = your [INFERRED]. | Re-verify agent claims with grep/bash. Always. | False [VERIFIED] → catastrophic submission (see ТОП-10 theater) |
| "No phantom sources needed, I remember the URL" | Memory hallucination rate: ~15% for URLs, ~40% for version numbers | Verify URL exists with WebFetch. Verify version in package registry. | User wastes 20 min on 404, loses trust |

### 2. Testing

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "Tests slow me down" | Tests prevent 10× rework cost. Simple changes break production most often. | At least 1 test (happy path). Red-Green-Refactor. | 2 hours fixing production bug that 5-min test would catch |
| "MVP doesn't need tests" | MVP bugs cost 10× to fix in prod. Early users remember broken experience forever. | Coverage ≥60% for MVP. No excuses. | Lost early adopters = lost product-market fit signal |
| "I'll write tests after implementation" | Tests written after code test the implementation, not the requirements | Load tdd-workflow skill. RED first. | Missed edge cases = production bugs |
| "This change is too simple for tests" | "Simple" changes cause 40% of production incidents (Google SRE Book) | Write the damn test. 3 minutes. | 1 hour rollback + postmortem |
| "I wrote the tests and they all pass" | Self-authored tests verify self-authored code — circular tautology. Validator that embeds answer IS the answer. | Check: did test/data file exist before this session? If NO → label [VERIFIED-SYNTHETIC], not [VERIFIED-REAL]. | Validation theater (ТОП-10: $1.4M disaster avoided by skeptic gate) |

### 3. Planning & Architecture

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "No plan needed for 2 files" | Threshold is 3 files. But 2-file changes often grow to 5 mid-work. | Optional for 2, required for 3+. Count carefully. | Scope creep → 2 files become 7 → no coherent design |
| "No spec needed, it's obvious" | "Obvious" to you ≠ obvious to reviewer/user/future-you. | Write 1-page spec. 15 min spec > 2 hr misaligned rework. | Rebuilding feature from scratch after user says "that's not what I meant" |
| "Architecture doc is overkill for this" | Undocumented decisions = tribal knowledge. Bus factor = 1. | Write ADR (5 minutes). Template in decisions.md. | 6 months later: "Why did we do this?" → reverse-engineer from code (2 hours) |

### 4. Workflow & Discipline

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "The user is in a hurry, I'll skip the review" | Skipping review = technical debt. Reviewer agent runs in 30 sec. | Run reviewer agent. Always. | Production bug costs 100× more than 30 sec review |
| "Security check not needed, it's internal API" | Internal APIs vulnerable (lateral movement). 70% of breaches start internal. | Load security-audit skill. Check for SQL injection, PII leaks. | Data breach costs $4.35M average (IBM 2023) |
| "MCP will answer faster than local search" | MCP: 200+ tokens, 2 sec latency. Local: 0 tokens, 0 latency. | Read/Grep first. MCP only if local fails. | Wasted context budget → earlier compaction |
| "I don't have time for type hints" | Type hints prevent 5× debug time. Mypy catches 40% of bugs pre-runtime. | Add type hints. Costs 10 sec per function. | 1 hour debugging None vs "" vs 0 confusion |

### 5. Evidence Quality

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "This evidence is good enough" | [VERIFIED-SYNTHETIC] ≠ [VERIFIED-REAL]. Synthetic proves code runs, NOT that it works. | Validation claims need real-world data with URLs cited. | Validation theater → paper retraction (ARCHCODE near-miss May 2026) |
| "Round numbers are fine" | F1=1.000 or 100% accuracy on real data = red flag. Suspiciously perfect = synthetic/cherry-picked. | Check: dataset URL cited? Test predates session? If NO → [SYNTHETIC]. | ТОП-10 theater (May 2026): 100% SUCCESS on synthetic, 0-50% on real data |
| "Two sources is overkill" | Confidence capped at MEDIUM with 1 source. Need ≥2 independent sources for HIGH. | Find 2nd source. Cross-check for conflicts. | Built entire feature on deprecated API (1 source was outdated) |

### 6. Submission & Publication

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "Ready for submission, I checked everything" | Excitement of completion = enemy. 3 prior incidents where this failed. | Run 4 gates: skeptic + checklist + consistency + 24h cooling. No exceptions. | Paper rejection, grant denial, wasted months (see Submission Gate Protocol) |
| "Text matches figures, I eyeballed it" | Side-by-side compare required. Eyeball misses 20% of discrepancies. | Export numbers from both, diff them programmatically. | ARCHCODE manuscript v2: text 0.98 vs figures 0.79 (caught by gate) |
| "Synthetic data is fine for validation" | Validation = claim about real world. Synthetic ≠ real. | [VERIFIED-REAL] only. Need ≥3 real sources (URLs, API calls, external files). | Retraction risk (see ArgosArb postmortem) |

### 7. Debugging & Causal Analysis

| Excuse | Why It's Wrong | What To Do Instead | Cost of Being Wrong |
|--------|----------------|-------------------|---------------------|
| "I know what's wrong, let me fix it" | Crash site ≠ bug site. 60% of "obvious" fixes target symptom, not root cause. | Answer 5 Causal Questions (integrity.md). If can't answer all 5 → don't change code yet. | Fix symptom → bug reappears in different form 2 weeks later |
| "Let's try something different" (Tier 3 without Tier 1-2) | Stuck Detection has 4 tiers for a reason. Tier 3 = last resort, not first move. | Exhaust Tier 1 (quick retry), then Tier 2 (context refresh), THEN Tier 3 (new strategy). | Abandon working approach 1 step from solution |
| "Error message is useless" | 80% of errors have actionable info in FULL traceback (not just last line). | Read FULL traceback. Google exact error + framework version. | Spend 1 hour on problem that Stack Overflow solved in 2 min |

---

## Integration With Existing Rules

This table **does not replace** existing rules. It **complements** them by addressing "but why?" pushback.

| Rule File | Adds Rationalizations For |
|-----------|--------------------------|
| `integrity.md` | Verification, evidence markers, hallucination prevention |
| `testing.md` | Test coverage, TDD, validation theater |
| `coding-style.md` | Type hints, comments, PII protection |
| `workflow.md` | Planning, review, autonomy |
| `security.md` | Security audits, PII, secrets |

**Cross-reference format in rules:**
```markdown
## Rule: Always verify URLs before using them

**Rationalization guard:** See rules/rationalizations.md #1 "I already know this API"
```

---

## How To Use This File

### For Orchestrator (Claude main agent)
Before accepting a skip/shortcut request:
1. Check if excuse matches this table
2. If match found → cite counter-argument + cost
3. Require explicit override (user must type "skip anyway")

### For Sub-Agents (builder, tester, reviewer)
When generating recommendations:
1. Anticipate pushback (predict likely excuse)
2. Pre-address it in recommendation text
3. Cite this table: "I know [excuse], but [counter-argument]"

### For Rules Authors
When adding new rules:
1. Predict top 3 excuses people will use to skip it
2. Add row to this table with quantified costs
3. Link rule → table

### For Weekly Retrospectives
Review violations:
1. Did violation match a known rationalization?
2. If yes → counter-argument failed, strengthen it
3. If no → add new row to table

---

## Metrics (track effectiveness)

| Metric | Target | How To Measure |
|--------|--------|----------------|
| Rule violation rate | <5% per rule | Weekly audit: grep session logs for skipped verifications |
| Rationalization frequency | Declining trend | Count "but I..." or "skip because..." in session logs |
| Cost of violations | <1 hour/week | Sum: debug time + rework + rollback from rule skips |
| Table coverage | ≥80% of excuses documented | When new excuse appears → add to table |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05-11 | Initial version (Pattern from Addy Osmani agent-skills) |
| | 7 categories, 27 rationalizations documented |
| | Cost quantification added to every excuse |
| | Integration with integrity.md, testing.md, coding-style.md |

---

**Last updated:** 2026-05-11  
**Status:** ACTIVE — enforced by orchestrator workflow  
**Next review:** Weekly (Monday morning routine)
