# decision.md — 20260912-research-evidence-loop-minimal-extension

## Verdict

- [ ] PROMOTE
- [ ] REPEAT
- [x] **NEEDS-MORE-DATA** — infrastructure verified sound and non-regressive;
      whether it changes real research outcomes for the better requires
      real-task dogfood, explicitly deferred to a separate Cycle 2 (per the
      user's own explicit choice, made before implementation started, to
      avoid fabricating a dogfood result against tasks that don't exist yet).
- [ ] REJECT
- [ ] ARCHIVE

## Evidence Summary

| Check | Result |
|-------|--------|
| Full suite (all tests, incl. new) | PASS — 3560 passed, 3 skipped, 2 xfailed, 0 failures |
| ruff / mypy | PASS — both clean (`hooks/sealed_holdout_guard.py`, `hooks/promotion_gate_guard.py`, `hooks/independence_scorer.py`, `scripts/check_experiment_graph.py`, `scripts/promotion_score_observer.py`) |
| Architecture gates (`check_architecture.py`, `sync_doc_counts.py`, `gen_hook_matrix.py`, `sync_plugin_hooks.py`, `check_experiment_graph.py`) | PASS — all `--check` green |
| Unit tests, new mechanisms | PASS — 23 (graph checker) + 26 (sealed-holdout guard) + 13 (priority observer) + 13 (promotion-gate 6th condition, `TestCheckSealedHoldout`) + 11 (independence detail) = 86 new tests |
| Mutation test | PASS — disabling each of the 6 branches added to `_check_sealed_holdout` (template-stub exclusion, `opened_by_stage` check, both-deltas-required, `<=0` boundary, import-fallback degrade, holdout_ref-unset-post-consumed) fails exactly its own corresponding test, 0 others — verified via a scripted mutate/run/restore loop, not by inspection |
| Historical replay | PASS — 2 real experiments (`20260824-quote-splitting-sweep`, `20260728-osa-fl-protocol-vs-standard-analysis`) validate cleanly against real, not synthetic, cross-experiment relationships; caught and fixed a real bug in the checker's own id-mismatch logic in the process |
| Leakage test | PASS — an oversized `holdout_ref` is rejected by length; a same-length-but-wrong-shaped value (spaces, no hash/path structure) is separately rejected by `_HOLDOUT_REF_SHAPE_RE`; an `artifact_refs` entry that is absolute or escapes the experiment directory via `../..` is rejected by resolved-path containment |
| Consumption/re-seal test | PASS — `hooks/sealed_holdout_guard.py` denies the re-seal shape (keyed on `holdout_ref` alone, not `holdout_ref`+`sealed_at`) and the invalid-consumption shape, survives an inline YAML comment on the same line as `consumed:`, and recognizes YAML 1.1 boolean synonyms (`yes`/`on`) the same way the offline `yaml.safe_load`-based checker does |
| Telemetry isolation | PASS — `promotion_score_observer.py` touches only its own new log file, never `graph.yaml` |
| Performance | PASS — `check_experiment_graph.py --check` runs in ~0.17s against the full `experiments/` tree |

**Skeptic result:** RAN, as a fallback — not skipped. The `reviewer` agent's
Evaluator-Optimizer cap was closed (3 consecutive non-LGTM verdicts) at the
point this artifact-level review was needed, so per
`rules/doubt-driven-development.md` § Independent Review Fallback Policy,
`skeptic` + `sec-auditor` reviewed the implemented code in parallel (Trigger
3 applies: this touches PreToolUse hooks / promotion gating). Both findings
sets were largely confirmed after independent tool-verification (not taken
on either agent's word) and fixed in this same PR:
- `hooks/lib/runtime.py`'s `hook_main()` called `os._exit()` without
  flushing stdio first, so a crashing `fail_closed=True` hook's deny JSON
  could be silently dropped by Claude Code's buffered pipe — a pre-existing,
  cross-cutting bug affecting every PREVENT-class hook, not scoped to this
  PR's new code. Fixed and shipped separately as its own PR (#443, merged),
  per this repo's "one fix per PR" convention.
- `hooks/sealed_holdout_guard.py`: re-seal detection keyed on both
  `holdout_ref`+`sealed_at` let an author bump the author-editable
  `sealed_at` and slip past undetected — re-keyed on `holdout_ref` alone.
  An inline YAML comment on `consumed: true` silently defeated `_is_true()`
  for both this hook and `promotion_gate_guard.py`'s float parsing — fixed
  once at the shared extraction point (`_strip_inline_comment`). YAML 1.1
  boolean synonyms (`yes`/`on`) were not recognized, creating a real
  disagreement with the offline `yaml.safe_load`-based checker. A malformed
  `tool_input` payload could crash the relevance check before the file-path
  gate ran, which combined with the `runtime.py` fix above would have made
  this hook start denying arbitrary unrelated Edit/Write calls.
- `hooks/promotion_gate_guard.py`'s `_check_sealed_holdout`: silently PASSED
  an unfilled `experiments/_template/` stub copy (fixed to treat as not
  applicable), silently PASSED `consumed=true` with `holdout_ref` never set,
  silently PASSED any `opened_by_stage` despite the docstring's own claim
  that only VERIFY counts, silently PASSED when only one of the two deltas
  was recorded, and used a strict `< 0` boundary that let `held_out_delta ==
  0` (the same Goodhart signature) through. All six independently
  mutation-tested (see above).
- An `ImportError` on `sealed_holdout_guard`'s functions (a partial live
  deploy) crashed `promotion_gate_guard.py` at import time, disabling all 5
  mandatory Perelman conditions, not just this opt-in one — sec-auditor
  flagged this as `[UNKNOWN]`; skeptic separately guessed it would fail
  closed (deny every PROMOTE), which was independently verified WRONG via a
  constructed reproduction — the real behavior was fail OPEN (silent,
  uncaught `ModuleNotFoundError`, exit 1, empty stdout), arguably worse.
  Fixed via `try/except ImportError` + a `None`-check fallback.
- `scripts/check_experiment_graph.py`'s `artifact_refs` handling used a
  naive `(exp_dir / artifact).exists()` that let an absolute path or a
  `../../..` escape resolve outside the experiment's own directory — fixed
  via resolved-path containment. A holdout-ref shape guard (regex, not a
  secret scanner) was added alongside the existing length ceiling.
- Not fixed, named explicitly instead of silently dropped: sec-auditor's
  observation that a delete-then-recreate sequence via separate Write calls
  is not caught by this PreToolUse-Write-only comparison (no persistent
  "was this file consumed" state outside the file's own content) — a real,
  narrow limitation, out of scope for this cycle.

## Rationale

Gate 0 reconnaissance (done before any code, per the motivating ТЗ's own
mandatory first step) found that most of the requested capability already
existed under different names — closer to done than the ТЗ assumed. The real,
narrower gaps were: no machine-readable graph spanning experiments (only
prose tables inside individual `decision.md` files); no separation between
"the oracle used for search" and "a provably untouched final check"; no
persisted per-dimension independence breakdown (computed, but discarded);
and no logging infrastructure for a priority-score heuristic the motivating
ТЗ itself calls unvalidated. Each gap was closed with the smallest addition
that reused existing machinery directly (the same JSON-Schema-subset
validator and cycle detector `check_architecture.py` already has; the same
shadow-log-then-replay discipline `verdict_logger.py`/`false_pass_rate.py`
already dogfood) rather than new machinery.

## If REPEAT / NEEDS-MORE-DATA: What Changes Next

- **Cycle 2** (separate, later session): real-task dogfood across the three
  task types the motivating ТЗ specifies (scientific hypothesis / engineering
  / failure investigation), an A/B comparison (current methodology vs.
  +Cycle-1 mechanisms), a false-promotion/false-kill/repeated-work count, and
  only then a genuine PROMOTE/REJECT verdict on whether these mechanisms
  actually help.
- Until Cycle 2 runs, `graph.yaml`/`sealed_holdout.yaml`/`priority_factors`
  remain fully optional — no experiment is required to adopt them.

## Skeptic Concerns and Resolution

Design-time concerns (status-vocabulary reconciliation, dogfood-phasing
scope, priority-formula scope) were raised and resolved during the
Gate-0/plan-approval stage and are recorded in the approved plan file, not
repeated here. The artifact-level skeptic + sec-auditor review that ran
after implementation (see Evidence Summary § Skeptic result above) found
real bugs, all responded to per the FALSIFIED → Fix/Accept/Dismiss matrix
(`falsification-ladder.md` § Step 8a): every concern was **Fixed** in this
same PR except two, handled as follows:
- The `hooks/lib/runtime.py` stdio-flush bug → **Fixed**, but as its own
  separate PR (#443, merged) rather than bundled here, since it is
  pre-existing and affects every PREVENT-class hook in the repo, not just
  this cycle's new code — "one fix per PR" convention.
- The delete-then-recreate PreToolUse-Write-only limitation → **Accepted
  limitation**, documented explicitly above rather than fixed, as a narrow,
  named gap rather than a silently dropped concern.

No concern was Dismissed outright — both agents' findings were independently
tool-verified before being accepted (including one case, skeptic's guess
about the import-coupling failure mode, that was verified WRONG via a
constructed reproduction and corrected rather than taken on trust).
