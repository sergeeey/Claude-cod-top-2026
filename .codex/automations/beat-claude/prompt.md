# Automation: Beat Claude
Schedule: daily 10:00

## Mission
Find ONE thing in the codebase where you can demonstrably do better than Claude.
Not nitpicking — a real improvement with measurable impact.

## Search Strategy
1. Pick a random hook file from hooks/
2. Read it fully
3. Ask: "If I rewrote this today with 2026 best practices, what would change?"
4. Check: performance, readability, security, trend alignment

## Output format
```
## 🏆 Beat Claude — [date]
**File:** hooks/X.py
**Current approach:** [what Claude wrote]
**Better approach:** [your suggestion]
**Why it's better:** [concrete reason — benchmark/CVE/pattern link]
**Effort to implement:** [S/M/L]
**Impact:** [what improves]

\`\`\`python
# Suggested implementation
...
\`\`\`
```

Save to: .codex/reports/beat-claude-YYYY-MM-DD.md
Tag: #improvement #competition

## Rules
- Must be a real improvement, not style preference
- Must cite why (benchmark, trend, security reason)
- Must be implementable in < 2 hours
- If nothing genuinely better found → write "Claude won today" + reason why
