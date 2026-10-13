# controls.md — [EXPERIMENT-ID]

## Positive Control
_Known-good input that MUST produce the expected output.
If this fails, the test setup itself is broken — do not proceed._

**Input:**

**Expected output:**

**Command:**
```
[paste exact command here]
```

**Result:** [ ] PASS  [ ] FAIL

---

## Negative Control
_Known-bad input that MUST be rejected / produce failure from the system under test._
_**Result convention (same as Positive Control above — PASS always means "the control
confirmed the expected behavior," never a raw pass-through label):**_
_**Result: PASS** = the bad input WAS correctly rejected — the control did its job._
_**Result: FAIL** = the bad input was NOT rejected (leaked through) — the claim is
weaker than stated, revisit it._

**Input:**

**Expected output (rejection or failure):**

**Command:**
```
[paste exact command here]
```

**Result:** [ ] PASS  [ ] FAIL

---

## No-Collapse Tests
_Stability check (Perelman principle): result must not vanish under small, legal changes._
_If result disappears — it is an artifact, not a law._

| Test | What changes | Result | Notes |
|---|---|---|---|
| Data swap | different dataset, same type | [ ] PASS [ ] FAIL | |
| Noise injection | add σ = 10% noise | [ ] PASS [ ] FAIL | |
| Scale variation | ×0.1 and ×10 | [ ] PASS [ ] FAIL | |
| Convention flip | different normalization / baseline | [ ] PASS [ ] FAIL | |
| Negative control | known-false input | [ ] PASS [ ] FAIL | |
| Adversarial input | targeted hard examples | [ ] PASS [ ] FAIL | |
| Alternative tool | different tool for same task | [ ] PASS [ ] FAIL | |

_Minimum for Standard-Ladder: Data swap + Negative control + 1 other._
_Full-Ladder: all 7 required._

### Verdict-process sensitivity (advisory — NOT counted in the 7 above)
_Added 2026-10-01 (`experiments/20261001-epistemic-structure-layer`, W1). The seven tests above ask
whether the RESULT survives legal changes to data and method. These ask whether the VERDICT PROCESS
does: a verifier's verdict must not move under changes that carry no evidential content. Generate
the variants and score the verdicts with `scripts/verdict_invariance.py`; compare each variant with
the spread of IDENTICAL repeats (run `base` at least twice), not with a single baseline run.
Advisory only: no gate reads these rows — the result words are deliberately not PASS/FAIL, so
`promotion_gate_guard`'s No-Collapse counts are unchanged._

| Relation | What changes | Expected | Result |
|---|---|---|---|
| invariant | section order, premise order, identifier names, narrative removed | verdict class unchanged | [ ] HOLDS [ ] WITHIN-NOISE [ ] VIOLATED |
| invariant | expected answer stated vs hidden | unchanged | [ ] HOLDS [ ] WITHIN-NOISE [ ] VIOLATED |
| invariant | announced prior reviews ("confirmed" / "found an error") | unchanged — authority must not leak | [ ] HOLDS [ ] WITHIN-NOISE [ ] VIOLATED |
| monotonic | evidence weakened, or a required assumption deleted | class must not improve | [ ] HOLDS [ ] VIOLATED |
| kill | a required dependency replaced by a known-false one | reaches the reject class | [ ] HOLDS [ ] VIOLATED |
| control | document truncated to half | MUST diverge or abstain; if not, the instrument is blind — discard the rows above | [ ] CONTROL-OK [ ] CONTROL-FAILED |

---

## Notes
_Any edge cases or boundary conditions observed during control runs._
