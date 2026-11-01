# claim.md — 20260912-cycle2-retrospective-replay

**Cycle 2, Part 1** of the Research/Evidence Loop minimal extension (Cycle 1 =
`experiments/20260912-research-evidence-loop-minimal-extension/`, shipped as PR #444).

**PREREGISTERED.** Everything below the line "— END OF PREREGISTRATION —" was written and
committed BEFORE running the replay script, before reading any historical verdict for this
purpose, and before seeing any count. This matters because the whole point of the exercise
is to avoid the Cycle-1 mechanisms grading their own homework.

---

## L0 — Question type (mandatory gate, EstimandOps)

- [x] **Descriptive**
- [ ] Predictive
- [ ] Causal

**Why NOT causal, stated explicitly because the motivating ТЗ's own success criterion IS
causal:** the ТЗ asks whether the system *became less likely* to promote false results and
repeat dead ends — a counterfactual contrast. That estimand is **not identifiable** from
the available data:

| Identifiability assumption | Status here |
|---|---|
| Consistency | ok in principle |
| Positivity | **violated** — no historical experiment was ever run under the treatment (the mechanisms did not exist) |
| Exchangeability | **violated** — no randomization, no comparable control arm |
| SUTVA | **violated** — the same author/agent carries knowledge across "arms"; a re-run of a past task is contaminated by knowing its outcome |

Per `estimand-ops.md`'s hard stop, a non-identifiable causal estimand is downgraded to
descriptive rather than answered anyway. The causal question is deferred to Part 2 (a
prospective Harness Change Ledger), not answered here.

## Estimand (descriptive)

- **Population:** every verdict-bearing artifact in this repository as of 2026-09-12 —
  `experiments/*/decision.md` excluding `_template` (N=12), `null_results/*.md` excluding
  INDEX (N=7), `parked/*.md` excluding INDEX (N=4).
- **What is measured:** for each Cycle-1 gate, whether it would FIRE against that artifact,
  under two separate layers (A and B below).
- **Summary measure:** absolute counts (not rates — N is far too small for a rate to mean
  anything), reported per gate, per layer.
- **MCID:** none defined, deliberately. This run produces counts to reason about, not a
  threshold to act on. Any "the mechanism is worth it / not worth it" decision belongs to
  Part 2's prospective ledger, not here.

**Natural-language statement (written before results):**
> We count, for each Cycle-1 gate, how many of this repository's 23 existing
> verdict-bearing artifacts that gate would flag — first as the gate actually ships
> (Layer A), then under a counterfactual mapping of each artifact's existing prose into the
> new schema (Layer B) — with no comparator arm and no claim about what the author would
> then have done.

## Preregistered predictions and their falsifiers

**P1 — Layer A (gates as they actually ship) fires ≈ 0 times.**
Both new gates are opt-in and keyed on files (`graph.yaml`, `sealed_holdout.yaml`) that no
experiment created before 2026-09-12 has. Prediction: **0 firings across all 23 artifacts**,
excluding the 2 `graph.yaml` replay entries Cycle 1 itself added.
*Falsified if:* any firing occurs on a pre-2026-09-12 artifact. That would mean my model of
where these gates apply is wrong, which is more interesting than the count itself.

**P2 — Layer B (counterfactual schema-fill) fires on a MINORITY, not a majority.**
Mapping each historical artifact's existing prose (verdict → `status`, Kill Analysis →
`kill_reason`, Revival Condition → `revival_condition`) into the new schema and then running
`check_status_conditional_fields`: prediction **< 50% of KILLED/REJECT-class artifacts flag**.
Reasoning: `reject_gate_guard.py` has enforced non-empty Kill Analysis since 2026-06-24, so
most post-June records should already satisfy the new check; the flags should concentrate in
pre-June records.
*Falsified if:* ≥ 50% flag, which would mean the existing `reject_gate_guard.py` is much
weaker in practice than its own enforcement claim.

**P3 — the sealed-holdout gate has ZERO retrospective power, by construction.**
No historical experiment separated a search-oracle from a one-time final check, so there is
nothing for the invariant (internal↑ + held-out↓) to evaluate. Prediction: **0 artifacts
carry both deltas**, therefore 0 evaluable invariant checks.
*Falsified if:* any historical artifact records both an internal and a held-out delta in a
form the gate can parse.

**P4 — the DAG's dead-end-detection has near-zero retrospective power on THIS corpus.**
The `null_results/INDEX.md` grep-before-work protocol already existed; a machine-readable
DAG adds power only where a branch relationship was never written down at all. Prediction:
**≤ 2 cross-experiment relationships exist in prose that no INDEX entry already records.**
*Falsified if:* ≥ 3 such unrecorded relationships are found.

**Meta-prediction (the one I most expect to be wrong):** the aggregate retrospective signal
will be WEAK — these mechanisms are prospective by construction, and a retrospective replay
mostly measures "did past records meet a standard that did not exist yet", which is close to
tautological. If that is what comes out, the honest verdict for Part 1 is
`NEEDS-MORE-DATA`, and the real evidence has to come from Part 2.

## What this result does NOT mean (written before results)

1. Does **NOT** establish that the Cycle-1 mechanisms cause fewer false promotions or fewer
   repeated dead ends. That is the causal question ruled non-identifiable above.
2. Does **NOT** mean a firing gate would have changed the author's decision. A gate that
   fires surfaces a signal; whether a human/agent then acts differently is unmeasured here.
3. Does **NOT** generalize beyond this repository's own 23 artifacts, which were produced by
   a single author under a single evolving methodology — the opposite of an independent sample.
4. Does **NOT** support "the mechanisms are unnecessary" if counts come out low. Low
   retrospective firing on records that predate the mechanism is the EXPECTED result (P1),
   not evidence of uselessness — a smoke detector installed today does not retroactively
   detect last year's fires.

## Claim Entropy (Perelman)

| Source | Count | Note |
|---|---|---|
| Unsupported HIGH claims | 0 | no HIGH claim is made; everything is a count |
| Hidden assumptions | 1 | that prose→schema mapping in Layer B is faithful; mitigated by recording the mapping per artifact so it is auditable |
| Missing negative controls | 0 | see controls below |
| Ambiguous definitions | 0 | "fires" = the gate's own function returns a failure/flag |
| Unresolved blockers | 0 | |

**Negative control:** `experiments/_template/` must produce ZERO firings in both layers — it
is a placeholder, not a result. If the replay flags the template, the replay itself is
broken, not the corpus.

**Positive control:** `experiments/20260728-osa-fl-protocol-vs-standard-analysis/` is a real
REJECT with a real, non-empty Kill Analysis and Revival Condition (verified during Cycle 1
when its `graph.yaml` was written). Layer B must NOT flag it. If it does, the replay's
mapping logic is wrong.

— END OF PREREGISTRATION —
