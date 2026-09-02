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
| **updated** | 2026-09-02 evening, after PR #311 merged, PR #312 (P0) open, permission_policy deny-only fix pending PR [VERIFIED: `git log -1`, `gh pr view 312`] |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config (hooks/agents/skills/rules), self-checking against its own Falsification Ladder methodology. |
| **branch** | `main` = `61a07ee` (PR #311 merged); `fix/ifs-default-operators-erasure-p0` = PR #312 open (CI watching); `fix/permission-policy-deny-only` = next, uncommitted at time of writing |
| **released** | `v3.10.0` (tag + public GitHub Release); `boyko-baseline-v1`/`v2` are eval-suite reference tags, not releases |
| **tests** | 2998 local on #312 branch (2 pre-existing unrelated failures: `test_vector_store` live-drift, `test_check_global_hooks` hardcoded path); README badge is CI-authoritative, re-sync after #312 lands |
| **HARD RULE — solo autonomy (owner, angry, 2026-09-02 17:xx)** | ZERO tool-level confirmation prompts. I caused a prompt storm across 4–5 open sessions by re-wiring `permission_policy.py` to `PreToolUse/Bash` (its `decide()` returns "ask" on any `&&`/`;`/`|`); also added `Edit(**/test_*.py)`-class denies that blocked test edits. Both reverted within the hour; permission_policy `main()` now emits ONLY on "deny" (silent on ask/allow → static `Bash(*)` allow applies). Full rule + WHY in auto-memory `feedback_solo_autonomy_no_confirmations.md`. Never register an "ask"-emitting hook on his live machine again; never add source/test file-class denies. Deny-only security is welcome; anything that prompts is the wrong step. |
| **DEFAULT FOCUS BIAS (owner decision, 2026-09-02)** | When no explicit direction is given, bias work toward Constitution **§8 experimental packs** (`scientific-discovery`: sci-hypothesis, hypothesis-arbiter, boyko-*, consilience, proof-ladder; `claim-pipeline`; `self-development`) — NOT further polishing of §7 stable packs (hooks/security/CI). Rationale: owner's stated purpose for the repo is a **solo testing ground for scientific-hypothesis methodology across many projects**; the infra backlog that dominated 2026-09-02 is now essentially closed. Explicit owner direction always overrides this bias — infra work stays legitimate when asked for. |
| **target user (Constitution §2, RECONFIRMED 2026-09-02)** | Solo — the author only. NOT a team product. No access control / multi-author memory / human-reviewer workflows needed. |
| **review threshold (owner-reviewed 2026-09-02, /tracy)** | KEEP AS IS: reviewer mandatory at 3+ files OR security-critical. Evidence from this session: cost of review correlates with *branching logic over untrusted input*, not diff size (87-file mechanical migration = 1 cheap pass; 1-file `$IFS` parser fix = 3 expensive rounds, each finding a real bug). Do NOT narrow the 3+ files trigger — it is what caught `reliability_vector.py`'s P1, which was not security-tagged. |
| **current focus** | 2026-09-02 shipped: property-based parser tests (#305), `file_lock()` AST guard (#306), security reliability vector (#308), `postconditions` schema field (#307), `utils.py`→`lib/` migration of all 86 in-repo call sites (#310), and a real `$IFS` shell-obfuscation bypass fix in `hooks/lib/security.py` (#311, 3 review rounds). Live `~/.claude/hooks` redeployed (70 files) — `live-drift-guard` now clean. |
| **next action** | **In flight (2026-09-02 evening):** PR #312 (P0 IFS default-operator erasure fix + `find_event_registration_drift`) — CI re-running after README 2989→2999 sync; merge when 3.12 is green (gate on the 3.12 job explicitly — `gh pr checks --watch` exit 0 lied once today when `tail` cut the failing line). Then branch `fix/permission-policy-deny-only` from fresh main, commit the uncommitted `hooks/permission_policy.py` + `tests/test_permission_policy.py` edits (main() emits only on "deny"; 95/95 local), push, PR, README sync (+3 tests → ~3002), merge. Live `~/.claude` already has both the P0 security.py AND deny-only permission_policy.py deployed and re-registered on `PreToolUse/Bash` — verified: chained cmd → 0 bytes stdout, `sudo` → deny. **P1 — automation silently dead:** all 4 `Claude-*` Windows scheduled tasks fail weekly (`WeeklyIntel-Monday`, `RepoScout-Weekly`, `Collectors-Saturday`, `SkillFeedback-ResearchAudit`; only `graphify-weekly` returns 0). Root cause in `~/.claude/logs/weekly-intel-2026-08-24.log`: `401 API key is invalid` — stale `ANTHROPIC_API_KEY` env var overrides the claude.ai login in non-interactive `claude -p`. Last real output: repo-scout 08-23, weekly-intel 08-24. Wrappers print `DONE` on failure (no exit-status check). Owner must fix the key/env himself (credential — not mine to touch). **P2a:** `commit_test_gate.py` registered on `PreToolUse+PostToolUse+Stop` in repo but only `PreToolUse+PostToolUse` live — found by the new drift check; detected only, owner decision. **P2b:** `commands/release-scout.md` (the "watch the field weekly" scout) exists in-repo, never deployed to `~/.claude/commands/`, never ran once. **DONE today:** `Edit(**/secrets/**)` added live (was the P1b gap). |



## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication



## Auto-commit log
- [2026-09-02 17:35] `8fe4be3`: fix(readme): sync test count 2989->2999 (CI-measured on PR #312)
- [2026-09-02 17:29] `d6caeb2`: fix(security): exclude IFS default/assign/error operators from normalization (P0)
- [2026-09-02 16:00] `a736165`: fix(readme): sync test count 2973->2989 (CI-measured on this PR)
- [2026-09-02 15:24] `bac1322`: fix(security): close $IFS shell-obfuscation bypass in dangerous-command detection
- [2026-09-02 08:51] `c865e20`: refactor(hooks): migrate all internal call sites off the utils.py facade
- [2026-09-02 08:32] `67cb43a`: docs(memory): update activeContext.md after PR #305/#306/#307/#308 merged (#309)
- [2026-09-02 01:52] `aa28ee4`: fix(readme): sync test count 2971->2973 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:50] `2924160`: merge main into feat/capability-postconditions-field
- [2026-09-02 01:47] `cee839f`: fix(readme): sync test count 2959->2961 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:47] `9b84957`: fix(readme): sync test count 2959->2971 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:45] `2d1a466`: merge main into feat/capability-postconditions-field
- [2026-09-02 01:44] `5bee5c7`: merge main into feat/property-based-parser-tests
- [2026-09-02 01:41] `ea1a7f2`: fix(readme): sync test count 2938->2959 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:38] `307c94b`: fix(scripts): reliability_vector correctly reports collection errors and skipped tests
- [2026-09-02 01:27] `d39954a`: merge main into feat/capability-postconditions-field
