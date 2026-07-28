# decision.md — hypothesis-arbiter taxonomy + Oracle Adequacy Gate pilot

## Verdict

**Filing status: ARCHIVE → `parked/`** (corrected 2026-07-28 after external review
caught a mis-filing: this entry was originally copied to `null_results/`, but per
`rules/falsification-ladder.md` § FL Rescue Layer, "Rescue saves directions (→
`parked`)" — once Rescue Review below assigns Final Status = `parked`, the
routing follows the direction's disposition, not the raw claim-level kill. See
`parked/20260728-hypothesis-arbiter-taxonomy-pilot.md` for the filed copy.)

**Claim-level result: REJECT** (falsified as stated) — for the pre-registered claim
only. The 8-class taxonomy addition to `hypothesis-arbiter`'s SPAWN step did NOT
cause inclusion of an Artifact-class hypothesis where the unmodified version
lacked one, on this n=1 case. Both arms independently produced a functionally-
equivalent Artifact-class hypothesis without the explicit checklist mattering for
THIS endpoint. This narrower claim-level REJECT is real and stands — only the
FILING location changes, not the finding.

## Result Classification

Blind grader (context-asymmetric, no session history), negative-control-tested:

| Transcript | Arm | Artifact-class hypothesis present? | Grader excerpt |
|---|---|---|---|
| 1 | A (baseline, `6ba1c29`) | **YES** | H₁: "T1 matches literal stdout of test-runner and lint tools... independent of any assertion being made" |
| 2 | B (taxonomy-augmented) | **YES** | H₂ (explicitly labeled Artifact): "T1 is matching against raw tool stdout that passes through the hook's input stream... cannot distinguish 'agent typed this sentence' from 'agent's shell command printed this line'" |
| 3 | Negative control (fabricated, no Artifact hypothesis) | **NO** (correct) | Grader: "None mention pytest, progress bars, stdout, or any tool-generated text as the source of the match" |

Oracle Adequacy: grader passed its own negative control (Transcript 3), so the
verdict on Transcripts 1-2 is not attributable to a grader that defaults to YES
under ambiguity.

## Evidence Summary

Pre-registered MCID ("Arm B includes it AND Arm A does not") requires Transcript
1 = NO. It is YES. **MCID not met — claim falsified as stated.**

## Kill Analysis (OSA)

### What Was Killed

The specific claim: "an explicit 8-class taxonomy checklist is NECESSARY for
`hypothesis-arbiter`'s SPAWN step to surface an Artifact-class hypothesis on a
tool-output-driven false-signal question." A sufficiently capable generator
already reaches for this class unaided when the raw symptom material itself
contains strong tool-output shape cues (in this case: literal `[NNN%]` tokens
next to recognizable tool banners like `---RUFF---`).

### What Was NOT Killed

- The taxonomy could still add value on cases where the tool-output cue is
  LESS visually obvious than this one, or where the model's own prior is more
  strongly anchored on a single plausible mechanistic story (this session's own
  original real-world encounter with this exact bug: my FIRST, unaided
  hypothesis was the WRONG mechanistic guess — "wording matches all/passed
  prose" — and I only reached the correct Artifact-class explanation after a
  negative-control harness forced a second look. That original real-world
  failure happened WITHOUT the raw symptom pre-organized into a clean 10-item
  frequency table the way this pilot's prompt handed it to both arms — the
  pilot's input format may have already done work that the taxonomy would
  otherwise have to do).
- The secondary, non-pre-registered observation below (explicit class
  separation) is not killed by this result — it simply wasn't what this
  pilot's endpoint measured.
- The Oracle Adequacy Gate addition is entirely untested by this pilot (its
  endpoint only exercises the SPAWN-stage taxonomy, per `estimand.md`).

### Relaxation Map (for surviving assumptions)

| Assumption | Relax how | Cheapest next test |
|---|---|---|
| "Raw symptom material is unstructured/ambiguous enough that a taxonomy could matter" | This pilot's prompt already handed both arms a pre-frequency-sorted table with visible tool-banner strings (`---RUFF---`) — a genuinely harder input might not include those cues explicitly | Re-run with a MESSIER raw symptom (e.g. a single unsorted transcript excerpt, no frequency counts, no `---RUFF---`-style banner strings) closer to how the real 2026-07-28 investigation actually started |
| "The model's own default prior already covers Artifact-class reliably" | Test on a case where a Mechanistic explanation is MORE seductive / has more surface plausibility than Artifact, so the generator has more pull toward Mechanistic-only tunnel vision | Re-run on a case from a DIFFERENT domain, ideally one where this session's own history shows a real first-hypothesis mistake (candidate: the pattern_escalation_review.py UTC/local timezone bug — my own real first read of that code briefly assumed it was already fixed based on an unrelated heuristic before checking the actual dates) |

## Secondary observation (Pearl Registry candidate, NOT rescue evidence for the falsified claim)

Both arms found the Artifact class, but Arm B's hypotheses are explicitly
separated into distinct, individually-labeled causal classes (Mechanistic ≠
Artifact ≠ Confounder ≠ Boundary ≠ Cross-domain, each its own row with its own
class tag), while Arm A's H₁/H₂/H₃ partially overlap the same idea-family
without an explicit label distinguishing "the trigger matches tool stdout"
(Artifact) from "the hook is architecturally scoped to see all tool output"
(closer to Boundary/Confounder) — Arm A's own table does not name these as
different classes even though they are conceptually different explanations.
Arm B also explicitly named and justified the 2 classes it chose NOT to
include (Reverse causality, Adversarial) rather than silently omitting them.

This is a real, observed difference — but it is NOT what the pre-registered
claim/MCID tested (presence/absence of Artifact-class content), so it does
not rescue the REJECT verdict. Logged separately to Pearl Registry as a
distinct, smaller, more specific falsifiable prediction for a future test:
"an explicit taxonomy improves downstream KILL-DESIGN quality (Этап 2) by
producing more distinct, non-overlapping kill-tests per hypothesis, even when
SPAWN-stage class coverage is unaffected" — this would require testing Этап 2
output, not Этап 1, and is out of scope for this pilot.

## Why This Differs From Prior Null Results

Distinct from `null_results/20260728-osa-fl-protocol-vs-standard-analysis.md`
(the same-day OSA/FL protocol pilot): that pilot found the FULL protocol
underperformed on end-to-end review tasks. This pilot tests one narrow,
specific addition (SPAWN-stage taxonomy) on one narrow, specific endpoint
(Artifact-class presence) and finds it made no measurable difference on THIS
case — a much more local and more clearly-scoped null result, consistent in
spirit (added structure ≠ automatic improvement) but not the same finding.

## Rescue Review (OSA)

Formulation killed, not the whole direction: "explicit taxonomy checklist,
tested via SPAWN-stage class-presence on ONE case" is what's falsified. The
broader direction ("does explicit hypothesis-class diversification help
anywhere in the 5-stage cycle") is not ruled out — parked pending a harder
test case (see Relaxation Map) or a different pipeline stage (Этап 2, per the
Pearl Registry candidate above).

**Status: `parked`** (not `hard_killed`) — genuinely untested on a harder case,
not disproven on the general idea.

## Post-hoc corrections (external review, 2026-07-28, same day)

An outside review of this pilot's write-up caught two real defects before
anything reached main. Both were tool-verified before accepting (per this
repo's own `audit-verification-gate.md` — an external claim is `[INFERRED]`
until re-checked, not `[VERIFIED]` by assertion):

1. **Mis-filing.** This decision was originally copied to `null_results/`
   under a bare REJECT. But `rules/falsification-ladder.md`'s own FL Rescue
   Layer text says "Rescue saves directions (→ `parked`)" — once Rescue
   Review (above) assigns Final Status `parked`, filing follows the
   direction's disposition, not the raw claim-level kill. **Fixed:** moved to
   `parked/20260728-hypothesis-arbiter-taxonomy-pilot.md` +
   `parked/INDEX.md`; removed from `null_results/`. The claim-level REJECT
   above is unchanged and still stands — only the routing changed.
2. **Oracle Adequacy Gate duplication.** `git log` confirms
   `docs/oracle-adequacy-gate.md` already existed (2026-06-30, PR #149/#153)
   as the canonical Oracle-Aware Core component 2, with its own
   ADEQUATE/WEAK/INADEQUATE verdicts and a 5-check table — never referenced
   by `falsification-ladder.md` before today's edit (verified: `git show
   HEAD:rules/falsification-ladder.md | grep -i oracle` was empty). The
   additions here re-specified ~half that checklist under new names instead
   of pointing at it — a real drift risk (two documents, two check-counts,
   silently diverging over time). **Fixed:** both `rules/falsification-
   ladder.md` Step 2b and this skill's Этап 4 now point at the canonical
   gate and keep only the 2-3 checks genuinely not covered there
   (independence/context-asymmetry, injected-error catch, no data leakage).

Two review findings did NOT hold up under verification:
- "L0 was skipped" — `estimand.md` already classified this pilot
  `question_type: causal` before any test ran. The chat summary given to the
  user omitted mentioning that step; the artifact itself did not skip it.
- "Grader verdict called blanket-trustworthy" — the decision.md language was
  already scoped to the one failure mode the negative control tests
  (default-to-YES), not a general reliability claim. The looser word
  "trustworthy" appeared only in the informal chat summary, not here.

One finding is agreed as valid future-pilot guidance, not a defect in this
pilot: MCID measured only SPAWN-stage class presence, not diversity/
duplication/downstream kill-test quality — already captured, pre-review, in
the Pearl Registry entry above, scoped correctly as future work rather than
retrofitted to rescue this pilot's own falsified claim.

## Recommendation — explicit judgment call for the user, not decided here

The taxonomy addition was already reverted from
`skills/extensions/hypothesis-arbiter/SKILL.md` (see Rescue Review above).
What remains open is the Oracle Adequacy Gate addition (now deduplicated
against canonical, see corrections above) — cheap, untested by this pilot,
structurally sound. `hypothesis-arbiter`'s existing `maturity: dogfooded`
evidence (`benchmarks/strong-inference/run-2026-07-23-full.md`, 10/10) predates
this addition — the file has diverged from what was benchmarked, the same
"re-tag when the contract changes" situation found earlier this session for
`boyko-agent`/`boyko-baseline-v1`→`v2`. Recommend noting in
`skills/registry.yaml` that `hypothesis-arbiter`'s `maturity_evidence` does
not yet cover the Oracle Adequacy Gate addition, rather than reverting it
outright (it duplicates nothing now, and costs little) — but this is a
judgment call for the user, not decided here.
