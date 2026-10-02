# Claim under review

`compute_mdr()` (mutation detection rate) has no bug that produces a wrong rate, wrong verdict tier, or
wrong blind-spot list for any input consistent with its documented contract.

# Documented contract

- `mutations`: list of dicts `{"id": str, "detection_expected": bool}`. A mutation is "expected" only if it
  is explicitly flagged `detection_expected: true`.
- `results`: list of dicts `{"id": str, "detected": bool}`.
- "scored" = expected mutations that have a recorded result. rate = actually_detected / scored.
- Tiers: PASS if rate >= 0.80, WARN if 0.50 <= rate < 0.80, FAIL if rate < 0.50.
- rate is None with verdict PENDING when no results are recorded yet.
- blind_spots = ids of expected mutations whose recorded result is detected=False.

# Code (from hooks/mutation_tracker.py, with _MDR_PASS = 0.80 and _MDR_WARN = 0.50)

```python
def compute_mdr(
    mutations: list[dict],
    results: list[dict],
) -> tuple[float | None, str, list[str]]:
    """Return (rate, verdict, blind_spots).

    rate is None when no results are recorded yet.
    blind_spots: mutation IDs where detection_expected=True but detected=False.
    """
    if not results:
        return None, "PENDING", []

    det_map = {r["id"]: r.get("detected") for r in results if "id" in r}
    expected = [m for m in mutations if m.get("detection_expected", True)]
    if not expected:
        return None, "NO_EXPECTED_DETECTIONS", []

    blind_spots: list[str] = []
    actually_detected = 0
    for m in expected:
        detected = det_map.get(m["id"])
        if detected is True:
            actually_detected += 1
        elif detected is False:
            blind_spots.append(m["id"])
        # None → result not yet recorded, skip

    scored = len(expected) - sum(1 for m in expected if det_map.get(m["id"]) is None)
    if scored == 0:
        return None, "PENDING", []

    rate = actually_detected / scored
    if rate >= _MDR_PASS:
        verdict = "PASS"
    elif rate >= _MDR_WARN:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return round(rate, 3), verdict, blind_spots
```

# Task

Try to falsify the claim from the text above only. Do not use any tools, do not read files, do not run commands.
Reply with the verdict tag on the first line, exactly one of [CONFIRMED-REAL], [WEAKENED], [FALSIFIED],
[NEEDS-REAL-DATA], followed by at most 8 lines of justification. If you answer [FALSIFIED], give a concrete input
and the wrong output it produces.
