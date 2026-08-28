# decision.md — 20260716-response-guard-fp-calibration

## Verdict: ARCHIVE (parked) — RFC-003 shadow-mode calibration stalled at step 6

> **Update 2026-08-28 (research-audit + boyko-project-radar gap, six weeks later):**
> RFC-003's `severity_calibrator.py` (steps 1-5) is real and shipped: a pure
> `calibrate_severity` function wired into `web_response_guard.py`/
> `mcp_response_guard.py` in SHADOW MODE ONLY (log-only, off by default via
> `CLAUDE_GUARD_SHADOW`, zero effect on displayed behavior). Step 6 got exactly
> one probe — `step6_shadow_findings.md`, n=4, same day as the rest of this
> experiment (2026-07-16) — which already corrected the corpus's optimism:
> real-world FP reduction is weaker than the corpus implied (HIGH→REQUIRES_CHECK,
> not HIGH→INFO), though the safety side generalized cleanly (zero unsafe
> downgrades, one real detection improvement). That file's own honest verdict
> said step 7 (turning shadow proposals into displayed changes) "should wait for
> a real multi-session shadow sample, not this [n=4 probe]."
>
> No further shadow data has been collected since. The two `xfail` markers in
> `tests/test_guard_corpus_baseline.py` are still honestly RED (confirmed live
> on HEAD, 2026-08-28) -- the defect this experiment measured (8/13 FP, 2/12 FN)
> remains unsolved in production, exactly as documented, not silently regressed.
> Nothing about the underlying claim was falsified in this window -- it simply
> never got the follow-up data collection its own step-6 verdict called for, and
> had drifted untracked in neither `parked/` nor the Pearl Registry (a real gap
> named by `research-audit`'s 2026-08-28 run, itself scoped as read-only
> analysis -- this file is the follow-through). Parking here, not re-attempting
> another design, closes that tracking gap without pretending the FP/FN problem
> is solved.

---

> **Update 2026-07-16 (same session):** the deferred fix was built and falsified.
> Composition-regex scoring scored 0 FP / 0 FN on the calibration corpus but 4 FP /
> 2 FN on an 8-case held-out set it was not tuned against — it does not generalize.
> See `result_summary.md`. The guard's xfail targets stay RED (honestly unsolved);
> the real fix is a source-aware classifier, an architecture decision left for the
> user. Recorded as null_result `20260716-regex-composition-response-guard`.

---

## Original baseline verdict (still valid): defect confirmed

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

## Revival Condition (added 2026-08-28, on ARCHIVE)

Any ONE of:
1. `CLAUDE_GUARD_SHADOW=1` has been enabled across enough real sessions to
   collect a shadow sample an order of magnitude past the n=4 probe (n≥30
   real WebFetch/WebSearch/mcp__* responses through the shadow path) --
   step 6 as originally scoped, not step 7 attempted without it.
2. A new, independently-motivated FP/FN incident on the live guards makes the
   cost of staying at 8/13 FP, 2/12 FN acute enough to justify committing to
   the real-prose descriptive-detection broadening `step6_shadow_findings.md`
   already named as the actual remaining gap.
3. Someone proposes a genuinely different mechanism (not a third regex/LLM-
   judge variant -- both of those shapes were already independently REJECTed,
   see `null_results/20260716-regex-composition-response-guard.md` and
   `null_results/20260716-llm-judge-response-guard.md`) -- per the Adaptive
   Iteration Branch Rule, a revival needs a changed assumption, not a retry.

## What this ARCHIVE does NOT claim

- Does NOT claim the FP/FN defect is fixed, smaller, or lower-priority than
  when first measured -- the numbers (8/13 FP, 2/12 FN) are unchanged and the
  xfail tests stay red on purpose.
- Does NOT claim the calibrator approach itself was falsified -- step 6's one
  data point was net-positive (safety held, one detection improved); only the
  FP-reduction magnitude was corpus-optimistic. This is an ARCHIVE (valid,
  deprioritized), not a REJECT.
- Does NOT block a differently-motivated redesign -- see Revival Condition
  #3 and `rules/falsification-ladder.md`'s Adaptive Iteration Branch Rule.
