# decision.md — 20260728-osa-fl-protocol-vs-standard-analysis

## Verdict

- [x] REJECT — claim falsified → copy to `null_results/<id>-<slug>.md` + update INDEX.md

_Scope note: this REJECTS the pilot's specific falsifiable statement ("Arm B
beats Arm A by ≥3 pts on ≥1 of 2 cases"), NOT the OSA/FL/Perelman apparatus in
general — see Kill Analysis below for the precise boundary. This experiment is
about the repo's own methodology, not a product feature; "REJECT" here means
"this specific claim about the protocol's comparative value did not survive its
own falsification test," which is itself an instance of the protocol working
as designed._

## Result Classification (End-of-session diamond scan)

- [ ] 🥇 Gold
- [x] 💎 **Diamond** — mandatory Steelman step over-credited a factually false
      security argument (Case 2); a specific, transferable, unexpected failure
      mode of DDD's Step 2 as currently worded. See Pearl Registry entry.
- [ ] 🥈 Silver
- [ ] 🪨 Stone

| Инсайт | Куда применимо |
|--------|----------------|
| Mandatory "steelman the opposing view" has no discriminator between a plausible-but-contestable counter-argument and a counter-argument that is simply false — applies to DDD Step 2 wherever it's invoked, not just security reviews | `rules/doubt-driven-development.md` Step 2 |
| REPEAT/REJECT threshold can under-reject relative to a real expert who has outside corroboration the test/agent doesn't have access to | `rules/perelman-audit.md` Promotion Rule, applies to any retrospective-grading pilot design |

## Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | N/A — this is a methodology-comparison pilot, not a classifier eval; "control" role is played by the real documented verdict as semi-gold-standard |
| Negative control | PASS — contamination check confirmed neither arm saw the real verdict or referenced its specific vocabulary/examples (see result_summary.md) |
| Stress tests | SKIPPED — n=2 pilot, no stress-test tier required at this scale; flagged as a limitation, not silently omitted |
| Skeptic verdict | SKIPPED — Step 8a applies to PROMOTE verdicts; this is a REJECT, governed by the Kill Analysis mandate instead |

## Rationale

Both blind graders, working independently on different cases, converged on the
same finding: Arm A (standard analysis) outscored Arm B (full protocol) by a
margin (4 and 2 points respectively) that would itself clear the pre-registered
MCID if the sign were reversed. The pre-registered falsifiable statement
required Arm B to win by ≥3 on at least one case; it lost both. This is a clean
falsification, not an ambiguous or narrowly-missed one — the honest verdict is
REJECT for the specific claim under test, with a full Kill Analysis to prevent
this from being mis-read as "the methodology has no value" (it does not
support that broader claim either — see below).

## If REJECT: Kill Analysis (OSA)

### What Was Killed

- The claim as stated: "applying this repo's full OSA/FL/Perelman apparatus to
  a REJECT-shaped claim's raw evidence, in a one-shot retrospective-grading
  context, produces a verdict a blind grader scores higher against the real
  documented outcome than standard informal analysis." Killed under the tested
  conditions: n=2, both REJECT-type cases, single run per arm, retrospective
  (not live/prospective) framing, single non-independent grader per case.
- Specifically, assumption(s) killed: "the protocol's REPEAT/REJECT threshold
  matches real-expert decisiveness at equal information" (Case 1); "the
  mandatory Steelman step is net-positive regardless of whether the
  counter-argument being steelmanned is actually sound" (Case 2, as currently
  worded with no soundness discriminator).

### What Was NOT Killed

- [x] Core mechanism / theoretical basis: the diagnostic content of
      claim_entropy / No-Collapse-Test / Kill Analysis reasoning was, per the
      graders' own sub-scores, often AS or MORE technically thorough than
      Arm A's (e.g. Case 1 falsifiability/specificity: Arm A 3/3, Arm B 2/3 —
      the one sub-score where Arm B trailed was itself close, and Arm B's
      "data swap RAN — FAILED" framing was praised as concrete). The failure
      is in verdict-selection and Steelman-application, not in the underlying
      analytical apparatus.
- [x] Assumption: "the protocol adds diagnostic value beyond standard
      analysis" (survived because: both graders found Arm B's structured
      breakdown caught real issues — missing MCID, missing ablation, missing
      adversarial subset — that Arm A also independently found by different
      means; the protocol didn't fail to find problems, it failed to convert
      findings into a verdict/recommendation that matched the real outcome).
- [x] Assumption: "the protocol is worth using live/prospectively, where no
      grader and no pre-existing gold-standard verdict exist" (survived
      because: this pilot never tested that mode — it tested retrospective
      grading against an answer key one arm structurally could not see but
      whose EXISTENCE and threshold-setting behavior may still differ from a
      live decision with no answer key at all — untested here, not disproven).

### Relaxation Map (for surviving assumptions)

| Assumption | Modification | New Path | Known kill-evidence? | Cheapest test |
|---|---|---|---|---|
| DDD Step 2 Steelman is unconditionally net-positive | Weaken — add a soundness discriminator ("steelman only if the counter-argument survives its own quick fact-check; otherwise state why it's false and skip crediting it") | V1: re-run Case 2's Arm B prompt with the discriminator added, same blind grading | **Done 2026-07-28 — CONFIRMED.** Score 7→11/12, now beats Arm A (7/12 that run). See `followup-v1-v2-rerun.md`. | Single re-run, ~15 min, reuses this pilot's harness |
| Perelman REPEAT/REJECT threshold is well-calibrated at equal information | Replace — require Arm B to also ask "would this evidence alone, with no outside corroboration, justify a REJECT this strong?" as an explicit Promotion-Rule sub-question | V2: re-run Case 1's Arm B prompt with the explicit question added | **Done 2026-07-28 — REFUTED as stated.** Verdict stayed REPEAT, score only 5→6/12, still loses to Arm A (8/12 that run). Confound identified: real investigator had external corroboration neither arm had access to — see `followup-v1-v2-rerun.md`. | Single re-run, ~15 min |
| Retrospective grading is a valid proxy for live protocol value | Remove — this pilot's design cannot test it | V3: a genuinely prospective pilot — apply the protocol to a NEW, not-yet-decided claim in real time, compare the eventual real-world outcome months later | Check: none yet, this is the honest next tier | Opportunistic, same accumulation pattern as `20260727-config-effectiveness-opportunistic` |

_Kill any row where "Known kill-evidence" = Yes before running the test — none
apply here, all 3 rows are open._

### Escape Point

- Should have been caught at: estimand step (Intercurrent Events table).
- Why it wasn't: the ICE table anticipated grading ambiguity and contamination,
  but did not anticipate that the real verdict's own confidence level might
  rest on information (external reviews) asymmetric to what either arm
  received — this is a variant of Exchangeability risk the DAG's
  Identifiability Checks table flagged for the GRADER but not for the
  underlying GOLD STANDARD's own evidentiary basis.
- Guard to add: `experiments/_template/estimand.md`'s Causal Layer checklist
  should add a line under Identifiability Checks specifically for
  retrospective-grading-against-a-real-verdict designs: "does the gold-standard
  verdict itself rest on information not available to the units being
  compared against it?" — not added to the template in this session (scope:
  this decision.md documents the gap; a template edit is a separate, small
  follow-up, not bundled into this pilot's result).

### Why This Differs From Prior Null Results

- No matching prior entry — this is the first experiment applying the
  falsification apparatus to itself (methodology-on-methodology), not a repeat
  of either underlying `null_results/20260716-*` case, which remain correctly
  REJECTed on their own separate claims.

## Rescue Review (OSA)

| Branch | What Red Team killed | Whole branch dead? | Weaker formulation | Revival Condition | AOG risk | Final Status |
|---|---|---|---|---|---|---|
| "Full protocol > standard analysis in one-shot retrospective grading, n=2" | The comparative claim as tested | no — only the tested formulation | "Full protocol > standard analysis WHEN Steelman has a soundness discriminator AND REPEAT/REJECT threshold accounts for grader-vs-real-verdict information asymmetry" | Re-run V1+V2 from Relaxation Map above; if the gap closes or reverses, the weaker formulation gains support | low — the relaxations are narrow, pre-registered before this decision, independently motivated by the graders' own stated reasoning (not post-hoc rescue) | `weak_alive` |
| "Full protocol has no diagnostic value" | N/A — never claimed by this pilot; explicitly the wrong reading per "What Was NOT Killed" | n/a | n/a | n/a | n/a | `hard_killed` as a mischaracterization — not a real branch this experiment supports |

**AOG check on `weak_alive` promotion (5/5 required for anything beyond `parked`):**
1. Pre-registration — yes, both relaxations (Steelman discriminator, threshold
   question) are directly read off the graders' own stated reasoning for THIS
   run, not invented after seeing an unfavorable result to save face.
2. Specificity — yes, V1/V2 are at least as specific as the original (single
   added instruction each, same harness, same cases).
3. Novel prediction — yes: V1 predicts Case 2's anti-pattern-avoidance
   sub-score rises without the discriminator changing anything else; V2
   predicts Case 1's verdict shifts from REPEAT toward REJECT without changing
   Arm B's diagnostic content.
4. Non-triviality — yes, both variants remain falsifiable (could still lose).
5. Independent motivation — yes, grounded in the graders' explicit reasoning,
   not "we want the protocol to win."
**Passes 5/5 → `weak_alive` is a legitimate final status, not narrative rescue.**

## Pearl Card Update

**Was the Prediction correct?** No — the pilot's own falsifiable statement
predicted Arm B could win; it lost both cases. Prediction was wrong, and the
falsification is exactly what makes the 2 mechanism-level findings trustworthy
(they survived an honest test that could have gone the other way).

**Falsification condition triggered?** Yes (claim rejected).
