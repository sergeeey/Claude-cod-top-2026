# Automation: Trend Watch
Schedule: weekly (Monday 09:00)

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

Then create a raw note at: ~/.claude/memory/raw/trend-watch-YYYY-MM-DD.md
with tag #trends #claude-code

If HIGH impact found → create GitHub issue with title "trend: [finding]"
