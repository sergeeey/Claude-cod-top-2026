# Doubt-Driven Development — Adversarial Review Protocol

## Purpose
**Red-team non-trivial decisions BEFORE implementation** to catch blind spots, false assumptions, and costly mistakes.

**Key insight:** Single-agent confirmation bias is eliminated by cross-model adversarial review. Claude + skeptic disagree more productively than Claude + Claude.

**Pattern source:** [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills), integrated with our skeptic agent.

---

## When To Invoke Skeptic (Auto-Triggers)

### Trigger 1: Architecture Decisions
**Pattern:** Choosing framework, database, deployment strategy, API design.

**Examples:**
- "Should we use Neo4j or PostgreSQL for GeoMiro graph storage?"
- "Microservices vs monolith for Portfolio project?"
- "REST vs GraphQL for VeriFind API?"

**Action:** Invoke skeptic BEFORE writing code.

```markdown
Agent(skeptic, prompt="Red-team this architecture decision: [proposal]. What breaks? What's the best counter-argument?")
```

### Trigger 2: Hypothesis Design (Research Projects)
**Pattern:** Experimental design before data collection.

**Examples:**
- ARCHCODE: "Propose H7 design for ATP-mutagenesis" → skeptic challenges assumptions
- Portfolio: "Test BTC volatility strategy" → skeptic identifies confounders
- GeoMiro: "New scenario planning algorithm" → skeptic finds edge cases

**Action:** Invoke skeptic after proposal, before experiment.

### Trigger 3: High-Risk Changes
**Pattern:** Database migration, auth refactor, payment flow, security changes.

**Examples:**
- "Migrate 50M rows from MySQL to Postgres"
- "Refactor authentication middleware"
- "Change payment provider"

**Action:** Invoke skeptic + sec-auditor (parallel review).

### Trigger 4: "I'm 95% Sure" Claims
**Pattern:** High confidence without verification.

**Examples:**
- "This will definitely work"
- "No way this breaks production"
- "I've done this 100 times"

**Action:** Invoke skeptic to falsify confidence.

### Trigger 5: Zero Failures in Validation
**Pattern:** All tests passed, no edge cases found, 100% success rate.

**Examples:**
- "10/10 test scenarios passed"
- "F1=1.000 on all datasets"
- "Zero bugs found in review"

**Action:** Invoke skeptic to find the 11th test case that fails.

---

## Adversarial Review Protocol (5 Steps)

### Step 1: Propose Solution
**Agent 1 (Primary):** Architect, builder, or researcher proposes solution with reasoning.

**Required fields:**
- **Goal:** What problem are we solving?
- **Proposal:** What's the solution?
- **Reasoning:** Why is this the best approach?
- **Alternatives considered:** What did we reject and why?

### Step 2: Red Team (Skeptic Agent)
**Agent 2 (Skeptic):** Falsification-first adversarial review.

**Skeptic's job:**
- **What breaks?** — Find the failure mode
- **Best counter-argument?** — Steelman the opposing view
- **Edge cases?** — What scenarios does this NOT handle?
- **Hidden assumptions?** — What's taken for granted?
- **Prior art failures?** — Who tried this and failed?

**Output:** List of vulnerabilities, ranked by severity.

### Step 3: Response to Skeptic
**Agent 1 (Primary):** Address skeptic's concerns.

**Options:**
1. **Refine proposal** — Fix identified issues
2. **Accept limitations** — Document known tradeoffs
3. **Change approach** — Skeptic was right, pivot
4. **Escalate** — Disagreement unresolved, need Opus/human

### Step 4: Escalation (If Needed)
**Trigger:** Primary and skeptic disagree on severity/approach after 1 round.

**Escalation path:**
1. Invoke opus-model agent (not sonnet)
2. Present both arguments side-by-side
3. Opus makes final call OR defers to human

**Human escalation:** If Opus uncertain, STOP and ask user.

### Step 5: Document Decision (ADR)
**Always:** Record decision + dissent in `.claude/memory/decisions.md`.

**Format:**
```markdown
## Decision: [Title] (2026-05-11)

**Context:** [Problem statement]

**Proposal:** [Chosen approach]

**Skeptic concerns:** [What skeptic flagged]
- Concern 1: [description] → **Accepted** (documented limitation)
- Concern 2: [description] → **Mitigated** (added guard X)
- Concern 3: [description] → **Dismissed** (reasoning Y)

**Final decision:** [Approach] because [reasoning]

**Dissent recorded:** [If skeptic still disagrees, note it here]

**Reviewers:** Agent 1 (primary), skeptic, [opus if escalated]
```

---

## Integration With Existing Agents

### Architect Agent
**Before:** Architect proposes design → builder implements.  
**After:** Architect proposes → **skeptic red-teams** → architect refines → builder implements.

**Trigger:** Any architecture decision in architect output.

### Navigator Agent
**Before:** Navigator picks approach → executes.  
**After:** Navigator picks approach → **skeptic challenges** → navigator defends or pivots.

**Trigger:** Non-obvious approach choice (not "read file", but "use Neo4j for this").

### Builder Agent (High-Risk Code)
**Before:** Builder writes migration/auth/payment code → tests.  
**After:** Builder writes → **skeptic + sec-auditor review** → builder fixes → tests.

**Trigger:** Code touches database schema, auth, payments, secrets, PII.

---

## Cross-Model Review (Advanced)

**Single-model risk:** Claude reviews Claude's code → confirmation bias.

**Cross-model solution:**
1. **Primary:** Claude Sonnet proposes solution
2. **Skeptic:** Different model (GPT-4, Gemini, or Opus) red-teams
3. **Escalation:** If disagreement, third model (Opus/o1) arbitrates

**Why different models:**
- Claude + Gemini disagree on 30% more points than Claude + Claude
- Different training data = different blind spots
- Cross-model consensus > single-model confidence

**Implementation:**
```markdown
# Primary proposal (Claude Sonnet)
Agent(architect, model="sonnet", prompt="Design X")

# Skeptic review (Different model if available, else Opus)
Agent(skeptic, model="opus", prompt="Red-team this design: [proposal]")

# If Claude Code supports multi-model (future):
Agent(skeptic, model="gemini", prompt="Red-team this design: [proposal]")
```

---

## Doubt-Driven vs Traditional Review

| Approach | When Invoked | What It Catches | Limitation |
|----------|--------------|-----------------|------------|
| **Traditional Review** | After code written | Style, bugs, tests | Too late — design already committed |
| **Doubt-Driven** | Before implementation | Bad assumptions, wrong approach, edge cases | Requires discipline to slow down |
| **Post-Mortem** | After failure | What went wrong | Only learns from mistakes, not prevents |

**Doubt-driven timing:** Catch mistakes when they're **cheap to fix** (design phase), not expensive (production).

---

## Anti-Patterns (What NOT To Do)

### ❌ Anti-Pattern 1: Skeptic After Implementation
**Wrong:** Write code → invoke skeptic → rewrite.  
**Right:** Design → skeptic → write code once.

**Why:** Rewriting code costs 10× more than redesigning on paper.

### ❌ Anti-Pattern 2: Skeptic as Rubber Stamp
**Wrong:** Invoke skeptic, ignore concerns, proceed anyway.  
**Right:** Address concerns OR document why dismissed in ADR.

**Why:** Skeptic value = finding what you missed. Ignoring = wasted effort.

### ❌ Anti-Pattern 3: Skeptic for Trivial Decisions
**Wrong:** "Should this function be 10 lines or 15?" → invoke skeptic.  
**Right:** Save skeptic for **non-trivial** decisions (architecture, experiments, high-risk).

**Why:** Skeptic time is expensive. Reserve for decisions with 10x cost difference.

### ❌ Anti-Pattern 4: No Documentation
**Wrong:** Skeptic review happens → not recorded → forgotten in 2 weeks.  
**Right:** Always write ADR with skeptic concerns + resolution.

**Why:** Future-you needs to know WHY this decision was made despite concerns.

---

## Success Metrics

Track doubt-driven effectiveness:

| Metric | Target | How To Measure |
|--------|--------|----------------|
| **Caught-before-code** | ≥60% | Design flaws found by skeptic / Total design decisions |
| **Escalation rate** | 5-10% | Decisions needing human input / Total skeptic reviews |
| **False positives** | <20% | Skeptic concerns dismissed as invalid / Total concerns |
| **Decision reversals** | <5% | Decisions changed after implementation / Total decisions |

**Goal:** Find design flaws BEFORE code, minimize expensive reversals AFTER deployment.

---

## Real-World Examples

### Example 1: ARCHCODE Router KILLED by Doubt-Driven
**Proposal (Jan 2026):** Use ML router to classify VUS pathogenicity (AUC 0.89).

**Skeptic concerns:**
- Training data bias (benign/pathogenic not matched by allele frequency)
- Unmatched test set (easy variants vs real-world)
- Category leakage (model learns source annotation, not biology)

**Response:** Re-ran with matched controls → AUC dropped to 0.52 → **KILLED**.

**Outcome:** Saved 6 months of wasted development. Skeptic was right.

### Example 2: mcp-bouncer Prompt Injection Patterns
**Proposal (Apr 2026):** Block 5 prompt injection patterns.

**Skeptic concerns:**
- Pattern 3 blocks legitimate code examples with backticks
- False positive rate not measured
- No escape hatch for advanced users

**Response:**
- Added whitelist for code blocks
- Measured FP rate: 2.3% (acceptable)
- Added `--trust` flag for power users

**Outcome:** Launched with skeptic improvements → 0 user complaints.

### Example 3: GeoMiro Brier Score Accumulation
**Proposal:** Sequential Brier score accumulation (each scenario depends on previous).

**Skeptic concerns:**
- Can't parallelize (slower)
- Early mistake compounds (error propagation)
- User can't skip boring scenarios

**Response:** Accepted limitation, documented tradeoff in ADR.

**Outcome:** Sequential accepted because **Brier scores must accumulate** (inherent constraint, not fixable).

---

## Integration Checklist

Before enabling doubt-driven in your workflow:

- [ ] Skeptic agent exists and tested
- [ ] Architect agent knows when to invoke skeptic
- [ ] ADR template includes "Skeptic concerns" section
- [ ] decisions.md tracks doubt-driven decisions
- [ ] Team understands: skeptic = red team, not enemy
- [ ] Metrics tracked (caught-before-code rate)

---

## Quick Reference

**When to invoke skeptic:**
1. Architecture decisions
2. Hypothesis design (before experiment)
3. High-risk changes (DB/auth/payment)
4. High confidence without verification
5. Zero failures in validation (suspiciously perfect)

**How to invoke:**
```markdown
Agent(skeptic, prompt="Red-team this proposal: [description]. What breaks? Best counter-argument? Edge cases?")
```

**What to do with skeptic output:**
1. Address concerns (refine proposal)
2. Accept limitations (document in ADR)
3. Change approach (skeptic was right)
4. Escalate (unresolved disagreement)

**Always document:** Decision + skeptic concerns + resolution in ADR.

---

**Last updated:** 2026-05-11  
**Status:** ACTIVE — integrate with architect/navigator agents  
**Next review:** After 10 doubt-driven decisions (measure effectiveness)  
**Pattern source:** Addy Osmani agent-skills + our skeptic engine

---

## References
- [[agents/skeptic.md]] — Skeptic Engine v2.1 implementation
- [[Repo Intel — Addy Osmani Agent Skills]] — Original pattern
- [[rules/rationalizations.md]] — Anti-excuse table (related)
- [[rules/integrity.md]] — Submission Gate (uses skeptic auto-trigger)
- `.claude/memory/decisions.md` — ADR format examples
