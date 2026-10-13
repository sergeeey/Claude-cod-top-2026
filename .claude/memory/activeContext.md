# activeContext.md — Claude-cod-top-2026

<!-- ─────────────────────────────────────────────────────────────────────────
     CURRENT STATE is the authoritative snapshot. Read THIS block first.
     Everything below CURRENT STATE is either durable (Scope Fence) or a
     bounded, auto-written log (Auto-commit log, capped at 15 entries) — never
     a place to accumulate narrative history.

     Split executed 2026-08-28 (docs/memory-architecture.md's own deferred
     target, finally applied): this file had grown to a CURRENT STATE table
     whose single "updated" cell alone was 52,267 characters — the Read tool
     could not return even a 45-line window without exceeding its token cap.
     The full pre-split content (multiple months of accumulated narrative,
     several stale/superseded "Current Focus"/"Project State" sections, a
     duplicated "Recent findings" header) is preserved byte-for-byte at
     .claude/memory/history/pre-2026-08-28-consolidation.md — nothing was
     deleted, only moved. Going forward: keep this table SHORT and current;
     anything narrative or dated belongs in history/, not here.

     Known gap surfaced while doing this split, not fixed here (separate,
     deliberate decision): the LIVE global ~/.claude/hooks/post_commit_memory.py
     on this machine never got the 2026-08-22 update that caps the Auto-commit
     log at 15 entries and archives to history/commits-<date>.md — the repo's
     own copy has that code, but .claude/memory/history/ did not exist on this
     machine until this split created it. Until the live hook is updated, this
     log will grow unbounded again and need another manual trim.
──────────────────────────────────────────────────────────────────────────── -->
## CURRENT STATE (authoritative)

| field | value |
|-------|-------|
| **updated** | 2026-09-25, after the Cursor-BOM fix (#475), the positioning/cost-claims alignment (#482) and the merge chain #472 → #475 → #476 → #482 (#483 by a peer session). Older per-row narratives moved to `history/current-state-rows-2026-09-04.md`. |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config (hooks/agents/skills/rules), self-checking against its own Falsification Ladder methodology. |
| **branch** | `main` = `ade12d2` [VERIFIED: `git log --oneline -1 origin/main`; `Tests` green on the last 5 commits, incl. this file's own refresh #484]. Open work PRs: #454, #461, #462, #463 (plus automated FocusOS PRs). Local branch cleanup DONE 2026-09-25 (26 verified branches deleted by the owner, 13 left). |
| **released** | `v3.10.0` (tag + public GitHub Release); `boyko-baseline-v1`/`v2` are eval-suite reference tags, not releases |
| **tests** | 3813 CI-measured on `main` (`test (3.12)` job printed `Actual: 3813 tests, 85% coverage`) [VERIFIED 2026-09-25: `gh api repos/.../actions/jobs/<id>/logs`]; README carries the floor `3600+` (form-gated), not this exact number. |
| **HARD RULE — solo autonomy (owner, angry, 2026-09-02 17:xx)** | ZERO tool-level confirmation prompts. I caused a prompt storm across 4–5 open sessions by re-wiring `permission_policy.py` to `PreToolUse/Bash` (its `decide()` returns "ask" on any `&&`/`;`/`|`); also added `Edit(**/test_*.py)`-class denies that blocked test edits. Both reverted within the hour; permission_policy `main()` now emits ONLY on "deny" (silent on ask/allow → static `Bash(*)` allow applies) — this fix is now merged (PR #313), not just deployed live. Full rule + WHY in auto-memory `feedback_solo_autonomy_no_confirmations.md`. Never register an "ask"-emitting hook on his live machine again; never add source/test file-class denies. Deny-only security is welcome; anything that prompts is the wrong step. |
| **DEFAULT FOCUS BIAS — now a firm decision, not just a bias (owner, 2026-09-02 late night, after PR #317's own reviewer proposed a VerificationOps layer)** | Owner explicitly chose **"B now, A later"**: do real §8 experimental-pack work NOW (scientific-discovery / hypothesis-arbiter / claim-pipeline — real hypotheses, real oracle-adequacy tests) rather than build a `verification_gap`/telemetry layer on top of §7, which is essentially closed. Full reasoning in `.claude/memory/decisions.md` § 2026-09-02. Two things permanently rejected (not deferred): (1) inferring agent claim-status by regexing prose ("done"/"passed") — validation theater by construction; any future claim-status field must be an explicit structured value an agent sets deliberately; (2) any mechanism where measured reliability *automatically* mutates the live autonomy tier — telemetry may only feed a `measurement → recommendation → human` loop, never `measurement → policy mutation` (conflicts with the solo-autonomy HARD RULE above). **Stop-condition for revisiting VerificationOps:** real §8 runs across multiple hypotheses with actual PASS/FAIL/UNKNOWN disagreement cases exist — not a calendar date, not a round number of runs. |
| **target user (Constitution §2, RECONFIRMED 2026-09-02)** | Solo — the author only. NOT a team product. No access control / multi-author memory / human-reviewer workflows needed. |
| **review threshold (owner-reviewed 2026-09-02, /tracy)** | KEEP AS IS: reviewer mandatory at 3+ files OR security-critical. Evidence from this session: cost of review correlates with *branching logic over untrusted input*, not diff size (87-file mechanical migration = 1 cheap pass; 1-file `$IFS` parser fix = 3 expensive rounds, each finding a real bug). Do NOT narrow the 3+ files trigger — it is what caught `reliability_vector.py`'s P1, which was not security-tagged. |
| **current focus** | 2026-09-19..25. (a) Cursor 3.20.21 sends UTF-8-BOM stdin; text-mode `json.load` failed and every fail-closed PREVENT hook (pre_commit_guard, pre_vault_write, security_verify, input_guard) denied every call. Fixed by `read_stdin_text()` in `hooks/lib/runtime.py` (#475); live-deployed 2026-09-19. (b) Public claims audited against code (#482): token costs (template ~2.1k, rules ~58k under `standard`/`full`, ~155/skill), enforcement wording (PostToolUse cannot block), stale counts. Measured table: Obsidian `knowledge/Claude-cod-top-2026 — стоимость в токенах (измерено 2026-09-25).md`. (c) `boyko-goal-expansion-100` v1.2.0 unasked-questions step (#476); independence scorer UNKNOWN tier (#472); stale-skill test fix (#483). Live install: BOM fix + 7 skills deployed, backups `~/.claude/backups/skills-20260925/`. Details: auto-memory `project_cursor_bom_and_positioning_20260925`, Obsidian session note 2026-09-25. |
| **next action** | Owner decisions pending: (1) limit more rules via `paths:` (19 of 21 unscoped, ~58k tokens always in context under `standard`/`full`); (2) **`y17/pilot-pains` holds 6 local-only commits that exist nowhere on the server** (skill lifecycle check, claim-decomposer ILL-POSED, cross-domain Problem Mining, docs) — push as a backup; (3) open a PR from `fix/independence-empty-list-yaml` (peer session; bug `key:[]` is still on `main` at `hooks/independence_scorer.py:541`, patch `3a7be41` merges cleanly); (4) live-only edits in `ace_reflector.py`, `iteration_guard.py`, `rules/pearl_registry/INDEX.md` are `UNPROVEN` drift — port or discard (#461 covers the INDEX row; branches `fix/port-iteration-guard-stop-agent-type[-local]` are the only git copy of the live `iteration_guard` variant, keep until decided); (5) three empty/equivalent branches can be deleted (`feat/codex-competitor-config`, `y67/audit-followups`, `y58/entry0-event-definitions`). Not verified: 36 of 135 skills ship without YAML frontmatter (load impact UNKNOWN); ~29 advisory hooks read stdin directly (likely fail-open under the Cursor BOM). The date-based test `test_no_stale_skill_still_claims_confirmed` will go red again as more skills pass 60 days. Full audit report: Obsidian `13 Reviews/claude-cod-top-2026-cursor-bom-and-positioning-audit-2026-09-25.md`. |







## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication







## Auto-commit log
- [2026-09-05 01:16] `c19330e` (local, branch `docs/record-agent-tool-scope-guard-log-evidence` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(memory): record real historical impact of the All-tools bug from logs
- [2026-09-05 00:43] `afc5413` (local, branch `docs/pr364-live-redeploy-record` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): fix(docs): map PR #364's own commit hashes to the surviving squash
- [2026-09-05 00:38] `822e824` (local, branch `docs/pr364-live-redeploy-record` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(memory): record PR #364 centralization fix + live redeploy
- [2026-09-05 00:32] `73c674c` (PR #364, squashed from local `962d512`): docs(readme): sync test count to CI-reported 3125 (was 3123)
- [2026-09-05 00:29] `73c674c` (PR #364, squashed from local `0dd79a8`): fix(hooks): centralize commit_test_gate state access, fix sibling readers
- [2026-09-05 00:08] `73c674c` (PR #364, squashed from local `16ace5a`): docs(readme): sync test count to CI-reported 3123 (was 3109)
- [2026-09-05 00:02] `73c674c` (PR #364, squashed from local `1ad0b36`): fix(hooks): port 4 real bugs found only live, never committed
- [2026-09-04 23:31] `f04f980` (local, branch `fix/check-global-hooks-machine-dependent-test` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): fix(tests): make test_check_global_hooks.py machine-independent
- [2026-09-04 23:14] `f6b27ec` (local, branch `docs/pr361-live-redeploy-record` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(memory): record PR #361 live redeploy, sync branch/test-count rows
- [2026-09-04 23:08] `8875190` (local, branch `fix/knowledge-librarian-suffixed-focus-headers` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(readme): sync test count to CI-reported 3109 (was 3108)
- [2026-09-04 23:06] `74ab316` (local, branch `fix/knowledge-librarian-suffixed-focus-headers` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): fix(hooks): restrict Current Focus suffix grammar, fix memory typo/size
- [2026-09-04 22:55] `e4abb84` (local, branch `fix/knowledge-librarian-suffixed-focus-headers` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(readme): sync test count to CI-reported 3108 (was 3101)
- [2026-09-04 22:52] `c7518f3` (local, branch `fix/knowledge-librarian-suffixed-focus-headers` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): fix(hooks): match suffixed ## Current Focus headers in knowledge_librarian.py
- [2026-09-04 22:35] `80d3c8c` (local, branch `docs/issue227-live-redeploy-record` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(memory): sync stale test-count row to 3101
- [2026-09-04 22:35] `a0c6e28` (local, branch `docs/issue227-live-redeploy-record` -- may be replaced if this branch is later merged via squash or rebase; check that branch's PR/merge for the surviving hash if this one becomes unresolvable): docs(memory): record issue #227's live redeploy + Codex P1 dismissal reasoning
