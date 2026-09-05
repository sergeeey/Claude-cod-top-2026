# boyko-scientific-consortium — nudge-throttle noise-reduction hypothesis

**Date:** 2026-09-05
**Object:** does the throttle fix to `post_commit_memory.py` (this same
session, PR #369) genuinely reduce perceived hook noise, or only change the
code's behavior in a way that was never actually verified against the human
experience it claims to improve?

## Why this run exists

Real, current hypothesis about this session's own just-shipped work, chosen
specifically because it is exactly the shape of claim this skill's Step 6
anti-confirmation checklist and causal map exist to catch: a fix's author
grading their own fix as successful.

## Protocol

Depth: Глубокий (Standard tier) -- one mechanism, no competing hypotheses
(Step 4/hypothesis-arbiter not invoked), a cheap direct test already existed
(the hook's own live behavior this session). Ran Step 1 (thesis
reconstruction), Step 2 (3 adaptively-chosen roles: measurement engineer,
causal-inference expert, red-team skeptic -- each given a real, specific
question, not decorative), Step 3 (causal map), Step 6 (anti-confirmation),
2 of 4 special modes (Anomaly + Inversion, per the skill's own minimum-2 rule).

## Result -- consortium's own analysis

The causal map named the correct hidden variable (unmeasured "perceived
noise," never directly measured — only inferred from one complaint), a real
confounder (session type: interactive/supervised vs. autonomous), and,
critically, the anti-confirmation step correctly identified that **this
very consortium run** suffers from the same self-grading bias it was
designed to catch (same party authored the fix, the causal analysis, and
would have been the implicit judge). Per the skill's own Step 10 ("next best
experiment/observation"), the correct next action was named as: delegate to
`skeptic` rather than self-declare success.

## Handoff to skeptic (the consortium's own named next step, actually executed)

`Agent(skeptic)` was given the claim and the real code
(`post_commit_memory.py`'s `_nudge_commit_count`/`should_nudge` logic), no
session history.

**Verdict: WEAKENED**, with 3 substantive findings:

1. **Recomposition-gate failure, correctly caught:** the compound claim
   ("mechanism X + effect Y") smuggled a mechanism-level fact (archive/
   active-log writes are unconditional -- CONFIRMED, trivially checkable
   from code) into license for an effect-level claim (perceived noise
   reduced -- unmeasured). "The hook went silent as coded" is evidence about
   the code, not about a human's experience of it.
2. **Boundary overclaim, matches the consortium's own Anomaly-mode finding**
   independently: users working in many short sessions (1-3 commits, fresh
   `session_id` each time) get zero suppression from the throttle -- the
   claim as stated doesn't scope itself to "sessions with >=6 commits."
3. **A genuinely NEW defect neither the consortium run nor the earlier
   `post_commit_memory.py`/PR #369 work had named:** if `session_id` is ever
   absent from the hook's payload, ALL commits collapse onto one shared key
   (`"default"`), causing the OPPOSITE failure mode -- over-suppression
   across genuinely unrelated sessions, not under-suppression. This is a
   real, additional, previously-unflagged code-level finding.

## Result vs the object question

Yes, and more precisely than the original claim: the mechanism half is
CONFIRMED (unconditional archive/log writes), the effect half is
NEEDS-REAL-DATA/HYPOTHESIS (perception was never measured, only asserted),
and one real additional bug (the `session_id`-missing collapse) was
surfaced that neither this consortium run's own causal map nor the
originating fix work had caught.

## Promotion rationale

This is the 3rd independently-dated real session for this skill (2026-08-09,
2026-08-10, now 2026-09-05), each finding real, distinct gaps and -- unlike
the first two, which self-scored 7/10 without external check -- this run
correctly named its own self-grading risk AND actually executed the
delegation to skeptic rather than stopping at naming the risk. Promoted from
`described` (n=2, "still narrow") to `dogfooded` on the combined weight of a
3rd session plus, for the first time, a genuinely closed-loop
self->skeptic handoff.

## Limitation

n=1 for the "consortium correctly identifies its own self-grading risk and
follows through on delegating" pattern specifically -- the two prior
sessions (2026-08-09/10) did not test this exact failure mode, so this is
new evidence for THIS aspect of the skill, not a 3rd replication of
identical ground.
