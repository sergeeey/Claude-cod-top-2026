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
| **updated** | 2026-09-03 morning, after PRs #327-#330 (correction + completion of the audit backlog) [VERIFIED: `gh pr view <n> --json state,mergedAt`] |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config (hooks/agents/skills/rules), self-checking against its own Falsification Ladder methodology. |
| **branch** | `main` = `41ebef3` (PR #330 merged). No open feature branches (2 pre-existing FocusOS draft PRs #249/#250 are a separate automated system, unrelated). |
| **released** | `v3.10.0` (tag + public GitHub Release); `boyko-baseline-v1`/`v2` are eval-suite reference tags, not releases |
| **tests** | 3028 CI-measured on PR #330 (`test (3.12)` job) [VERIFIED: `gh run view --log-failed` printed `Actual: 3028 tests, 84% coverage`]; README synced to 3028/84% in the same PR |
| **HARD RULE — solo autonomy (owner, angry, 2026-09-02 17:xx)** | ZERO tool-level confirmation prompts. I caused a prompt storm across 4–5 open sessions by re-wiring `permission_policy.py` to `PreToolUse/Bash` (its `decide()` returns "ask" on any `&&`/`;`/`|`); also added `Edit(**/test_*.py)`-class denies that blocked test edits. Both reverted within the hour; permission_policy `main()` now emits ONLY on "deny" (silent on ask/allow → static `Bash(*)` allow applies) — this fix is now merged (PR #313), not just deployed live. Full rule + WHY in auto-memory `feedback_solo_autonomy_no_confirmations.md`. Never register an "ask"-emitting hook on his live machine again; never add source/test file-class denies. Deny-only security is welcome; anything that prompts is the wrong step. |
| **DEFAULT FOCUS BIAS — now a firm decision, not just a bias (owner, 2026-09-02 late night, after PR #317's own reviewer proposed a VerificationOps layer)** | Owner explicitly chose **"B now, A later"**: do real §8 experimental-pack work NOW (scientific-discovery / hypothesis-arbiter / claim-pipeline — real hypotheses, real oracle-adequacy tests) rather than build a `verification_gap`/telemetry layer on top of §7, which is essentially closed. Full reasoning in `.claude/memory/decisions.md` § 2026-09-02. Two things permanently rejected (not deferred): (1) inferring agent claim-status by regexing prose ("done"/"passed") — validation theater by construction; any future claim-status field must be an explicit structured value an agent sets deliberately; (2) any mechanism where measured reliability *automatically* mutates the live autonomy tier — telemetry may only feed a `measurement → recommendation → human` loop, never `measurement → policy mutation` (conflicts with the solo-autonomy HARD RULE above). **Stop-condition for revisiting VerificationOps:** real §8 runs across multiple hypotheses with actual PASS/FAIL/UNKNOWN disagreement cases exist — not a calendar date, not a round number of runs. |
| **target user (Constitution §2, RECONFIRMED 2026-09-02)** | Solo — the author only. NOT a team product. No access control / multi-author memory / human-reviewer workflows needed. |
| **review threshold (owner-reviewed 2026-09-02, /tracy)** | KEEP AS IS: reviewer mandatory at 3+ files OR security-critical. Evidence from this session: cost of review correlates with *branching logic over untrusted input*, not diff size (87-file mechanical migration = 1 cheap pass; 1-file `$IFS` parser fix = 3 expensive rounds, each finding a real bug). Do NOT narrow the 3+ files trigger — it is what caught `reliability_vector.py`'s P1, which was not security-tagged. |
| **current focus** | 2026-09-02 shipped: property-based parser tests (#305), `file_lock()` AST guard (#306), security reliability vector (#308), `postconditions` schema field (#307), `utils.py`→`lib/` migration of all 86 in-repo call sites (#310), a real `$IFS` shell-obfuscation bypass fix in `hooks/lib/security.py` (#311+#312, incl. P0 default/assign/error-operator erasure fix + `find_event_registration_drift`), the permission_policy deny-only fix (#313), the long-pending root `CLAUDE.md` rewrite + archived memory history (#314, #315), and — after comparing this repo against an external Claude Code multi-agent orchestration research doc and finding it was already ahead on everything except two adoptable ideas — a "Declared Model" column on `agent_lifecycle.py`'s auto-generated performance table + a new `rules/delegation-contract.md` prose checklist for briefing non-trivial `Agent()` calls (#317). Found & fixed along the way: `TestAgentLifecycle` had been silently writing to this machine's REAL `~/.claude/logs/agent_lifecycle.log` for a long time (11,870+ real accumulated lines) because `Path.home()` patching can't retroactively redirect module-level path constants bound at import time — fixed with an autouse fixture pinning the constants directly. All merged to main, CI green. Live `~/.claude/hooks` + `~/.claude/rules/` + personal `~/.claude/CLAUDE.md`'s RULES line redeployed and smoke-tested against real `~/.claude/agents/*.md` files. |
| **P1/P2 backlog — CLOSED tonight (owner said "го все по очереди")** | **P1 wrapper bug fixed:** `weekly-intel-report.ps1`, `weekly-repo-scout.ps1`, `skill-feedback-update.ps1` (all `~/.claude/scripts/`, untracked personal automation, not part of this repo) now check `$LASTEXITCODE` after `claude -p` and log/exit FAILED instead of silently printing DONE on a 401 or any other failure — matches the pattern `run_collectors.ps1` already had. The stale-`ANTHROPIC_API_KEY` root cause itself is still unfixed (owner's credential, not mine to touch) — these 4 scheduled tasks will now at least report failure honestly instead of looking green. **P2a resolved (owner explicitly approved via AskUserQuestion):** live `~/.claude/settings.json` Stop event now includes `commit_test_gate.py` (was repo-only per `find_event_registration_drift`) — this is a real turn-blocking mechanism (exit 2) if source .py changed after the last pytest run, but fires on Claude's own Stop, never a user-facing dialog, so it doesn't conflict with the solo-autonomy HARD RULE above. Backed up live settings.json first. **P2b done:** `commands/release-scout.md` copied to `~/.claude/commands/release-scout.md` — `/release-scout` is now invocable. Scheduling it weekly is a separate standing-config decision (the file's own text treats it as opt-in via `scripts/setup_release_scout_schedule.*`, dry-run by default) — deliberately NOT done tonight, flagged for the owner given today's unrelated scheduled-task fragility. |
| **overnight audit-fix backlog — PART 1 (2026-09-02/03 night, autonomous)** | External 7.2/10 repo audit response. [VERIFIED: `gh pr view <n> --json state,mergedAt`] Confirmed real and merged: PR #323 (test-file-class `Edit()` denies removed from the `hooks/settings.json` TEMPLATE), PR #324 (`install.sh --non-interactive` no longer silently replaces a differing existing file; `--force-replace` is the explicit opt-in; also fixed a v2.1/v11.1 version-string contradiction), PR #325 (`@pytest.mark.security` on `test_guard_corpus_baseline.py`, making its known guard-defect xfails visible to the security-critical slice). |
| **overnight audit-fix backlog — PART 2 (2026-09-03 morning, owner said "го все по очереди" then "го все по очереди автономно"): the 4 items Part 1 wrongly dismissed were ALL real** | Re-verified with the correct tool invocation this time (`ruff check --extend-select` not `--select`, properly scoped to `hooks/+scripts/` not the whole repo) — every one of the 4 previously-dismissed audit numbers turned out exact. **PR #327:** 74 genuinely-unused `# noqa` directives removed (audit said 81; my first pass's "33" was a flawed grep). Caught and reverted my OWN mistake before committing: `--select RUF100` replaces the project's rule set instead of extending it, which would have deleted 10 still-needed `noqa: E402` comments. **PR #328:** security-diagnostics count matched exactly at 80 once properly scoped; found and removed a genuinely dead, unsafe `send_webhook()` in `hooks/lib/security.py` (zero SSRF validation, zero callers, superseded by `webhook_notify.py`'s hardened version) plus an `md5(usedforsecurity=False)` fix; the other ~76 findings were triaged individually and are documented false-positives/accepted-risk-by-design in the commit message, not blindly suppressed. Cyclomatic complexity (43 functions, confirmed exact) and registry provenance (65/137 author, 12/137 source, confirmed exact) were both reviewed and deliberately left unfixed — high regression risk for the former, manual data entry for the latter — not silently ignored, explicitly triaged. **PRs #329/#330:** GitHub's own Codex bot then reviewed #328's fix and found 2 real follow-up bugs missed before merging (facade broke `from utils import send_webhook` for a hypothetical external consumer; the replacement had a different signature/return type than the original) — both fixed. Codex then reviewed the xfailed/xpassed-visibility fix in #330 and found 1 real bug (a coexisting xfail could mask a genuine pytest setup error) and 1 hallucinated finding (cited a commit hash that does not exist in this repo's history) — the real one fixed, the fake one dismissed with the verification trail recorded. Full detail: `.claude/memory/decisions.md` §2026-09-03 (two entries: SEC-02 follow-up, and the Codex-findings-pattern entry). **Process fix mid-session:** running a reviewer/sec-auditor agent against the shared working directory while continuing to `git checkout` other branches corrupted 2 review passes — fixed by using `git worktree add --detach` to isolate concurrent reviews. Full suite after final merge: 3028 passed, 1 pre-existing unrelated failure (`test_check_global_hooks.py`). |
| **next action** | Obsidian session-note update for this morning's completion work (in flight). After that: resume the still-open **§8 direction** — waiting on the owner to name a concrete hypothesis/subject for `hypothesis-arbiter`/`claim-pipeline` (not itself a task without one). Also open, non-urgent: the stale `ANTHROPIC_API_KEY` (owner's credential fix); whether to arm `/release-scout` weekly; `claude-md/CLAUDE.md`'s RULES list still missing 6 real `rules/*.md` references (`estimand-ops.md`, `evidence-markers.md`, `falsification-ladder.md`, `perelman-audit.md`, `research-methodology.md`, `skeptic-triggers.md`). |




## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication




## Auto-commit log
- [2026-09-03 23:32] `d23d691`: docs(memory): auto-log commit 71d912a
- [2026-09-03 23:32] `71d912a`: fix(memory): delete idf sidecar on partial write, don't leave it stale
- [2026-09-03 23:19] `3145132`: docs(memory): auto-log commit 8dc98fa
- [2026-09-03 23:19] `8dc98fa`: fix(memory): compute real corpus-wide TF-IDF, not TF-only
- [2026-09-03 22:50] `a8b87bc`: docs(readme): sync test count to CI-reported 3052 (was 3048)
- [2026-09-03 22:46] `9871d7b`: docs(memory): auto-log commit 3f314c8
- [2026-09-03 22:46] `3f314c8`: fix(tests): mock _get_embedder too, not just _get_chroma_collection
- [2026-09-03 22:36] `c130252`: docs(memory): auto-log commit 76a38a1
- [2026-09-03 22:36] `76a38a1`: fix(memory): fall back to TF-IDF when Chroma has no embedder, report writes honestly
- [2026-09-03 22:20] `e88fd00`: docs(memory): auto-log commit 6a01fa0
- [2026-09-03 22:20] `6a01fa0`: fix(memory): don't wipe the index on a total transient failure
- [2026-09-03 22:10] `766143c`: docs(memory): auto-log commit 584a111
- [2026-09-03 22:10] `584a111`: docs(readme): sync test count to CI-reported 3048 (was 3045)
- [2026-09-03 22:06] `1bc4d8e`: docs(memory): auto-log commit d16d95c
- [2026-09-03 22:06] `d16d95c`: fix(memory): atomic batch rebuild that actually removes stale entries
