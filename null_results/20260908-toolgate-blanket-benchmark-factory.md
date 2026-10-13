# 20260908-toolgate-blanket-benchmark-factory — REJECT

## Claim

**Not under test: "ToolGate is useless."** Under test: "a blanket ToolGate-
style executable-acceptance benchmark factory — generate N candidate tasks
per skill, run them through the 3-gate pipeline (executable reference
solution / no-tool screening / tool-using solve), across this repo's skill
catalog — is worth adopting at the current execution design and observed
per-candidate cost."

Source idea: ToolGate (arXiv 2609.02067, independently verified real) — a
3-gate pipeline for accepting AI-generated benchmark tasks, applied in the
source paper to 500 generated FEniCSx tasks → 128 survivors. Proposed here as
a way to generate real, hostile test cases for this repo's own skills instead
of relying only on hand-written eval cases.

## Context — why this looked worth piloting

The paper's mechanism is real and the gap it targets is real: this repo's
skill evals (e.g. `boyko-preflight`'s own eval loop, `skill-creator`'s
benchmark machinery) are largely hand-written test cases, which are cheap
but can miss the failure modes an adversarial, executable-acceptance
pipeline would catch. Before committing to build this for the whole catalog
(134 skills at last count), the user's own instruction was explicit:
"начни с одного скилла, померь токены живьём" — pilot on exactly one real
skill, at minimal scale (3 candidates, no external CLI, pure subagent
reasoning), and get a real number before any scaling decision.

## Test (live, one skill, three candidates)

Ran the pilot on `skills/extensions/security-audit/SKILL.md` (financial-org
security checklist skill, `maturity: wired`). Generated 3 candidate
benchmark tasks (deliberately adversarial code snippets a real audit should
catch), built ground truth for each independently before running the skill
against them, then screened per the 3-gate protocol.

**Result: 1/3 candidates survived all 3 gates.** 2/3 were killed at the
no-tool-screening / ground-truth-mismatch stage — not because the skill was
wrong, but because the candidates themselves didn't cleanly isolate a single
checkable claim (execution/ground-truth construction overhead, the same
class of loss the source paper's own 500→128 funnel already describes at
its own scale).

**Real cost, measured, not estimated:** subagent-reported token usage across
the full pilot (candidate generation + ground truth + screening + solve,
3 candidates, 1 skill) = **190,848 tokens**.

```
190,848 / 3 candidates ≈ 63,616 tokens per candidate (this skill, this design)

Sanity check only, NOT a forecast (linear extrapolation from n=3 on one
skill; ignores that a skill's own file-read cost amortizes across its
candidates, and pilot generation quality may not hold at scale):
  30 candidates × 3 skills   ≈  90 × 63,616 ≈ 5.7M tokens
  3 candidates  × 134 skills ≈ 402 × 63,616 ≈ 25.6M tokens
```

## Verdict: REJECT (narrow — scope stated explicitly, see Kill Analysis)

**REJECT: blanket ToolGate-style benchmark-factory rollout across the skill
catalog, at the current execution design (full LLM-driven candidate
generation + ground truth + screening + solve per candidate) and the
observed cost per candidate.** Not a verdict on ToolGate's underlying
mechanism, which worked exactly as designed and caught a real issue (see
below) — the economics of running it this way, at this cost, catalog-wide,
do not clear the bar.

```yaml
verdict: REJECT

target:
  blanket benchmark-factory rollout

reason:
  observed_cost:
    candidates: 3
    skills: 1
    tokens: 190848

value_observed:
  valid_candidates: 1
  real_skill_gaps_found: 2

interpretation:
  method is diagnostically useful
  current economics do not support catalog-wide scaling

revival_condition:
  - materially cheaper candidate generation
  - deterministic screening replaces major LLM stages
  - cost per accepted benchmark drops substantially
```

## Kill Analysis (Anti-Overfitting Gate)

**What this killed:** running the full 3-gate pipeline, at its current
all-LLM execution design, as a standing benchmark-generation factory across
this repo's skill catalog. At ~63.6k tokens/candidate, even a modest
30-candidates-×-3-skills trial run is ~5.7M tokens, and a shallow
3-candidates-×-134-skills catalog sweep is ~25.6M tokens — disproportionate
to the value a single pilot actually returned.

**What this did NOT kill:**
- ToolGate's own mechanism (executable reference solution → no-tool
  screening → tool-using solve) is real and worked as designed on this
  pilot: it correctly killed 2/3 weak candidates before they could produce a
  false benchmark result, and the 1 surviving candidate correctly exercised
  a real gap in the target skill.
- The pilot is a genuine PROMOTE at its own (tiny) scale as a **diagnostic**,
  not a factory: run ad hoc, by hand, on a single skill under active
  suspicion, it is cheap enough to be worth doing again.
- Two real, independently-actionable findings survived the pilot and are
  addressed directly, outside this REJECT: `security-audit`'s SKILL.md was
  missing explicit checklist coverage for (a) secrets/credential handling
  and (b) monetary-transaction integrity validation — both added in this
  same PR (see `skills/extensions/security-audit/SKILL.md`). `maturity`
  stays `wired`, not promoted — a 1/3 raw pass rate on a 3-sample pilot is a
  "don't promote" signal, not a quality percentage to publish.

**Relaxation Map (untested, not built — do not build without a new trigger):**
- Remove assumption "candidate generation must be full LLM reasoning": a
  deterministic or template-driven candidate generator (parameterized from
  known vulnerability classes per skill category) would cut the dominant
  cost driver without touching the gate logic itself — the gate structure
  is exactly what worked in this pilot.
- Remove assumption "ground truth must be independently re-derived per
  candidate by the same pipeline": a small hand-curated ground-truth bank
  per skill category, reused across many generated candidates, would
  amortize the most expensive single step.
- Remove assumption "this must run catalog-wide before it's worth doing
  again": nothing here blocks re-running this exact pilot, by hand, on
  another single skill under active suspicion — that is a diagnostic use,
  not the rejected factory use, and costs the same ~64k tokens/candidate
  regardless of this REJECT.

## Trigger condition to revisit

Any of: (a) a materially cheaper candidate-generation path is available
(non-LLM or much smaller model); (b) a deterministic screening stage
replaces one or more of the current all-LLM gates without losing the
adversarial-quality signal the pilot demonstrated; (c) cost per accepted
benchmark drops substantially from the observed ~64k tokens (order of
magnitude, not incremental). None of these observed yet — this is a fresh
REJECT, not a stale one.

## null_retroscan check (Principle 5, immediate retroscan)

No active PROMOTE in `null_results/`'s sibling PROMOTE-tracking shares
meaningful token overlap with "benchmark factory" / "ToolGate" / "executable
acceptance" — this is a new mechanism to this repo, not a variant of a
tracked prior claim. No undercut to check against.

## Evidence

Live pilot, real subagent-reported token usage (not estimated), on the real
`skills/extensions/security-audit/SKILL.md` file, 3 real generated
candidates with independently-built ground truth before screening. Full
pilot transcript/report:
`toolgate_pilot_security-audit.md` (session scratchpad — candidate code,
ground truth, per-gate verdicts, and the raw token count this entry's math
is built from).
