# Automation: Quality Audit
Schedule: after every merged PR (checkpoint-gated poll every 30 min via
`~/.claude/scripts/on-merge-quality-audit.ps1` — the "daily 08:00" fallback
below is retired: cost measured at ~140k tokens/run on 2026-09-07, too
expensive to pay on a fixed daily tax when most days have no new commits at
all. See `null_results/INDEX.md` era decision recorded 2026-09-07 in this
repo's session notes for the actual numbers.)

## Mission
Review all commits since last audit. Score Claude's work.

## Steps
1. Read the checkpoint (last audited `origin/main` HEAD SHA). The invoking
   script passes the actual range for this run as an appended section below
   — use that range, not a fixed window. If invoked standalone with no range
   given, fall back to `origin/main~5..origin/main` (last 5 commits) and say
   so explicitly in the report.
2. `git log --oneline <range>` — commits since last audit
3. `git diff <range>` — full diff
4. For each changed file: apply all 4 review modes from AGENTS.md
5. Run security scan mentally: injection, race conditions, secrets
6. If the range contains zero commits (checkpoint already current), write a
   short no-change report instead of inventing a score — do not re-score an
   empty diff.

## Scoring
Score each PR: X/10 across 4 dimensions.
Track trend: is Claude improving or regressing?

## Output
Write report to: reports/audit-YYYY-MM-DD.md (`.codex/reports/` is read-only
in the sandbox this automation actually runs under — confirmed live
2026-09-07, use the project-root `reports/` directory instead).

Format:
```
# Quality Audit — [date]
## Range reviewed: <start-sha>..<end-sha>
## PRs reviewed: #XX, #XX
## Overall score: X/10
## Top issues found: [list]
## Patterns to watch: [list]
## Would ship: YES/NO
```

If overall < 7 → open GitHub issue "audit: quality regression detected"
(search for an existing open issue with that title first — do not open a
duplicate). Note: this repo's `codex exec` runs with `approval: never`, so an
issue-creation attempt that requires interactive MCP approval will be
rejected automatically — save the drafted issue text locally
(`reports/audit-YYYY-MM-DD-issue.md`) when that happens rather than treating
the rejection as a failure.
