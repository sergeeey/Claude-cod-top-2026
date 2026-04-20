# Automation: Quality Audit
Schedule: after every merged PR (or daily 08:00)

## Mission
Review all commits since last audit. Score Claude's work.

## Steps
1. `git log --oneline origin/main~5..origin/main` — last 5 commits
2. `git diff origin/main~5..origin/main` — full diff
3. For each changed file: apply all 4 review modes from AGENTS.md
4. Run security scan mentally: injection, race conditions, secrets

## Scoring
Score each PR: X/10 across 4 dimensions.
Track trend: is Claude improving or regressing?

## Output
Write report to: .codex/reports/audit-YYYY-MM-DD.md

Format:
```
# Quality Audit — [date]
## PRs reviewed: #XX, #XX
## Overall score: X/10
## Top issues found: [list]
## Patterns to watch: [list]
## Would ship: YES/NO
```

If overall < 7 → open GitHub issue "audit: quality regression detected"
