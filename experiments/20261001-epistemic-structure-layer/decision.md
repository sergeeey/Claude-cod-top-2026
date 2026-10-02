# decision.md — 20261001-epistemic-structure-layer

## Verdict

- [ ] PROMOTE
- [ ] REPEAT
- [ ] REJECT
- [x] ARCHIVE — the three tools pass their own tests and stay in `scripts/` as utilities; the stronger claim
  (they show structure in real, actually-filled artifacts that current artifacts do not) could NOT be tested:
  every real-data measurement was `NO_HEADROOM` by construction (see `ceiling.md`), so no skill text, rule or
  hook is changed. This is a stop-verdict, not evidence against the idea. Revisit on the prospective
  `ledger.md` triggers, not on a date.

## Result Classification

- [ ] 🥈 Silver — not claimed: the transferable technique (fix the extraction rule before computing, count
  independent units) is already in this stack; this experiment applied it but did not extend it.
- [x] 🪨 **Stone** for the main question (uninformative by construction). Side value: running the generator on a
  real checkpoint exposed a fence-blind splitter, and an independent review found 11 more defects.

## Evidence Summary

| Check | Result |
|-------|--------|
| Tool correctness (unit + property + mutation) | PASS on their own tests — `[VERIFIED-SYNTHETIC]`. A review the same day found and reproduced 11 more defects (decode radius, greedy cost-0, parser drops, only-AND flag, ABSTAIN literal, control-not-run status, ...); all fixed with regression tests that fail on the old code. The review was not exhaustive |
| P1 EQR, 2 independent subjects | `NO_HEADROOM`: lakes floor == observation for any data of that shape (4 of 5 probe rows constant); install observed 0 so p = 1 by construction. Extraction choices (negative-control series only, FP by any mechanism) removed the variation that could separate variants |
| P3 ECSA | `NO_HEADROOM`: 0 of 2 claims have OR structure; AND-only gives kappa 1 everywhere. The "hit" C4 is implied by the edge C4 -> C5 (tautological). E2's 4 other computed-minus-declared atoms (T1,T2,T3,T5) are the same mechanical type. E2 is not a `claim-decomposer` output (outside the preregistered population) and its source file is untracked in the main repo, so it cannot be reproduced from this branch |
| P4 Checkpoint Fidelity, 2 checkpoints | distribution: control OK under the preregistered oracle. boyko: the preregistered oracle (`2\+`, document says "2+ PCs") graded the answer "2" WRONG, which makes the control INSTRUMENT_INVALID; it became valid only after I relaxed the regex to `2` post hoc. So P4 rests on 1 checkpoint cleanly and on 2 only after a disclosed post-hoc fix. 0 divergences on `reorder_sections`; ceiling on explicit lookup questions |
| P5 Narrative Poison, 1 input | 5/5 FALSIFIED incl. both authority framings; ceiling, input answer-bearing; no inference |
| P6 FIS-lite | NOT STARTED (conditional on P3 in the ledger; P6 itself is independent in `claim.md`, so this is a scope choice, not a criterion) |
| Not run, with reasons | checkpoint `pr106` and variant `reorder_list_items`: dropped to stay inside the 2.6M stop at the time of planning (the cost per run, ~166k, was only known after the pilot); in hindsight both fit, and `pr106` holds order-sensitive questions, so the omission favours a null on P4. Second Narrative Poison input: not run, ceiling expected |
| Skeptic verdicts on this write-up | two independent skeptic passes (artifact and code), both NEEDS_WORK; artifact pass `[WEAKENED]`: ARCHIVE honest, "not met"/"correct" overclaimed. Corrections applied in this file, `ceiling.md`, and the benchmark report |

## Rationale

Every preregistered park criterion for a module fired or the module's precondition failed, so by the rules written
before the runs: EQR stays a utility (no text change to `hypothesis-arbiter`/`evolve-solution`/CDT), ECSA stays a
utility (no `claim-decomposer` change), FIS-lite is not built, `memory-protocol.md` keeps Checkpoint Fidelity as
prose. The only integration made is the already-committed advisory rows in `experiments/_template/controls.md`,
which do not enter the No-Collapse count. Where data was scarce the result is stated as scarcity, not as a verdict
on the idea.

## Surgery log

| old_component | failure_mode | evidence | replacement | why_valid | forbidden_claims | new_tests |
|---|---|---|---|---|---|---|
| `verdict_invariance._sections` (regex split) | `#` shell comments in fenced code taken for headings; reordered checkpoint had broken fences | generator run on `2026-05-06_distribution-sprint-step2-done.md` | fence-aware line scan | two regression tests fail on the old code (verified by stashing) | cannot claim earlier unit tests covered fenced documents | `test_hash_lines_inside_code_fences_are_not_headings`, `test_tilde_fence_is_also_respected` |

## What this does NOT mean

1. Does NOT mean equivalence classes, cut sets or invariance checks are useless: n = 2 independent subjects per
   module, on artifacts that mostly lack the structure these tools need.
2. Does NOT show verdicts are authority-insensitive (the one input was a ceiling).
3. Does NOT establish any effect on conclusion quality (causal question not identifiable retrospectively).

## Skeptic Concerns and Resolution

Not yet collected. Before opening a PR: context-blind `skeptic` pass on `claim.md` + this file + `metrics/`; if the
`reviewer` cap is closed, name the fallback in the PR body (rules/doubt-driven-development.md).

## Side findings (recorded, not acted on)

- `.claude/checkpoints/2026-07-22_boyko-agent-v2-autonomous-hardening.md` names `dff76c5` as the SEC-04 fix; git
  says the fix is `889c1f5` (merge `10eafd4`).
- `tests/test_pre_compact.py::TestTrimOldEntries::test_keeps_recent_section` hard-codes 2026-07-01 and fails once
  that date is older than 90 days (spawned as a separate task).

## Review findings, status (2026-10-01; two skeptic passes; the code pass had no shell, so each item was reproduced here first)

| # | Finding | Status |
|---|---|---|
| 1 | `decode`: radius used the global closest pair, so an unrelated close pair made every observation UNCORRECTABLE | reproduced, FIXED (`d_best`) + regression test |
| 2 | `compare_verdicts`/`fidelity_report`: control never run still reported `OK` | reproduced, FIXED -> `INSTRUMENT_UNVALIDATED` |
| 3 | skeptic family: an earlier bracket tag beat a later `VERDICT:` line | reproduced, FIXED (last token by position wins) |
| 4 | parser dropped rows containing `N/a` and typos like `C/I`; duplicate test ids accepted | reproduced, FIXED (only all-placeholder rows are skipped; duplicates rejected) |
| 5 | greedy `identify` ignored a free (cost 0) test that separated a remaining pair | reproduced, FIXED |
| 6, 7 | `floor --trials 0` crashed; `place_candidate` ignored unknown test ids | reproduced, FIXED |
| 8 | `only_and_logic` true for `A & (B \| C)` (would under-count `claims_with_or_structure`) | reproduced, FIXED; the two real subjects were pure AND, their numbers are unchanged |
| 10 | `eig --merge-equivalent` skipped the name check and crashed | reproduced, FIXED |
| 11, 12 | `score_answers` literal `ABSTAIN` graded WRONG, hedged answers graded ABSTAIN, non-string crashed; `reorder_sections` not an involution without a final newline | reproduced; semantics documented instead: a document without a final newline is padded, involution holds for newline-terminated documents |
| 9 | decomposer mode: status `cited` weighted like `unverified`; `--nodes` ignored with `--decomposer` | NOT fixed: affects only the `[WEAK]` ranking heuristic; open |
| 13 | two tests that cannot fail (CLI verdict in a set of both values; mutants defined inside the test file) | NOT fixed; open |
| design | skeptic-noted asymmetries (control passes on a token change inside one class; `rename_identifiers` merges H/C/T prefixes) | recorded, not changed |
