# Session Example: Systematic Debugging

A real-world example: a test fails after a dependency update.

## User Request

```
test_payment_process fails after updating stripe SDK. Investigate.
```

## Stuck Detection + Evidence Policy in action

### Attempt 1: Claude investigates

```
[VERIFIED] test_payment_process fails with:
  AttributeError: 'PaymentIntent' object has no attribute 'charges'
  (pytest output, line 47 test_payment.py)

[CODE] payment_service.py:23 uses intent.charges.data[0]
[DOCS] Stripe SDK v8.0 changelog: "charges" renamed to "latest_charge"
[INFERRED] Breaking change in Stripe SDK v7→v8: intent.charges → intent.latest_charge
```

Claude does NOT guess. He:
1. Read the error (VERIFIED)
2. Found the line in code (CODE)
3. Checked the changelog (DOCS)
4. Drew a conclusion (INFERRED — with reasoning chain stated)

### Attempt 2: Minimal fix

```python
# payment_service.py:23
# Before:
charge = intent.charges.data[0]
# After:
charge = intent.latest_charge
```

### Result

```
$ pytest tests/unit/test_payment.py -x -q
3 passed in 0.15s
```

```
[VERIFIED] 3/3 tests pass after replacing intent.charges with intent.latest_charge
[DOCS] Stripe SDK v8.0 migration guide confirms: latest_charge is the recommended approach
[UNKNOWN] did not check other places in the codebase where .charges may be used
```

### Claude suggests a follow-up check

```
Recommend grepping the entire project:
$ grep -rn "\.charges" src/ --include="*.py"

This is [UNKNOWN] — there may be other locations with the same breaking change.
```

## What this example demonstrates

1. **Evidence Policy** — every fact is marked, it is clear what was verified
2. **Stuck Detection** — not needed (solved in 1 iteration)
3. **Minimal fix** — 1 line, not a refactor of the entire module
4. **[UNKNOWN]** — honest "did not check" instead of "everything is fixed"
