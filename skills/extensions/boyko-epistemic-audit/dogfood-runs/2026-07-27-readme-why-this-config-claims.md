# Dogfood run — boyko-knowledge-audit vs README.md "Why This Config?" + "Security"

**Date:** 2026-07-27
**Invocation:** `Skill(boyko-knowledge-audit, ...)`, forked execution, real task with a
checkable outcome (not a hypothetical walkthrough).

## Context

Promoting a 6th skill toward the P2-item-16 "5-10 dogfooded" target
(`docs/baselines/2026-07-24-plan.md`). Picked `boyko-knowledge-audit` deliberately
because it tests a *different* capability than the 5 skills already `dogfooded`
(epistemic claim-level classification of prose, not code-vs-doc matching like
`intended-vs-implemented`, not chain-verdict like `boyko-why-ladder`).

## First attempt failed — disclosed, not hidden (per maturity-criteria point 4)

The first invocation resolved its target to a **stale, 3-month-old clone** of this
same repo at `D:\ANALITIK HB RK\.temp_repo\Claude-cod-top-2026\` (commit `378b706`,
April 2026) instead of the live working copy. Verified independently before
trusting anything from that run: `git remote -v` confirmed same GitHub origin, `git
log -1` confirmed the stale commit, `wc -l` confirmed a line-count mismatch (405
lines there vs 535 in the real working copy) consistent with 3 months of drift. This
is a **Substrate Gate** failure (`rules/falsification-ladder.md` Step 2a) — the
audit target was wrong, not the skill's reasoning — so that run's findings were
discarded, not scored either way for this promotion.

**Fix applied:** re-invoked with an explicit absolute path
(`C:\Users\sboi\Claude-cod-top-2026\README.md`) and an explicit instruction not to
search by repo name across the filesystem. Second run correctly targeted the live
file (confirmed: line numbers and total line count matched the actual working copy).

## Real findings (second run, all independently re-verified with a tool before being
recorded here — agent's `[VERIFIED]` treated as this session's `[INFERRED]` until
independently checked, per `rules/audit-verification-gate.md`)

| Claim (README.md location) | Skill's verdict | Independently re-verified how | Confirmed? |
|---|---|---|---|
| "4 agents with persistent memory across sessions" (was L201, L341) | WRONG — actual count is 7 | `grep -l "^memory:" agents/*.md` → 7 files (builder, explorer, navigator, reviewer, sec-auditor, security-guard, tester) | **Yes — [VERIFIED-grep]** |
| "InputGuard — 8 categories" | MATCH | `grep -n "^    \"[a-z_]*\":" hooks/input_guard.py` → exactly 8 keys | **Yes — [VERIFIED-grep]** |
| "HIGH_PRIORITY_CATEGORIES ... AUTO-BLOCK (single match)" applies to only 3 of 8 | MATCH | `grep -n "HIGH_PRIORITY_CATEGORIES"` → `{"encoding_attack", "command_injection", "data_exfil"}`, 3 items | **Yes — [VERIFIED-grep]** |
| "2474 tests" vs actual count | Drift, self-acknowledged elsewhere in README | `pytest tests/ --collect-only -q` → 2480 tests collected | **Yes — [VERIFIED-bash]**, matches skill's number exactly |
| "~500 tokens (core only)" vs actual `claude-md/CLAUDE.md` size | Marked `[INFERRED]` by the skill itself (heuristic char/word count, not a real tokenizer) — flagged as a 3-4x discrepancy, not claimed as strict proof | Not independently re-verified with a real tokenizer (out of scope for this promotion — the skill's own evidence marker already correctly downgrades this to INFERRED, which is the correct epistemic level, not an overclaim to correct) | N/A — skill self-graded correctly |

## Fix applied to the audited subject (not just the skill)

README.md's two "4 agents" occurrences corrected to "7" (this session, this commit).
The second occurrence (agent diagram summary line) also got an honest disclosure
added — the diagram above it only names 8 agents and does not include
`security-guard`, so a bare "7" next to an 8-agent diagram would have created a new,
different confusion; the line now says so explicitly rather than leaving the reader
to notice the mismatch themselves.

## Why this counts as `dogfooded`, not just `wired`

1. **Real invocation** — two, actually run via `Skill(...)`, not simulated.
2. **Citable artifact** — this file, a real repo-relative path (not the skill citing
   its own `SKILL.md`).
3. **A task that could have failed, and the first attempt genuinely did** (wrong
   target) — disclosed as a failure, not smoothed over, exactly matching the
   "failures and all" bar in `docs/skill-maturity-criteria.md`.
4. **Real, checkable outcome**: every MEDIUM-severity finding from the successful
   second run was independently re-verified with `grep`/`pytest`, not trusted on the
   skill's own word, and one genuine bug in the audited document was found and
   fixed as a direct result.

## Anti-theater checklist (per `docs/skill-maturity-criteria.md`)

- [x] Citation target (`skills/extensions/boyko-knowledge-audit/dogfood-runs/2026-07-27-readme-why-this-config-claims.md`) exists, is not `SKILL.md`
- [x] Run happened this session, not reconstructed from memory
- [x] No result here is suspiciously clean — the run genuinely failed once, and the
      successful run found a real, previously-undetected numeric bug (not a
      zero-findings pass, which would itself be a `skeptic-triggers.md` red flag)
- [x] All MEDIUM+ findings independently re-verified with a real tool before being
      recorded as confirmed in this file
