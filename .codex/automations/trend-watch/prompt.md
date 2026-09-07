# Automation: Trend Watch
Schedule: weekly, Monday 09:30 (shifted from 09:00 to avoid colliding with
this machine's other Monday-morning scheduled tasks: Claude-RepoScout-Weekly
05:57, Claude-WeeklyIntel-Monday 07:03)

## Mission
Search the web for what changed in the last 7 days in:
1. Claude Code / Anthropic — new hooks, new events, new features
2. Python async patterns — anything deprecated or superseded
3. Security — new CVEs relevant to hook-based systems
4. AI agent tooling — new patterns for multi-agent coordination

## Output format
For each finding:
```
## [Category] — [Finding title]
**What changed:** ...
**Impact on this repo:** [HIGH/MED/LOW]
**File to update:** hooks/X.py or rules/Y.md
**Source:** [URL]
```

Then create a raw note at: reports/trend-watch-automation.md
with tag #trends #claude-code (the originally-requested
`~/.claude/memory/raw/` path is outside the project tree and rejected by the
`workspace-write` sandbox this automation actually runs under — confirmed
live 2026-09-07; a human can copy the note into real memory afterward if it
warrants it)

If HIGH impact found → search for an existing open issue with a matching
title first, then create a GitHub issue titled "trend: [finding]". Note:
`codex exec` runs with `approval: never`, so an issue-creation attempt
requiring interactive MCP approval will be rejected automatically — that is
expected, not a failure; the finding still stands, just undelivered as an
issue.
