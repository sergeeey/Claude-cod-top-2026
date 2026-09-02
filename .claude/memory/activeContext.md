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
| **updated** | 2026-09-02 late night, after PR #317 merged (declared-model column + delegation-contract rule) [VERIFIED: `gh pr view 317 --json state,mergedAt`, `git log -1` on main = `6be0e00`] |
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
| **next action** | **In flight:** transitioning to §8 work per the decision above — waiting on the owner to name a specific real hypothesis/subject to run through `hypothesis-arbiter`/`claim-pipeline` (transitioning to §8 is a direction, not itself a task; needs a concrete subject to act on). Open, non-urgent, deliberately not §7 infra work: the stale `ANTHROPIC_API_KEY` (owner's credential fix); whether to arm `/release-scout` on a weekly schedule (owner decision, not yet asked); `claude-md/CLAUDE.md`'s RULES bullet list still missing 6 real `rules/*.md` references (`estimand-ops.md`, `evidence-markers.md`, `falsification-ladder.md`, `perelman-audit.md`, `research-methodology.md`, `skeptic-triggers.md`) — confirmed real, deliberately unfixed, flagged so it isn't lost. |




## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication




## Auto-commit log
- [2026-09-03 00:00] `d294796`: fix(tests): mark test_guard_corpus_baseline.py as security-critical
- [2026-09-02 23:52] `4542c40`: docs(memory): auto-log commit a39bb3e
- [2026-09-02 23:51] `a39bb3e`: fix(install): safe non-interactive default on file conflict + version string fix
- [2026-09-02 23:27] `92a6097`: fix(hooks): remove test-file-class Edit denies from the distributable settings.json template
- [2026-09-02 23:20] `b6d446f`: fix(tests): mock chromadb unavailability before index_wiki_entry, not just semantic_search
- [2026-09-02 21:13] `016e039`: fix(readme): sync tests 3002->3009 + coverage 83%->84% (CI-measured on PR #317)
- [2026-09-02 21:09] `bb05378`: feat(hooks,rules): declared-model column in agent perf table + delegation contract rule
- [2026-09-02 19:48] `05e670a`: fix(readme): sync test count 2999->3002 (CI-measured on PR #313)
- [2026-09-02 19:44] `2619b04`: fix(security): make permission_policy.py deny-only on PreToolUse/Bash
- [2026-09-02 17:35] `8fe4be3`: fix(readme): sync test count 2989->2999 (CI-measured on PR #312)
- [2026-09-02 17:29] `d6caeb2`: fix(security): exclude IFS default/assign/error operators from normalization (P0)
- [2026-09-02 16:00] `a736165`: fix(readme): sync test count 2973->2989 (CI-measured on this PR)
- [2026-09-02 15:24] `bac1322`: fix(security): close $IFS shell-obfuscation bypass in dangerous-command detection
- [2026-09-02 08:51] `c865e20`: refactor(hooks): migrate all internal call sites off the utils.py facade
- [2026-09-02 08:32] `67cb43a`: docs(memory): update activeContext.md after PR #305/#306/#307/#308 merged (#309)
