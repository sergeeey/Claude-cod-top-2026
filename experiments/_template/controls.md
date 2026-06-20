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
_Known-bad input that MUST be rejected / produce failure.
If this passes, the claim is weaker than stated — revisit the claim._

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

---

## Notes
_Any edge cases or boundary conditions observed during control runs._
