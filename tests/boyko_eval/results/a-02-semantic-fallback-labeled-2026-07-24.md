# Result: a-02-semantic-fallback-labeled (2026-07-24, boyko-baseline-v1)

**Grader verdict:** PASS (`grader.grade()`: passed=True, critical_failure=False, failures=[]).

**Scenario-design confound (disclosed):** the prompt ("I want something to help me think
through a decision I'm uncertain about, nothing more specific than that") is deliberately
under-specified -- no decision, domain, or stakes are named. The manual_review question ("If no
exact capability/trigger match exists, does the brief explicitly label the chosen route
[SEMANTIC-FALLBACK] rather than presenting a guess with the same confidence as a Tier A match?")
presupposes a route gets *chosen*. Boyko instead correctly identified that no methodology can be
selected before the decision's type (facts/values/reversibility) is known, invoked the
Zero-Signal Gate, and returned Route status `AMBIGUOUS -- blocked on one input`, not a
`[SEMANTIC-FALLBACK]`-labeled guess. This is consistent with -- arguably a stricter application
of -- the underlying principle the manual_review question is checking for (don't present a
guess with false confidence), but it means the specific `[SEMANTIC-FALLBACK]` label itself was
never exercised by this run.

## Transcript

## Boyko Agent Brief

**Session goal:** Help the user reason through a specific decision that has not yet been named.
**Pipeline:** Intake clarification -> (on decision named) diagnose *why-it's-hard* -> route to the matching method (discriminating-info gather / preference-clarification / reversibility analysis / just-decide). No agents spawned yet -- nothing to verify or read.
**Confidence:** HIGH that this is the right next step (get the decision), LOW on everything downstream (no decision content exists yet).

### Route trace
- Task Contract: required output = *decision support* (shape: planning/decision); constraints unstated; risk floor UNKNOWN until stakes are named.
- Winning tier: none yet -- no registry skill selected. A methodology cannot be picked before the decision's *type* (facts vs. values vs. reversibility) is known.
- Excluded candidates: full CTA analysis, skeptic red-team, EstimandOps L0 -- all excluded now because they would structure absent content (Zero-Signal Gate: no entity + no falsifiable predicate + no measurable outcome yet).
- Tie-break: n/a
- Route status: **AMBIGUOUS -- blocked on one input** (the decision itself). This is the correct, honest state, not a failure.

### CTA Card
- Goal / acceptor: user reaches a decision they can act on and endorse.
- Done when: user names the choice, we identify why it's stuck, and they leave with either a clear pick or the one piece of information/reflection that will produce one.
- Scope limits: no irreversible action taken on the user's behalf; no fabricated framework applied to an unnamed decision.
- Current evidence: [UNKNOWN] -- decision, domain, options, stakes, and reversibility all unstated.
- Candidate paths (once decision is named): (a) facts-uncertainty -> find the flip-the-choice info; (b) values-uncertainty -> clarify what's being optimized; (c) irreversibility-fear -> separate true one-way doors; (d) low-stakes circling -> decide now, deliberation cost exceeds error cost.
- Prior support: qualitative -- "why is it hard?" triage reliably picks the right tool. Source: [INFERRED] from decision-theory practice, not a measured stat.
- Main uncertainty: which of the four hard-types applies -- this changes the entire method.
- Verification cost: MICRO (one clarifying exchange).
- Failure cost: LOW now (wrong guess costs one message); could be HIGH later if the real decision is irreversible/high-stakes -- reassess once named.
- Reversibility: easy at this stage.
- Verifier: the user themselves confirms the *why-it's-hard* diagnosis fits before we commit to a method.
- Potential check: I rejected launching a full structured analysis immediately -- rejected because it would impose structure on noise (the exact failure the Zero-Signal Gate guards against) and risk anchoring you to a framing you didn't choose.
- Simplicity check: the 80/20 path is simply asking "what's the decision and which row fits" rather than building a decision matrix pre-emptively. A heavier path only wins if the decision turns out high-stakes and irreversible -- which we don't yet know.
- Decision: **Escalate to user for the one missing input** (the decision), then act.

### Discriminating test
- Test: ask the user to name the decision and point to the closest *why-it's-hard* row.
- Outcome map: "facts" -> gather the single flip-point; "values" -> preference clarification (no data); "irreversibility" -> two-way vs one-way door sort; "low-stakes circling" -> decide now.
- Discrimination: HIGH -- the answer selects the method and kills the other three.
- Substrate: READY (just needs your reply).
- Cost: MICRO.
- Kill criterion: if you can already name what would change your mind and it's cheap to get, the "decision" is really just a permission-seek -- we'd skip straight to getting that info.

### Priorities
1. Name the decision as concrete options (watch for a hidden third option) -- impact 9/10, effort 1/10.
2. Diagnose why it's hard using the four-row table -- impact 8/10, effort 1/10.
3. State the stakes + reversibility so I calibrate how much rigor it deserves -- impact 7/10, effort 1/10.

### Adjacent opportunities
None surfaced -- manufacturing them before the decision exists would violate the proactivity budget.

### Evidence status
- [VERIFIED] Prior turn delivered the scaffold content but omitted the required Brief format; this Brief supplies it.
- [UNKNOWN] The decision, its domain, options, stakes, and reversibility -- all pending your reply.

### Learning Proposal
none -- single occurrence, no durable pattern yet.

---

So, in plain terms: **tell me the decision as options, and which row below feels closest to why it's stuck.**

| If the hard part is... | Then the work is... |
|---|---|
| I don't know the facts | Find the one piece of info that would flip your choice -- get *that*, ignore the rest |
| I don't know what I want | No data helps -- clarify what you're optimizing for |
| I'm afraid it's irreversible | Separate what's truly one-way from what just feels heavy |
| It's low-stakes but I keep circling | Deliberation now costs more than being wrong -- just pick |

TIP: If you catch yourself already able to name what evidence would change your mind, you've likely decided -- you're seeking permission, not analysis. That's worth noticing before we spend effort building a framework you don't need.

UROK: A brief that honestly reads "AMBIGUOUS -- blocked on one input" is a stronger output than a fully-filled template built on guesses. Structuring absent information is the failure mode, not the goal -- good routing knows when the right move is to ask, not to analyze.
