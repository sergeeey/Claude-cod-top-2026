# Checkpoint — Boyko Agent v2 autonomous hardening in progress

**Date:** 2026-07-22
**Branch:** main, HEAD `9c214f9`
**Mode:** user stepped away, explicit go-ahead to act autonomously and bring
agents/navigator.md (boyko-agent) to a reference/exemplary state.

## Done and pushed this session (all CI-green on their SHAs)

1. `dff76c5` — SEC-04: `permission_policy.py` process-substitution Bash bypass
   fixed (missing `<` in `CHAIN_OPERATORS`), 4 regression tests, independent
   `Agent(sec-auditor)` review CONFIRMED.
2. `027e4ca` — README test-badge sync 2408 -> 2412 (CI-authoritative).
3. `dff76c5`'s follow-up — `aecd738`/`dff76c5`: fixed my own regression in
   `skills/core/routing-policy/SKILL.md` (had reverted an upstream fix that
   correctly renamed "navigator" to "boyko-agent" per the real Agent-tool
   roster; restored the correct name with an accurate explanation).
4. `f077e20`/`0394f91` — Boyko Agent v2 round 1: added `## Reconciliation
   Protocol` section, 3 new CTA Card fields (`Done when:`, `Scope limits:`,
   `Verifier:`), Operating Contract item 12 (context budget per delegate).
   Reviewed twice by `Agent(reviewer)` (1 P1 + 4 P2 found and fixed,
   iteration 2 = LGTM).
5. Ran `install.sh --non-interactive --profile=standard` for real against
   live `~/.claude` (was previously stale/never-deployed for
   `resource_router.py` and today's hook fixes) — confirmed file-identical
   deploy.
6. Live dogfood test of the updated boyko-agent on a real task (repo
   prioritization) — structurally compliant (9/9 required headers), 3/3
   spot-checked factual claims verified real (no hallucination). **Found a
   real gap**: the 3 new CTA Card fields were silently skipped in the actual
   output — `boyko_protocol_guard.py` only checks for section headers, not
   field-level completeness inside them. Rated 7.5/10.
7. Spawned a background task for the CTA-field-completeness guard fix
   (`task_e5aab128`) — **user already started it in a separate worktree
   session before I could do it myself; I dismissed my own attempt to avoid
   duplicating that work.** Do NOT redo this fix here; check if it landed
   before touching `hooks/boyko_protocol_guard.py` or
   `tests/test_boyko_protocol_guard.py` again.
8. `69678f8`/`9c214f9` — clarified the "Default routing patterns" table in
   navigator.md is orchestrator-facing recommendations, not agents
   boyko-agent invokes itself (its own `tools:` whitelist correctly excludes
   `architect`/`builder` per its "Must NOT do: implementation edits" rule) —
   resolved a reviewer-flagged ambiguity without changing the whitelist.

## In progress / next steps (per user's "доведи до эталонного состояния")

- Design and run ONE more dogfood test that specifically tries to force the
  new Reconciliation Protocol to fire (two agents giving genuinely
  conflicting answers on the same fact) — not yet exercised in any real run.
- Check whether the parallel worktree session's CTA-field-completeness fix
  has landed (look for a new commit touching `hooks/boyko_protocol_guard.py`
  / `tests/test_boyko_protocol_guard.py` on origin/main not yet pulled
  locally) before doing any further work in that specific file.
- Consider whether `maxTurns: 12` is still adequate given the Reconciliation
  Protocol adds another decision loop — no evidence of turn exhaustion yet,
  don't change without evidence.
- `.claude/memory/activeContext.md` is stale (memory-guard flagged 350+ min
  since last manual update — only auto-log commit-message lines have been
  appended). Do a real manual update summarizing this session's work before
  declaring the Boyko v2 effort complete.
- Final step: one more summary/rating message to the user when they return,
  covering everything done autonomously.

## Rollback

`9c214f9` is the last known-good, CI-green, fully-tested state.
```bash
git reset --hard 9c214f9   # only with explicit confirmation — not pre-authorized here
```
No destructive git operations have been run this session; every merge was
--no-ff with verified two-parent ancestry before push.

## Known standing constraints (do not re-attempt)

- Cannot directly Edit live `~/.claude/hooks/*.py` files for diagnostics —
  blocked by this session's auto-mode classifier (attempted once, respected
  the block, did not route around it).
- `resource_router.py` telemetry (recommended vs actual tier/model/agents)
  is designed but not built — blocked on the above restriction. Left as an
  open thread per an earlier AskUserQuestion answer ("install.sh" was
  chosen over live-diagnostic-edit or "defer"); install.sh is done, the
  live-field-verification step is what remains blocked.
- User works on this repo from 2+ PCs — always expect `origin/main` to have
  moved; `git fetch` before assuming local state is current.
