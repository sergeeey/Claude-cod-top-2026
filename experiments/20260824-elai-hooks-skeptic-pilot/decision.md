# decision.md — 20260824-elai-hooks-skeptic-pilot

**STATUS: RESOLVED** — fixed, merged, re-verified on `main`.
PR [#261](https://github.com/sergeeey/Claude-cod-top-2026/pull/261), merged
2026-08-23T21:07:54Z. Full repo suite re-run on `main` after all three pilot
PRs merged (2026-08-24): **2767 passed**, 1 pre-existing unrelated
machine-path-dependent failure (confirmed unrelated across every re-run this
session). No open items remain for this experiment.

## Verdict: REJECT (claim as originally worded) → FIXED, re-verify PASS

The claim "compute_independence() and compute_mdr() have no bug that produces a wrong
score or wrong tier for any input consistent with their documented contract" is
**falsified as originally stated**. A real bug was found, fixed, and closed with a
regression test in this same session.

## What happened (Phase-1 pilot results)

Two Skeptic Step 8a invocations ran in parallel on the identical claim + identical code,
context-asymmetric (no session history, no reasoning chain) — differing only in how the
falsification-request prompt was worded (JudgeSense-style paraphrase probe):

| | Variant A (formal register) | Variant B (paraphrased register) |
|---|---|---|
| Verdict | **WEAKENED** | **FALSIFIED** |
| Found the real bug? | No | **Yes** |
| Found something else | Contract-wording self-contradiction in my own prompt text ("FAIL <0.80" vs WARN 0.50-0.79 overlap — my typo, not the code's) + 2 narrow libraries-dimension edge cases (dotted package names, non-`==` version specifiers) | — |

**The verdicts disagreed.** This is itself a finding, not noise: it's a live, in-repo
instance of exactly what JudgeSense (arXiv:2604.23478, cited Tier1 in the 2026-08-24
Falsification Audit) predicts — a judge's output is sensitive to how the same
falsification request is phrased, even holding claim and code fixed. Neither variant
was "wrong" to disagree; Variant B's specific phrasing ("walk through what the code
would literally compute for your example, step by step") happened to prompt the
trace that surfaced the real defect; Variant A's more abstract phrasing did not.

**Abstention tracking (AbstentionBench-style):** neither invocation abstained
(`NEEDS-REAL-DATA`). Both committed to a verdict. n=2, first entries toward the
Phase-0 outcomes ledger the audit's roadmap requires (`skeptic-triggers.md`'s own
ledger is still otherwise empty).

## The real bug (Variant B, independently reproduced)

`hooks/mutation_tracker.py:111` (pre-fix): `m.get("detection_expected", True)` —
a mutation entry with a missing/unparseable `detection_expected` key was silently
promoted into the MDR denominator as if it had been explicitly flagged `true`.

**Independently reproduced** (not just trusted from the agent — audit-verification-gate.md
requires this):
```
mutations = [{"id":"M-001","detection_expected":True}, {"id":"M-002"}]
results   = [{"id":"M-001","detected":True}, {"id":"M-002","detected":False}]
compute_mdr(mutations, results) -> rate=0.5, verdict=WARN, blind_spots=['M-002']
```
Expected per spec ("scored" = mutations *flagged* `detection_expected: true`):
`M-002` should be excluded entirely → rate=1.0, verdict=PASS, blind_spots=[].

**Reachability check** (per audit-verification-gate.md — is a dangerous default ever
hit in real usage?): `experiments/_template/mutation_suite.yaml` requires every
mutation entry to explicitly set `detection_expected: true|false`; a user copying the
template and adding a new mutation row without filling that field reaches this exact
code path. Real, not theoretical.

**Fix applied:** `hooks/mutation_tracker.py:111` default changed `True` → `False`,
with a `# WHY` comment pointing at this pilot. Regression test added:
`tests/test_mutation_tracker.py::test_missing_detection_expected_key_not_promoted_to_expected`.

**Verification:** `pytest tests/test_mutation_tracker.py tests/test_independence_scorer.py -q`
→ 53 passed (52 existing + 1 new).

## Secondary findings (not acted on this pilot — logged only)

1. `independence_scorer.py`'s `libraries` Jaccard tokenizer only recognizes `pkg==major`
   syntax; dotted package names (`zope.interface==5.0`) and non-`==` specifiers
   (`numpy>=1.26.0`) fall through to a bare-name/raw-string fallback that can either
   over- or under-count similarity depending on the exact string shape. Contract is
   silent on whether PEP 440/503-style specifiers are in scope, so this is **not**
   ruled a falsification — logged as a real narrow gap, Minimal-Relaxation discipline
   says fix one thing at a time, not bundle it into this pilot's fix.
2. `compute_mdr`'s `NO_EXPECTED_DETECTIONS` return value is a legitimate verdict not
   enumerated in the claim's PASS/WARN/FAIL tier set — claim-wording completeness gap,
   not a code defect.

## Kill Analysis (per Falsification Ladder's Minimal Relaxation Rule)

- **What was killed:** the specific claim "no bug ... for any input consistent with
  the documented contract" — false as stated, one concrete counter-example existed.
- **What was NOT killed:** the core independence/MDR *algorithms* (weighted-dimension
  sum, Jaccard libraries, PASS/WARN/FAIL/HIGH/MEDIUM/LOW thresholds) — all traced
  correct by both skeptic variants and by 53/53 passing tests post-fix. The defect was
  narrowly in one `.get()` default, not the algorithm design.
- **Relaxation:** claim re-stated post-fix as "... with no *known* bug ..." — the
  original absolute "any input" wording is retired; a new claim would need its own ID
  if re-tested against a broader input space (e.g. property-based/fuzz testing of
  `_parse_results`, which this pilot did not attempt).

## Phase-1 items actually piloted vs. not

| Phase-1 item | Status this pilot |
|---|---|
| JudgeSense-style paraphrase probe on Skeptic | **Piloted — worked as designed**, caught a real disagreement between variants |
| AbstentionBench-style abstention tracking | **Piloted** — n=2, 0 abstentions, logged as first ledger entries |
| DeepConf-style confidence pre-filter | **Not piloted** — no token-level logprob access via the Agent tool in this harness. Not simulated. |
| GraphRAG for one retrieval use-case | **Not piloted** — requires graph-construction infra out of scope for a single-turn pilot |

## Next action

Nothing further required to close this pilot. If a second pilot is wanted: run the
same paraphrase-probe pattern on ≥8 more real claims to start giving `skeptic-triggers.md`'s
outcomes ledger enough entries to move its 2.5x/`.000`/"≥5 tests" constants from
`[WEAK]` to a calibrated number (Phase 2 of the roadmap).
