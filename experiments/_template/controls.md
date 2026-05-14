# Controls

**Experiment ID:** `<YYYYMMDD-short-slug>`

## Positive Control (known-good input → must PASS)

**Input:**
```
[exact input that should work correctly]
```

**Expected output:**
```
[what the system should return/do]
```

**Actual output:**
```
[fill in after running]
```

**Result:** PASS / FAIL

---

## Negative Control (known-bad input → must REJECT/FAIL)

**Input:**
```
[exact adversarial/invalid input that should be rejected]
```

**Expected behavior:**
```
[system should reject / error / block]
```

**Actual behavior:**
```
[fill in after running]
```

**Result:** PASS (correctly rejected) / FAIL (incorrectly accepted)

---

## Control Status

- [ ] Positive control: PASS
- [ ] Negative control: PASS (correctly rejected)

**If either control fails → STOP. Do not proceed to baseline/test. Fix the instrument first.**
