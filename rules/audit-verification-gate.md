# Audit Verification Gate

## Problem this solves
Explorer agents read files in isolation and produce false positives:
- Symbolic formula mismatches that are algebraically equivalent
- "Dangerous defaults" that are never hit in production paths
- "Wrong sign" claims from misidentified time-direction conventions

## Hard Rule
NO HIGH or MEDIUM finding reaches the user without tool-verified evidence.

Agent's [VERIFIED] ≠ your [VERIFIED]. Agent's [VERIFIED] = your [INFERRED].

## Verification Protocol (between agent reports and user-facing output)

### For every HIGH/MEDIUM claim:

| Claim type | Required verification |
|------------|---------------------|
| Wrong formula / wrong sign | Run `pytest <relevant_test_file>` — if tests pass, downgrade to HYPOTHESIS |
| Dangerous default value | `grep -rn '<function_name>('` — find ALL call sites, check if default is ever used |
| Missing check / guard | `grep -rn '<pattern>'` across codebase — may exist elsewhere |
| Convention mismatch | Read the FULL call chain (min 2 files): caller → function → return value consumer |
| Boundary condition wrong | Run edge-case test if exists, or write a 3-line numerical check in Bash |

### For LOW/INFO claims:
Spot-check 3 random claims with grep/read. If any fail → verify ALL.

## Anti-patterns to catch
- "Standard form is X, code has Y, therefore bug" — check if X and Y are equivalent under project's variable definitions
- "Default is dangerous" — check if default is ever reached in actual usage
- "Sign is wrong" — check time direction (forward vs backward PDE), space convention (log-moneyness vs price)
- "No test for X" — grep for the test, it may have a different name

## Output format
Each finding in the final report must carry:
- `[VERIFIED-tool]` — confirmed by pytest/grep/bash (include which tool)
- `[HYPOTHESIS]` — agent found it, plausible, but not tool-confirmed
- `[DISMISSED]` — agent found it, verification disproved it

Never present [HYPOTHESIS] as a confirmed bug. Use language: "potential issue, requires manual review."
