# decision.md — 20260716-response-guard-fp-calibration

## Verdict: BASELINE RECORDED — defect confirmed, fix deferred to a separate PR

This experiment does not itself change the guard. Its job was to turn "the guard
false-positives on security prose" (a vibe I hit twice this session) into measured,
falsifiable numbers against a labelled corpus. It did.

## What is now on record (`[VERIFIED-bash]`, both controls pass)

| | Count | Meaning |
|---|---|---|
| False positives | 8 / 13 benign | guard warns on benign security/scientific/install text; 4 at HIGH severity |
| False negatives | 2 / 12 malicious | guard silently misses two real injections phrased around its keywords |

Positive + negative controls both pass → the defect is at the descriptive-vs-imperative
boundary, not a uniformly broken guard.

## Skeptic pass (inline, security finding → honored not overridden)

- FN cases are real injection shapes (override+harvest; Jinja `{{ system }}`), not strawmen.
- FP cases are genuinely benign (install commands, JS `fetch()`, threat-model prose).
- The 62% FP rate is on a **boundary-stress** corpus and is scoped as such in claim.md —
  it is not a claim about production web content at large.

## Next step (separate PR, NOT this one)

Composition-aware scoring: weight (imperative + agent-targeting + priority-override)
and subtract (quoted/descriptive context), threshold calibrated on this corpus;
plus close the two FN literal-phrase gaps. That PR:
1. gets a context-blind skeptic pass first (security code, doubt-driven-development Trigger 3),
2. must keep the positive control at `warn-high` and drive FP↓ AND FN→0,
3. removes the two xfail markers in test_guard_corpus_baseline.py and updates the pins,
4. records result_summary.md here with the after-numbers.

## Why split into two PRs

"Add corpus + measure" is Green-tier (no behavior change, adds tests). "Change security
scoring" is the risky part and deserves its own reviewed, reversible change with the
baseline already in the suite to measure against. Shipping them together would mean the
security change lands without a recorded before-state to prove it helped.
