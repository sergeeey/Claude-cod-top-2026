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
| **updated** | 2026-09-02, after PR #307 merged (main CI green on `79ebab5`) [VERIFIED: `git log -1`, `gh run watch`] |
| **goal** | Evidence-aware Goal Operating Layer for Claude Code — reusable, verifiable config (hooks/agents/skills/rules), self-checking against its own Falsification Ladder methodology. |
| **branch** | `main` = `79ebab5` (PR #307 merged) [VERIFIED: `git log -1`, `git branch --show-current`] |
| **released** | `v3.10.0` (tag + public GitHub Release); `boyko-baseline-v1`/`v2` are eval-suite reference tags, not releases |
| **tests** | 2973 CI-measured on main [VERIFIED: `gh run view` "Verify README metrics match reality" on `79ebab5`]; README badge synced to match |
| **current focus** | Implemented + shipped all 4 items from the "Frontier Agent Engineering 2026" gap-analysis Obsidian note (2026-09-02): (1) property-based tests for shell/pipe-table parsers (PR #305), (2) `file_lock()` AST-based repo-wide usage guard (PR #306), (3) security-critical reliability vector in CI, incl. reviewer-caught P1/P2 fixes for collection-error masking and skipped-count reporting (PR #308), (4) `postconditions` field on `capability.schema.json` (PR #307). All merged to main, CI green. |
| **next action** | None blocking. Open candidates from the last `/tracy` strategic pass (2026-08-28, still unaddressed): `hooks/session_save.py` split (1043-line God-module, 2 unrelated responsibilities), `utils.py` → `hooks/lib/` migration (stuck at 2/71 call sites since 2026-08-22), 3 named-but-untested shell-obfuscation techniques against `hooks/lib/security.py`. |


## Scope Fence

- **Goal:** production-ready Claude Code config for reuse across any project
- **Boundary:** only `hooks/` `agents/` `skills/` `rules/` — never touch external projects
- **Done when:** `install.sh` works on 3 machines, CI green, coverage ≥ 86%
- **NOT NOW:** GUI, web dashboard, SaaS, marketplace publication


## Auto-commit log
- [2026-09-02 01:52] `aa28ee4`: fix(readme): sync test count 2971->2973 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:50] `2924160`: merge main into feat/capability-postconditions-field
- [2026-09-02 01:47] `cee839f`: fix(readme): sync test count 2959->2961 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:47] `9b84957`: fix(readme): sync test count 2959->2971 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:45] `2d1a466`: merge main into feat/capability-postconditions-field
- [2026-09-02 01:44] `5bee5c7`: merge main into feat/property-based-parser-tests
- [2026-09-02 01:41] `ea1a7f2`: fix(readme): sync test count 2938->2959 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:38] `307c94b`: fix(scripts): reliability_vector correctly reports collection errors and skipped tests
- [2026-09-02 01:27] `d39954a`: merge main into feat/capability-postconditions-field
- [2026-09-02 01:26] `e3313f6`: merge main into feat/property-based-parser-tests
- [2026-09-02 01:24] `3d4ee5f`: feat(ci): security-critical reliability vector reported separately from aggregate
- [2026-09-02 01:20] `7a8147f`: chore: trigger CI re-run (previous push did not fire a workflow run)
- [2026-09-02 01:20] `3864541`: chore: trigger CI re-run (previous push did not fire a workflow run)
- [2026-09-02 01:16] `e7ecf0a`: fix(readme): sync test count 2934->2936 (CI-measured, matches this PR's actual run)
- [2026-09-02 01:14] `499265a`: fix(readme): sync test count 2934->2946 (CI-measured, matches this PR's actual run)
