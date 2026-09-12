# decision.md — 20260912-cycle2-retrospective-replay

All counts below come from `metrics/run.json`, produced by `replay.py`. None were retyped
from reading files by hand.

## Verdict

- [ ] PROMOTE
- [x] **REPEAT** — Part 1 did its job (four concrete actionable findings, two of them
      defects in Cycle 1's own output, one of them in this replay's own instrument), but it
      cannot answer the causal question the motivating ТЗ actually asks, and its
      floor–ceiling arm returned `NO_HEADROOM` for the mechanism as shipped. The causal
      answer requires Part 2's prospective ledger; the headroom result requires acting on
      "what changes next" item 1 first.
- [ ] REJECT
- [ ] ARCHIVE

## Preregistered predictions vs. results

| # | Prediction (preregistered in `claim.md`) | Result | Status |
|---|---|---|---|
| P1 | Layer A (gates exactly as shipped) fires **0** times on pre-2026-09-12 artifacts | **0/12**; 0 artifacts have `sealed_holdout.yaml`, 2 have `graph.yaml` (both added by Cycle 1 itself) | **CONFIRMED** |
| P2 | Layer B (counterfactual schema-fill) fires on a **minority** of KILLED/BLOCKED records | **3/7 = 43%** (3/12 overall) | **CONFIRMED**, but narrowly — and see the manual audit below, which changes what the 3 mean |
| P3 | **0** historical artifacts record both deltas, so the holdout invariant has zero evaluable checks | **0** | **CONFIRMED** — but only after fixing my own falsifier's wording, see "Instrument defects" |
| P4 | **≤2** cross-experiment relationships exist in prose that `INDEX.md` does not already record | **3** (of 6 relationships found) | **FALSIFIED** |
| Meta | The aggregate retrospective signal will be WEAK and the honest verdict `NEEDS-MORE-DATA` | Partly right (Layer A is literally zero), partly wrong (P4 falsified; 3 actionable defects found) | **PARTLY FALSIFIED** |

**Controls:** negative (`experiments/_template/`) PASS — never fired in either layer.
Positive (`20260728-osa-fl-protocol-vs-standard-analysis`, a known-good REJECT) PASS — not
flagged. Both controls behaved as preregistered, so the instrument discriminates.

## Floor–Ceiling Interval (FL Step 4a) — and it changes the headline

Added after the first write-up, because `hooks/ceiling_gate_guard.py` fired on this very
file and was right: a firing count means nothing without knowing what a mechanism-free
baseline already achieves.

**Floor arm — "mechanism removed":** `hooks/reject_gate_guard.py` has enforced
Kill-Analysis completeness on REJECT records since 2026-06-24, i.e. before Cycle 1 existed.
Run over the same 12 artifacts it **applies to 1 of 12** and **fires 0 times**.

| Arm | Coverage | Firings |
|---|---|---|
| Floor — pre-Cycle-1 `reject_gate_guard.py` | 1/12 | **0** |
| Layer A — Cycle 1 **exactly as shipped** | 12/12 attempted, 0 applicable (no `graph.yaml`/`sealed_holdout.yaml` in history) | **0** |
| Layer B — Cycle 1's **rule** + a multi-format verdict parser written *today* | 11/12 parsed | **3** |

**Verdict on headroom, stated against my own interest:** as *actually shipped*, floor = 0
and Cycle 1 = 0. That is `NO_HEADROOM` — on this corpus the shipped mechanism separates
nothing from the baseline. The 3 firings in Layer B are **not attributable to Cycle 1's
code**; they are attributable to the multi-format verdict extractor I had to write for
this replay, which Cycle 1 did not ship. Conflating the two would have been exactly the
overclaim this gate exists to catch, and the first draft of this file did conflate them.

**What that implies, and it is the most useful thing Part 1 produced:** the scarce
capability here is not the `graph.yaml` schema — it is *being able to read the verdicts
that already exist*. A gate keyed on a new opt-in file reaches 0 of 12 real records; a
parser that understands the 4 formats already in use reaches 11.

## Instrument defects found DURING the run (and fixed before any number was reported)

This section exists because the first run produced a clean-looking result that was false.

1. **Silent parse failure masquerading as a clean corpus.** The first verdict extractor
   handled only the `_template`'s checkbox form and returned `None` for **6 of 12**
   artifacts. Layer B then reported `0/12 firings` — which read as "the corpus is clean"
   but actually meant "6 files were never parsed". Fixed by supporting all four verdict
   forms the corpus actually uses, and — more importantly — by reporting `unparsed_count`
   as its own number so an unparsed file can never again be silently counted as a passing
   one. Residual after the fix: **1/12 still unparsed**
   (`20260728-hypothesis-arbiter-taxonomy-pilot`), reported rather than hidden.
2. **My own `[AVOID×7]` keyword-vs-assertion error.** P3's falsifier was worded as "any
   artifact *records* both deltas", but the first implementation matched any artifact
   *mentioning* the field names. Its single hit was Cycle 1's own `decision.md`, which
   contains the field names because it *describes the gate*. Counting that as evidence
   would have been this repo's own catalogued anti-pattern, committed by the script whose
   job was to measure rigour. Fixed to require `field: <number>`.

Both defects point the same way: **a measurement instrument that cannot distinguish "no
signal" from "I failed to look" will report the former.**

## Finding 1 — the Cycle-1 schema conflates two different kinds of KILLED

Manual audit of all 3 Layer B firings (a machine flag is a hypothesis, not a finding —
`audit-verification-gate.md`):

| Artifact | Flag | Verdict after reading the file |
|---|---|---|
| `20260701-revive-session-save` | `revival_condition` missing | **FALSE FLAG — my mapping's fault.** Its verdict is `NEEDS-HUMAN`, and the file explicitly says "the premise was already false, so no REVIVE/KILL/PARK applies". Mapping `NEEDS-HUMAN → BLOCKED` invented a killed-branch status the record itself denies. |
| `20260824-elai-hooks-skeptic-pilot` | `revival_condition` missing | **TRUE by the letter, SCHEMA GAP by substance.** |
| `20260824-permission-policy-skeptic-pilot` | `revival_condition` missing | **TRUE by the letter, SCHEMA GAP by substance.** |

Both of the latter two carry a substantive, high-quality `## Kill Analysis`, and both have
the same shape: *"REJECT (claim as originally worded) → the underlying defect was then
FIXED"*. They have no revival condition because **there is nothing to revive** — the claim
was retired and the bug closed.

`falsification-ladder.md` already distinguishes `hard_killed` / `killed` / `parked` /
`weak_alive` in its Rescue Review. Cycle 1's `graph.schema.json` flattened all of that into
a single `KILLED`, and `check_status_conditional_fields` then demands `revival_condition`
for every one of them. On this repository's real history that rule is wrong for **2 of the
3** KILLED-class records.

**This is a defect in Cycle 1's own output, found by running it against reality** — exactly
what the dogfood was for. It was not visible from the tests, because the tests assert the
rule the schema declares, not whether that rule matches how verdicts are actually used.

## Finding 2 — `INDEX.md` has a real blind spot, and Cycle 1 walked straight into it

P4 was falsified for a concrete, checkable reason: **2 of 13 experiments are absent from
`experiments/INDEX.md` entirely** —

- `20260728-hypothesis-arbiter-taxonomy-pilot`
- `20260912-research-evidence-loop-minimal-extension` ← **Cycle 1's own experiment**

The established protocol (`grep null_results/INDEX.md` / `experiments/INDEX.md` before
starting work) can only surface what somebody remembered to index. A DAG derived from files
on disk cannot have that failure mode. This is the first *measured* evidence that the DAG
addresses a gap the existing prose index does not already cover — and the sharpest possible
illustration is that the cycle which built the DAG forgot to index itself.

## Finding 3 — the corpus is not format-consistent, and the EXISTING gate is blind to it

Four different verdict formats in 12 files, plus **2 verdict tokens that are not in the
Falsification Ladder's vocabulary at all** (`RESOLVED`, `NEEDS-HUMAN`). Any machine check
over this corpus must handle that or silently under-report — which is precisely what this
script's own first version did.

The floor arm shows this is not only my bug: `reject_gate_guard.py`'s own `_has_reject()`
recognises the REJECT marker in **1 of 12** artifacts. A gate documented as enforcing
Kill-Analysis completeness "since 2026-06-24" has, in practice, been inspecting **8% of the
corpus** — and reporting nothing about the other 92%, which is indistinguishable from
"everything is fine" to anyone reading its output.

This is the same class of defect as instrument defect #1 above, and as the Cycle-1
gap in Finding 1: **a check that cannot see an artifact reports silence, and silence reads
as approval.**

## Finding 4 — self-reference contamination in the measurement itself

Caught live while adding the floor arm: the moment this experiment's own `decision.md`
existed, it entered the corpus being measured. Artifact count went 12 → 13 and P4's
relationship count 6 → 12 — purely because the write-up *names the experiments it
discusses*. Left uncorrected, every edit to this report would have silently changed the
numbers this report states.

Fixed by excluding this experiment's own directory from its own corpus (`_EXCLUDED_DIRS`).
Worth recording because it is a general hazard for any repo-introspecting measurement, not
a one-off: **the report is also a file in the corpus.**

## What this result does NOT mean (carried from `claim.md`, unchanged)

1. Does **NOT** establish that the Cycle-1 mechanisms cause fewer false promotions or fewer
   repeated dead ends. That estimand was ruled non-identifiable at the L0 gate and is not
   answered here.
2. Does **NOT** mean a firing gate would have changed the author's decision.
3. Does **NOT** generalize beyond this repository's 23 artifacts, single-author, single
   evolving methodology.
4. The near-zero Layer A count is **NOT** evidence the mechanisms are useless — it is the
   preregistered expected result (P1). A smoke detector installed today does not
   retroactively detect last year's fires.

## What changes next

Ordered by what the floor–ceiling result says actually matters, not by what Cycle 1
happened to build.

1. **Highest value, and not what Cycle 1 shipped — a verdict parser that handles the 4
   formats already in use.** The floor arm shows both the pre-existing gate (1/12 coverage)
   and the shipped Cycle-1 gate (0/12 applicable) are blind to nearly the whole corpus,
   while a format-aware parser reaches 11/12. Coverage, not schema, is the binding
   constraint. Candidate: promote this replay's `extract_verdict()` into a shared helper
   and have `reject_gate_guard.py` use it.
2. **Fix Finding 1** (own PR): either split `KILLED` into the states
   `falsification-ladder.md` already names (`hard_killed`/`killed`/`parked`/`weak_alive`),
   or require `revival_condition` only for the genuinely-revivable ones. Do not "fix" it by
   relaxing the check into uselessness.
3. **Fix Finding 2** (own PR): add the 2 missing experiments to `INDEX.md`, and add a gate
   that fails when an `experiments/<id>/` directory has no `INDEX.md` row — the cheapest
   possible closure of that blind spot, independent of the DAG.
4. **Part 2** — the prospective Harness Change Ledger, which is where the causal question
   actually gets answered. Nothing in Part 1 substitutes for it.

**Note on ordering:** item 1 outranks the DAG and the sealed holdout on this evidence. That
is an uncomfortable result for Cycle 1 and is recorded as such rather than softened — Cycle
1's own verdict was `NEEDS-MORE-DATA`, and this is some of that data.

## Skeptic concerns and resolution

- *"3/12 is a suspiciously small number to draw conclusions from."* — **Accepted, and that
  is why the verdict is REPEAT, not PROMOTE.** No rate is claimed; `claim.md` deliberately
  defined the summary measure as absolute counts and set no MCID. The findings rest on
  per-artifact manual audit, not on the count.
- *"You fixed the instrument mid-run after seeing results — that is p-hacking."* —
  **Partly fair, and recorded rather than hidden.** The fixes were made because the
  instrument provably failed (6/12 unparsed is a defect by any standard, independent of
  which direction it moved the count), and both fixes made the instrument *stricter*, not
  more favourable: the P3 fix moved a hit from 1 to 0 against my own prediction's interest,
  and the parser fix moved firings from 0 to 3, i.e. it made the mechanism look *more*
  needed, which is the direction that flatters the thing being evaluated. That asymmetry is
  named here explicitly so a reader can discount accordingly. The preregistration commit
  (`fe2b787`) predates every result.
- *"Finding 1 is just your own mapping being wrong, not a real schema defect."* —
  **Partly true and separated above**: 1 of 3 flags IS a mapping artifact and is labelled
  as such. The other 2 stand on the artifacts' own text, which describes a
  falsified-then-fixed outcome with no revivable branch.
- *"`NO_HEADROOM` means the whole Cycle-1 mechanism is worthless."* — **Dismissed, with the
  reasoning stated rather than asserted.** Per `ceiling_gate_guard.py`'s own rule, a
  stop-verdict means *this experiment could not have been informative about the claim* — it
  is not evidence against the claim. `NO_HEADROOM` here is largely the restatement of P1,
  which was preregistered and confirmed: opt-in gates keyed on files that no historical
  artifact has cannot reach historical artifacts. What it legitimately does establish is
  narrower and still useful: **retrospective replay is the wrong instrument for measuring
  these particular mechanisms**, which is precisely why Part 2 is prospective.
