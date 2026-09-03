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
| **updated** | 2026-09-03 overnight, after PRs #323/#324/#325 (external-audit fix backlog) [VERIFIED: `gh pr view <n> --json state,mergedAt`] |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config (hooks/agents/skills/rules), self-checking against its own Falsification Ladder methodology. |
| **branch** | `main` = `6be0e00` (PR #317 merged). No open feature branches. |
| **released** | `v3.10.0` (tag + public GitHub Release); `boyko-baseline-v1`/`v2` are eval-suite reference tags, not releases |
| **tests** | 3009 CI-measured on PR #317 (`test (3.12)` job) [VERIFIED: `gh run view --log-failed` printed `Actual: 3009 tests, 84% coverage`]; README synced to 3009/84% in the same PR |
| **HARD RULE — solo autonomy (owner, angry, 2026-09-02 17:xx)** | ZERO tool-level confirmation prompts. I caused a prompt storm across 4–5 open sessions by re-wiring `permission_policy.py` to `PreToolUse/Bash` (its `decide()` returns "ask" on any `&&`/`;`/`|`); also added `Edit(**/test_*.py)`-class denies that blocked test edits. Both reverted within the hour; permission_policy `main()` now emits ONLY on "deny" (silent on ask/allow → static `Bash(*)` allow applies) — this fix is now merged (PR #313), not just deployed live. Full rule + WHY in auto-memory `feedback_solo_autonomy_no_confirmations.md`. Never register an "ask"-emitting hook on his live machine again; never add source/test file-class denies. Deny-only security is welcome; anything that prompts is the wrong step. |
| **DEFAULT FOCUS BIAS — now a firm decision, not just a bias (owner, 2026-09-02 late night, after PR #317's own reviewer proposed a VerificationOps layer)** | Owner explicitly chose **"B now, A later"**: do real §8 experimental-pack work NOW (scientific-discovery / hypothesis-arbiter / claim-pipeline — real hypotheses, real oracle-adequacy tests) rather than build a `verification_gap`/telemetry layer on top of §7, which is essentially closed. Full reasoning in `.claude/memory/decisions.md` § 2026-09-02. Two things permanently rejected (not deferred): (1) inferring agent claim-status by regexing prose ("done"/"passed") — validation theater by construction; any future claim-status field must be an explicit structured value an agent sets deliberately; (2) any mechanism where measured reliability *automatically* mutates the live autonomy tier — telemetry may only feed a `measurement → recommendation → human` loop, never `measurement → policy mutation` (conflicts with the solo-autonomy HARD RULE above). **Stop-condition for revisiting VerificationOps:** real §8 runs across multiple hypotheses with actual PASS/FAIL/UNKNOWN disagreement cases exist — not a calendar date, not a round number of runs. |
| **target user (Constitution §2, RECONFIRMED 2026-09-02)** | Solo — the author only. NOT a team product. No access control / multi-author memory / human-reviewer workflows needed. |
| **review threshold (owner-reviewed 2026-09-02, /tracy)** | KEEP AS IS: reviewer mandatory at 3+ files OR security-critical. Evidence from this session: cost of review correlates with *branching logic over untrusted input*, not diff size (87-file mechanical migration = 1 cheap pass; 1-file `$IFS` parser fix = 3 expensive rounds, each finding a real bug). Do NOT narrow the 3+ files trigger — it is what caught `reliability_vector.py`'s P1, which was not security-tagged. |
| **current focus** | 2026-09-02 shipped: property-based parser tests (#305), `file_lock()` AST guard (#306), security reliability vector (#308), `postconditions` schema field (#307), `utils.py`→`lib/` migration of all 86 in-repo call sites (#310), a real `$IFS` shell-obfuscation bypass fix in `hooks/lib/security.py` (#311+#312, incl. P0 default/assign/error-operator erasure fix + `find_event_registration_drift`), the permission_policy deny-only fix (#313), the long-pending root `CLAUDE.md` rewrite + archived memory history (#314, #315), and — after comparing this repo against an external Claude Code multi-agent orchestration research doc and finding it was already ahead on everything except two adoptable ideas — a "Declared Model" column on `agent_lifecycle.py`'s auto-generated performance table + a new `rules/delegation-contract.md` prose checklist for briefing non-trivial `Agent()` calls (#317). Found & fixed along the way: `TestAgentLifecycle` had been silently writing to this machine's REAL `~/.claude/logs/agent_lifecycle.log` for a long time (11,870+ real accumulated lines) because `Path.home()` patching can't retroactively redirect module-level path constants bound at import time — fixed with an autouse fixture pinning the constants directly. All merged to main, CI green. Live `~/.claude/hooks` + `~/.claude/rules/` + personal `~/.claude/CLAUDE.md`'s RULES line redeployed and smoke-tested against real `~/.claude/agents/*.md` files. |
| **P1/P2 backlog — CLOSED tonight (owner said "го все по очереди")** | **P1 wrapper bug fixed:** `weekly-intel-report.ps1`, `weekly-repo-scout.ps1`, `skill-feedback-update.ps1` (all `~/.claude/scripts/`, untracked personal automation, not part of this repo) now check `$LASTEXITCODE` after `claude -p` and log/exit FAILED instead of silently printing DONE on a 401 or any other failure — matches the pattern `run_collectors.ps1` already had. The stale-`ANTHROPIC_API_KEY` root cause itself is still unfixed (owner's credential, not mine to touch) — these 4 scheduled tasks will now at least report failure honestly instead of looking green. **P2a resolved (owner explicitly approved via AskUserQuestion):** live `~/.claude/settings.json` Stop event now includes `commit_test_gate.py` (was repo-only per `find_event_registration_drift`) — this is a real turn-blocking mechanism (exit 2) if source .py changed after the last pytest run, but fires on Claude's own Stop, never a user-facing dialog, so it doesn't conflict with the solo-autonomy HARD RULE above. Backed up live settings.json first. **P2b done:** `commands/release-scout.md` copied to `~/.claude/commands/release-scout.md` — `/release-scout` is now invocable. Scheduling it weekly is a separate standing-config decision (the file's own text treats it as opt-in via `scripts/setup_release_scout_schedule.*`, dry-run by default) — deliberately NOT done tonight, flagged for the owner given today's unrelated scheduled-task fragility. |
| **overnight audit-fix backlog (2026-09-03, owner asleep, autonomous per standing solo-autonomy authorization)** | Owner pasted an external 7.2/10 repo audit + explicit overnight-autonomy go-ahead. Per `audit-verification-gate.md`, every claim was independently re-verified before acting (full trail: `.claude/checkpoints/2026-09-02_overnight-external-audit-fixes.md`, gitignored/local). **Confirmed real and fixed, each its own branch+PR+CI-gated merge:** (1) PR #323 — removed 6 test-file-class `Edit()` denies from the distributable `hooks/settings.json` TEMPLATE (the live personal file was already fixed earlier in the session; the repo template was a separate, missed location). (2) PR #324 — `install.sh --non-interactive` used to silently REPLACE a real, differing existing `settings.json`/`CLAUDE.md` (backup kept, not merged, zero consent); now defaults to skip on a real conflict, with `--force-replace` as explicit opt-in; also fixed an internal version-string contradiction (line 2 said "v2.1", runtime banner said "v11.1"). (3) PR #325 — `tests/test_guard_corpus_baseline.py` (documented, intentional xfail RED for the known prompt-injection guard FP/FN gap) now carries `@pytest.mark.security`, so `scripts/reliability_vector.py`'s security-critical slice actually sees it (408/408 → 413/413). **Checked, NOT acted on (audit's own numbers didn't hold up or weren't actionable as bugs):** "81 unused noqa" (actual grep count: 33, discrepancy unexplained); "80 security Ruff diagnostics" (my own scoped `ruff check --select S .` gives 4204, dominated by test-file S101 noise — not a fair comparison, needs proper scoping first, not done); "43 functions >10 cyclomatic complexity" (plausible, NOT independently re-measured, high regression risk, explicitly deferred — not something to refactor unsupervised); registry provenance gaps (65/137 author, 12/137 source — real but a data-entry task, not a bug); "0 benchmarked skills" (confirmed accurate via `skills/registry.yaml` — a maturity-gap observation, not a count-drift bug; `scripts/sync_doc_counts.py --check` independently confirmed zero drift anywhere, so no PR #4 was needed). Full suite after each merge: 3009 passed, 1 pre-existing unrelated failure (`test_check_global_hooks.py`, live-machine hook path). |
| **next action** | Obsidian session-note update for tonight's audit-fix work (in flight). After that: resume the still-open **§8 direction** from earlier tonight — waiting on the owner to name a concrete hypothesis/subject for `hypothesis-arbiter`/`claim-pipeline` (not itself a task without one). Also open, non-urgent: the stale `ANTHROPIC_API_KEY` (owner's credential fix); whether to arm `/release-scout` weekly; `claude-md/CLAUDE.md`'s RULES list still missing 6 real `rules/*.md` references (`estimand-ops.md`, `evidence-markers.md`, `falsification-ladder.md`, `perelman-audit.md`, `research-methodology.md`, `skeptic-triggers.md`); the three declined-tonight audit items above (noqa/Ruff-security reconciliation, complexity refactor, registry provenance backfill) if the owner wants them picked up. |




## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication




## Auto-commit log
- [2026-09-03 09:25] `64fbd1c`: fix(readme): sync test count 3009->3011 (CI-measured on this PR)
- [2026-09-03 09:12] `585de61`: fix(hooks): restore send_webhook facade export via delegation, not duplication
- [2026-09-03 08:51] `b8d56fc`: fix(docs): correct inverted FIPS semantics in md5 usedforsecurity comment
- [2026-09-03 08:41] `c86dd35`: fix(security): remove dead unsafe send_webhook duplicate + md5 usedforsecurity
- [2026-09-03 08:26] `11495a3`: fix(lint): remove 74 unused noqa directives
- [2026-09-03 00:05] `26be256`: docs(memory): summarize overnight external-audit fix backlog (PRs #323-#325)
- [2026-09-03 00:00] `de7b7ed`: docs(memory): auto-log commit d294796
- [2026-09-03 00:00] `d294796`: fix(tests): mark test_guard_corpus_baseline.py as security-critical
- [2026-09-02 23:52] `4542c40`: docs(memory): auto-log commit a39bb3e
- [2026-09-02 23:51] `a39bb3e`: fix(install): safe non-interactive default on file conflict + version string fix
- [2026-09-02 23:27] `92a6097`: fix(hooks): remove test-file-class Edit denies from the distributable settings.json template
- [2026-09-02 23:20] `b6d446f`: fix(tests): mock chromadb unavailability before index_wiki_entry, not just semantic_search
- [2026-09-02 21:13] `016e039`: fix(readme): sync tests 3002->3009 + coverage 83%->84% (CI-measured on PR #317)
- [2026-09-02 21:09] `bb05378`: feat(hooks,rules): declared-model column in agent perf table + delegation contract rule
- [2026-09-02 19:48] `05e670a`: fix(readme): sync test count 2999->3002 (CI-measured on PR #313)
