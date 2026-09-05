# boyko-project-radar — PROJECT-mode full re-run

**Date:** 2026-09-05
**Object:** does a second PROJECT-mode run of `boyko-project-radar` on this same
repo (Claude-cod-top-2026), with all 4 sub-scanners genuinely invoked and each
explicitly briefed to apply HARD RULE 5 (verify any history-based finding
against current HEAD before citing it), produce real, verified findings and a
synthesis whose top recommendation does not repeat the specific flaw that kept
the 2026-08-26 run at `described`?

## Why this run exists

The first PROJECT-mode run (2026-08-26, not filed as a separate artifact,
summarized inline in `skills/registry.yaml`'s prior `boyko-project-radar`
entry) found a real live bug and 6 unregistered hooks, but its synthesized
"МОЙ ВЫБОР" recommendation rested on an unverified `[INFERRED]` finding from
the `atomize` sub-scanner — a historical commit pattern cited as an active
bottleneck without checking it was already resolved at HEAD. That is a
concrete instance of the "registered != actual" failure class this repo has
independently rediscovered and gated at least 3 times elsewhere (PR #275-277,
#292). This run exists to check whether briefing each sub-scanner to apply the
same freshness discipline actually closes that gap, rather than assuming it
does.

## Protocol

User asked `/boyko-project-radar` in PROJECT mode (scope stated explicitly in
the invocation, satisfying the skill's own Scope Gate — no re-ask needed). Per
the skill's Step 1/2, checked which of the 5 candidate sub-scanners exist in
this catalog (all 5 do: atomize, deletion-test, sci-code-audit, research-audit,
skill-audit) and confirmed `experiments/` (14 subdirs), `null_results/`,
`parked/`, `pearl_registry/` all exist in this repo before deciding
research-audit applies.

Ran 4 sub-scanners as parallel background `Agent(general-purpose)` calls (each
told: read the actual named `SKILL.md` first, execute its real protocol via
tool calls against this repo's real files, and — the freshness instruction —
verify any commit-history-based claim against current HEAD via `git log --all
-- <file>` or a direct re-read before using it, not the third-party claim
alone). `skill-audit` was scoped out of this run (tooling-health question, not
in-scope for a code/research audit) — recorded as "skipped", not silently
dropped, per the skill's own Hard Rule 2 (all 4 categories present even when a
scanner is unavailable/skipped).

## Sub-scanner results (condensed; full text is this session's own transcript)

**atomize** — top-3 bottlenecks, all HEAD-verified:
1. Repo↔live hook-deployment drift — cross-checked against PRs #355-366 (this
   session's own history) and this session's live `live-drift-guard` output
   (which independently flagged 2-3 files not yet redeployed at session
   start), not just a historical commit count.
2. `activeContext.md`'s 15-entry cap — confirmed present in the repo copy of
   `post_commit_memory.py` (this session verified this by reading the actual
   file), confirmed NOT yet live via the same `live-drift-guard` signal.
3. 5 fossil one-off migration scripts in `scripts/` (`lint_all_p1.py`,
   `stage_p1.py`, `lint_p1_hooks.py`, `deploy_p1_hooks.py`, `git_add_hooks.py`,
   `fix_lint.py`) — 0 references anywhere in `.github/` (grep-verified by the
   sub-agent), not just "looked old."

**deletion-test** — real HEALTHY/CRITICAL vs DEAD classification, with the
known blind spot explicitly re-checked: all 6 `class: library` modules in
`hooks/registry.yaml` (`doc_bridge.py`, `doc_registry.py`, `cogniml_client.py`,
`vector_store.py`, `learning_tips.py`, `expert_registry.py`) were individually
grep-verified for real importers rather than assumed correctly-documented —
5 of 6 confirmed via in-repo imports, 1 (`expert_registry.py`) confirmed via
the already-documented personal-skill-only consumer, matching this repo's own
prior finding. `scripts/lint_all_p1.py` and 4 siblings independently flagged
DEAD by this scanner too (agreement with `atomize`, not a duplicate claim
copied across).

**sci-code-audit** — 3 findings, one of which was explicitly retracted by the
sub-agent itself after a second check (kept here as evidence the discipline
worked, not hidden):
1. `security_verify.py` (`fail_mode: closed`, `escalation: warn`) sits outside
   Gate 12a's `escalation: block`-only scope in `gen_hook_matrix.py` — CONFIRMED,
   currently wired correctly but with no CI gate that would catch a future
   regression in this specific warn-tier subset.
2. `hook_main()` — an initial hypothesis that this helper was untested was
   RETRACTED after the sub-agent found direct behavioral tests in
   `tests/test_coverage_boost.py:827-999` covering timeout/crash/`fail_closed`
   True and False.
3. The `CLAUDE_INVOKED_BY` recursion guard, stated as a hard invariant in
   `hooks/CLAUDE.md`, has zero mechanical enforcement — grep-confirmed absent
   from both `check_architecture.py` and `gen_hook_matrix.py`.

**research-audit** — 3 discrepancies, all diff/grep-verified against the real
`experiments/` tree and `pearl_registry/INDEX.md`:
1. `experiments/20260903-memory-retrieval-repair/` (58KB `decision.md`, source
   of 6 `pearl_registry` entries) is completely absent from
   `experiments/INDEX.md`.
2. `experiments/20260728-hypothesis-arbiter-taxonomy-pilot/` also missing from
   `experiments/INDEX.md` despite same-date siblings being listed.
3. One `pearl_registry/INDEX.md` row (`20260728-osa-fl-protocol-vs-standard-
   analysis`) has `next_check: 2026-09-01`, still `pending` as of 2026-09-05 —
   4 days overdue. Cross-checked `experiments/INDEX.md` ↔ `null_results/
   INDEX.md` ↔ `parked/INDEX.md` for all 9 already-indexed experiments: zero
   zombie hypotheses found among those — the scanner did not over-flag a
   clean baseline.

## Synthesis ("МОЙ ВЫБОР") and what changed from the 2026-08-26 run

Recommended chain 3 (a mechanical Gate 12c for the `CLAUDE_INVOKED_BY`
invariant, modeled directly on the already-existing, already-CI-enforced
Gate 12a) as the highest-leverage action, with the stated rationale that this
exact "documented rule, zero mechanical enforcement" pattern has already paid
off 3 times in this repo (PR #275-277, #292) — a named, checkable precedent,
not an unverified historical inference. No sub-scanner finding used in this
recommendation depended on an un-rechecked historical claim: the two
commit-history-based bottlenecks (drift, fossil scripts) were independently
re-confirmed live via `live-drift-guard`/grep at the time of this run, not
carried over from a stale citation.

## Result vs the object question

Yes: this run's synthesis path did not repeat the 2026-08-26 flaw. The one
place a sub-agent's own hypothesis was later found wrong (`hook_main()`
"untested") was caught and retracted by that same sub-agent before reaching
the synthesis step, rather than surfacing in the final recommendation — this
is the freshness/verification discipline functioning as intended, once, on a
live case, not merely a stated intention.

## Limitation

n=1 for this specific closed-loop claim ("briefing sub-scanners on freshness
prevents the 2026-08-26 failure mode") — one clean run does not establish a
base rate for how often an unbriefed or differently-briefed run would recur
the flaw. `TASK` mode remains completely unevaluated (n=0), not covered by
this artifact.

## Full agent transcripts

The 4 sub-scanner agents' full tool-call sequences and complete reports exist
in this session's own transcript (not reproduced verbatim here). This file is
the citable, committed artifact per this repo's anti-theater convention
(`scripts/check_architecture.py` gate 10) — the condensation above preserves
which specific file/line/mechanism each finding cites, matching the source
reports.
