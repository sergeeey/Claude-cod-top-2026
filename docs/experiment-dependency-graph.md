# Experiment Dependency Graph, Sealed Holdout, and Stage Tracking

> Machine-readable extensions to the existing experiment-tracking methodology —
> a `graph.yaml`, not a new framework.

## Why this exists

`experiments/_template/decision.md` already tracks branch-level state in prose:
the "Hypothesis Generation Mode" table (`New Branch | Parent Null Result |
Surviving Assumption | Imported Mechanism | Revival Condition | Cheapest Test |
Initial Status`) and the "Rescue Review" table (`Final Status: hard_killed |
killed | parked | weak_alive`). That is real, working state — but it lives only
as prose inside ONE experiment's own `decision.md`. Nothing lets a script ask,
across the whole `experiments/` tree:

- What's currently ACTIVE?
- What does killing experiment X unblock?
- Does this experiment depend on something that doesn't exist?

This gap — a machine-readable graph spanning experiments, not a new state
machine — is what `experiments/<id>/graph.yaml` closes. It is **optional**: an
experiment with no cross-experiment relationship worth declaring does not need
one. Absence is not an error.

## `graph.yaml`

Copy `experiments/_template/graph.yaml` into your experiment's own directory
only when you have a real `parent_ids`/`requires`/`blocks`/`evidence_for`/
`evidence_against` relationship to declare. Validated by
[`scripts/check_experiment_graph.py`](../scripts/check_experiment_graph.py)
against [`experiments/graph.schema.json`](../experiments/graph.schema.json) —
reusing `scripts/check_architecture.py`'s own stdlib-only JSON-Schema-subset
validator and cycle detector directly, not a reimplementation.

```bash
python scripts/check_experiment_graph.py            # human report
python scripts/check_experiment_graph.py --check    # CI mode
```

Checks: schema validity; the `requires`+`blocks`+`parent_ids` dependency graph
is acyclic; no dangling reference (a target must be a real `experiments/<id>/`
directory, or — for `evidence_for`/`evidence_against` — a real `null_results/`
or `parked/` entry too); every `artifact_refs` path exists.

### Status crosswalk

`graph.yaml`'s `status` (`ACTIVE | BLOCKED | KILLED | PROMOTED | VERIFIED`) is
the **one machine-queryable source** for cross-experiment status. It does not
replace `experiment.yaml`'s own `status:` or `decision.md`'s Rescue Review
`Final Status:` — those stay exactly where they are, human-authored. See the
crosswalk table in `experiments/_template/decision.md`, next to Rescue Review,
for the authoritative mapping.

### Mode: EXPLORE / DEVELOP / VERIFY

`graph.yaml`'s `mode` field is the **first code-traceable record** either of
this repo's two existing stage concepts has ever had — stated honestly, not as
"hooking into existing enforcement" that doesn't exist:

- `/evolve-solution`'s 8-stage pipeline (Route → Intent → Oracle Adequacy →
  Falsification Contract → Variant Tournament → Red-Team → Evidence Gate →
  Null Result Ledger) sequences stages **within one command invocation**, with
  no persistent, cross-session state.
- `rules/research-methodology.md`'s 4-stage Research Stage Protocol (idea
  scouting / hypothesis shaping / claim promotion / paper release) is **pure
  prose** — that file itself claims its "Arbiter" lives in `CLAUDE.md`; it does
  not (checked directly, zero matches in either this repo's or the user's
  global `CLAUDE.md`). Neither existing lifecycle has any code enforcement of
  stage today.

Rough crosswalk, for filling `mode` consistently with whichever of the two you
are already thinking in:

| `graph.yaml` mode | `/evolve-solution` stages | Research Stage Protocol |
|---|---|---|
| `EXPLORE` | Route, Intent | idea scouting |
| `DEVELOP` | Oracle Adequacy, Falsification Contract, Variant Tournament | hypothesis shaping |
| `VERIFY` | Red-Team, Evidence Gate, Null Result Ledger | claim promotion / paper release |

Do not build a third orchestrator around this field. It is a label a script can
read, nothing more, until real use shows it needs to be.

## Sealed Holdout Gate

`docs/oracle-adequacy-gate.md`'s own Oracle-Adequacy Gate audits whether the
oracle a Variant Tournament repeatedly scores variants against is trustworthy.
It does **not** separate "the oracle used for search" from "a provably
untouched check used exactly once" — after enough adaptive search even a good
oracle degrades into training signal (Goodhart's law). That gap is what
`experiments/<id>/sealed_holdout.yaml` closes.

Hard rules (enforced, not just documented):

- `holdout_ref` is a reference (hash or external path) — **never** raw held-out
  data inline. `check_experiment_graph.py` rejects a value that looks like
  inlined data rather than a pointer (a cheap length heuristic — it cannot
  detect a short secret pasted inline, only an obviously-too-long blob).
- Opens once, at `VERIFY` stage. [`hooks/sealed_holdout_guard.py`](../hooks/sealed_holdout_guard.py)
  is a PreToolUse hard block (same shape as `hooks/weakened_test_guard.py`)
  that denies a "re-seal" — moving `opened_at` again while `sealed_at`/
  `holdout_ref` stay the same — and denies `consumed: true` with no
  `opened_at` (structurally invalid consumption).
- Promotion invariant, enforced by `hooks/promotion_gate_guard.py`'s 6th
  condition (opt-in — an experiment with no `sealed_holdout.yaml` is
  completely unaffected): `internal_delta` up **and** `held_out_delta` down ⇒
  `PROMOTE` is denied, no exceptions.

## Independence model

`experiments/_template/dependency_graph.yaml` + `hooks/independence_scorer.py`
already computed a full per-dimension breakdown (`model_family`,
`model_version`, `retrieval_snapshot`, `code_commit`, `libraries`, `dataset`,
`definition_of_metric`, `executor`) before this pass — it just discarded the
breakdown after computing it, keeping only the blended `independence_score`/
`independence_tier`. As of 2026-09-12 the hook persists that breakdown into a
new `dimension_detail:` list in the same file, and the template gained two
optional, human-filled fields: `artifact_hash` (Gate 1 / Artifact Identity —
so a later copy can be shown to be the same object) and `result` (what each
verification path actually concluded, once both have run).

## Adaptive Promotion Score — OBSERVE only

The formula `expected_value × falsifiability × information_gain ×
evidence_independence ÷ expected_cost` is an **unvalidated heuristic**. As of
this pass it ships as **logging infrastructure only**:

- `graph.yaml`'s optional `priority_factors` block holds five human-filled 0–1
  estimates — nothing computes them automatically.
- [`scripts/promotion_score_observer.py`](../scripts/promotion_score_observer.py)
  reads any `graph.yaml` with all five filled, computes the naive product/
  ratio, and appends a shadow record to `.claude/memory/promotion_priority_
  shadow.jsonl` — the exact "log a prediction, don't act on it, score later"
  discipline `hooks/verdict_logger.py` + `scripts/false_pass_rate.py` already
  dogfood for a different signal (suspected false-pass rate on reviewer
  verdicts), reused here rather than reinvented.
- Nothing reorders, blocks, or reweights anything based on this score. A later
  replay pass (comparing `proposed_priority` against real time-to-decision) is
  explicitly deferred until real records accumulate — the same gate
  `false_pass_rate.py`'s own `MIN_RECORDS_FOR_RATE` threshold already models.

## What this pass explicitly does NOT do

- Does not change `/evolve-solution`'s 8 stages or `research-methodology.md`'s
  4-stage protocol — both stay exactly as they are; `mode` is a new, separate,
  optional label.
- Does not migrate `experiment.yaml`'s own `status:` or `decision.md`'s Rescue
  Review table — see the crosswalk, not a replacement.
- Does not make `graph.yaml` or `sealed_holdout.yaml` required for any
  experiment tier. Both are opt-in additions for experiments that have a real
  cross-experiment relationship, or a real adaptive-search Goodhart risk, to
  declare.
- Does not run any real-task dogfood, A/B comparison, or promotion decision on
  this mechanism itself — that is a separate, later cycle (this cycle's own
  `decision.md`, once filled, records `NEEDS-MORE-DATA`, not `PROMOTE`).

## Known limitation — one `status` field is carrying two different questions

Added by PR C (2026-09-12), recorded here rather than fixed, because the fix is a
schema change that should be driven by more than the evidence below.

`status` currently answers *"what happened to this experiment?"*. The corpus shows
authors also needing to answer a second, genuinely separate question: *"what happened
to the branch/direction?"* — and working around the single field by hand. Three
independent pieces of evidence, arrived at from different directions:

1. **The KILLED family.** `hard_killed` and `killed` both crosswalk to `KILLED`, but
   the Rescue Review rules give them different futures: `killed` allows a NEW branch
   via the Minimal Relaxation Rule, `hard_killed` changes only on new theorem-level
   input. PR C corrected the `revival_condition` requirement that this flattening had
   made wrong, but the two states remain indistinguishable in the graph.
2. **`20260728-hypothesis-arbiter-taxonomy-pilot`** records TWO verdicts at different
   levels in its own Verdict section: `**Filing status: ARCHIVE → parked/**` and
   `**Claim-level result: REJECT**`. Neither is wrong; the four-word vocabulary simply
   cannot hold both, so `hooks/lib/verdicts.py` correctly refuses to pick one and
   reports `UNPARSEABLE`.
3. **`20260728-osa-fl-protocol-vs-standard-analysis`** has experiment verdict `REJECT`
   while its Rescue Review's surviving branch is `weak_alive` — the experiment is
   killed, the rescued weaker formulation is alive. Its `graph.yaml` says `KILLED`,
   which is true of the claim and false of the direction.

**Why this is NOT fixed here:** the obvious fix — a second optional field carrying the
Rescue Review `Final Status` — would be a new opt-in field, and the measured lesson of
this whole cycle (see `experiments/20260912-cycle2-retrospective-replay/`) is that
opt-in fields keyed on nothing that already exists reach ~0 coverage on real history.
Only 3 of 13 experiments have a Rescue Review section at all, and only 1 has it filled.
A field derived from a section almost nobody fills would repeat that mistake. The
honest next step is to find out whether the Rescue Review itself is under-used because
it is optional, or because it is only sometimes applicable — which is a question about
process, not schema.
