# substrate_gate.md — [EXPERIMENT-ID]

_Step 2a. Run BEFORE any control or test (Steps 3-6). Answers one question that has
nothing to do with whether the claim is true: can the current infrastructure even test
it honestly right now? "Test could not run" and "test ran and disproved the claim" are
different facts — this gate keeps them from being conflated. See
`rules/falsification-ladder.md` § Step 2a._

## Checklist (all must PASS for READY)

| Check | What it verifies | Result | Notes |
|---|---|---|---|
| Environment | Versions/platform pinned; run is reproducible, not "worked once" | [ ] PASS [ ] FAIL | |
| Code provenance | Source of every function/constant the test depends on is known | [ ] PASS [ ] FAIL | |
| Dependencies | Lockfile or equivalent pinning exists | [ ] PASS [ ] FAIL | |
| Exactness | Critical verdict doesn't hinge only on floating-point rounding | [ ] PASS [ ] FAIL | |
| Test-harness sanity | The testing apparatus itself has a working smoke test (NOT the scientific controls of Steps 3-4 — this is a check on the harness) | [ ] PASS [ ] FAIL | |
| Artifacts | Output is persisted to a file/log, not asserted only in conversation | [ ] PASS [ ] FAIL | |
| Security/integrity | Protective hooks/guards run as documented, don't silently no-op, block, or distort the run | [ ] PASS [ ] FAIL | |
| Clean state | Uncommitted changes and experiment scope boundary are both known | [ ] PASS [ ] FAIL | |

## Verdict

- [ ] `READY` — proceed to Step 3
- [ ] `BLOCKED-INFRASTRUCTURE` — substrate itself can't run the test (broken deps, wrong
      hook wiring, missing tool). Fix substrate, re-run this gate, then retry Step 3.
- [ ] `UNTRUSTED-ENVIRONMENT` — substrate runs, but something can't be trusted
      (unverified provenance, unknown-scope uncommitted changes). Fix trust/provenance,
      re-run this gate, then retry Step 3.

**If BLOCKED-INFRASTRUCTURE or UNTRUSTED-ENVIRONMENT:** the claim's evidence status is
UNCHANGED — do not record FAIL or REJECT because of this verdict. State what's broken:

_[describe the specific substrate problem — not a claim about the hypothesis]_

## Fix log (only if not READY on first pass)

| Attempt | Problem found | Fix applied | Re-run result |
|---|---|---|---|
| 1 | | | |
