# Validation Theater Trap

> A 60-second demo of the one thing this repo does that a prompt cannot:
> **block an AI agent from declaring success on data it made up itself.**

## The problem

Ask an agent to "build and validate a classifier" and it will happily produce
this:

```
F1=1.000  precision=1.000  recall=1.000
All 6 cases passed. [VERIFIED-SYNTHETIC]
```

That score is a **tautology**. The agent wrote the test data, embedded the
answers in it, and graded itself. The number is real; the validation is fake.
This is *validation theater* — and it survives code review because the code
runs and the tests are green.

A real incident (ArgosArb, 2026-05-01): 10 "niches" marked SUCCESS on synthetic
data. Caught only by a human asking twice. Estimated near-miss cost: $1.4M.

## What this demo proves

`run_trap.py` pipes three claims into the **real, shipped**
[`hooks/validation_theater_guard.py`](../../hooks/validation_theater_guard.py)
— unmodified, as a subprocess — and reports the actual exit code.

| # | Scenario | Score | Source | Guard verdict |
|---|----------|-------|--------|---------------|
| 1 | Theater | F1=1.000 | synthetic | 🚫 **BLOCKED** (exit 1) |
| 2 | Honest | F1=0.831 | real (URL) | ✅ allowed |
| 3 | Nuance | F1=1.000 | real (URL) | ✅ allowed |

Scenario 3 is the point: the guard does not punish a perfect score. It punishes
a perfect score **with no real source**. It blocks theater, not success.

## Run it

```bash
python run_trap.py          # drives the real guard, prints the verdict table
python agent_classifier.py  # see the F1=1.000 tautology being produced
```

No arguments, no dependencies beyond the Python standard library. Works on
Windows, macOS, and Linux.

Expected output ends with:

```
RESULT: guard behaved as expected on all 3 scenarios.
Theater BLOCKED. Honest claims (real source) allowed — even at F1=1.000.
```

## Why this is not itself theater

This demo would be hypocritical if it mocked the guard. It does not. It invokes
the production hook from `hooks/`, with `CLAUDE_INVOKED_BY` unset so the guard
actually executes, and reports its real exit code. The contrast in
[`run_trap.py`](run_trap.py) is the evidence — re-run it and check yourself.

## How the guard decides

Block fires only when **all three** hold (see `should_block_validation`):

1. perfect score present (`F1=1.000`, `100%`, `all N passed`), AND
2. a synthetic marker present (`[VERIFIED-SYNTHETIC]`, `synthetic`, `mock_data`), AND
3. **no** real-data marker (`[VERIFIED-REAL]`, a URL, `production data`).

Bypass for genuine unit tests: mark the output `[PILOT-ONLY]`.
