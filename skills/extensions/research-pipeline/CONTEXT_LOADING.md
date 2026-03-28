# CONTEXT LOADING Protocol for last30days agents

This section must be included in every agent's SKILL.md or system prompt.
It ensures each agent in the swarm starts with awareness of project state
instead of operating in isolation.

---

## CONTEXT LOADING

**Critical: Before any action, synchronize with project state.**

```
Step 1 — Read shared state
  cat ~/.claude/memory/activeContext.md 2>/dev/null || echo "No context yet"
  cat ~/.claude/memory/last30days_state.json 2>/dev/null || echo "No state yet"

Step 2 — Extract current focus
  Parse "## Current Focus" section from activeContext.md.
  If present: bias your queries and synthesis toward this focus area.

Step 3 — Check recent topics
  Parse "recent_topics" from last30days_state.json.
  If topic was researched in the last 7 days: note this in output headers.
  If topic is identical to a recent run: warn the orchestrator before proceeding.

Step 4 — Read sprint goals (if present)
  cat ~/.claude/memory/sprint_goals.md 2>/dev/null

Step 5 — Proceed with task
  Carry context forward into every decision: query construction,
  source prioritization, synthesis framing, follow-up suggestions.
```

**If any context file is missing: proceed normally with empty context.**
Context is a bonus, not a blocker. Graceful degradation is required.

---

## Agent-specific CONTEXT LOADING rules

### Discovery agents (Reddit, X, YouTube, HN, web, Polymarket)
- Use `recent_topics` to add complementary angles to query
  - Example: if "Claude Code skills" was recent, search for "Claude Code plugins 2026" instead of repeating
- Use `current_focus` to weight sources:
  - Focus = "technical": prioritize HN, web
  - Focus = "community": prioritize Reddit, X
  - Focus = "trends": prioritize X, YouTube

### Funnel agent
- Check `decisions.md` for any custom scoring weights saved by the user
  - Example: user may have written "weight Polymarket × 1.5 for prediction topics"
- Load `patterns.md` for known false-positive patterns to exclude in dedup

### Synthesis agent
- Use `recent_topics` list to generate NON-OVERLAPPING follow-up suggestions
- If `current_focus` is set, frame TL;DR to address that focus directly
- Check `decisions.md` for preferred output format preferences

### Verifier agent
- Check `patterns.md` for known low-quality sources to flag automatically
- Use `run_history` to compare confidence trends over time:
  - If last 3 runs were LOW confidence: emit additional warning

---

## Writing back to shared state

After completing work, agents write results using `SharedState.update_last_run()`.

The orchestrator handles all writes — individual agents do NOT write state directly.
This prevents race conditions when multiple agents run in parallel.

**What gets written:**
```json
{
  "run_history": [
    {
      "topic": "Claude Code skills",
      "timestamp": "2026-03-28T10:00:00Z",
      "elapsed_s": 38.4,
      "confidence": "HIGH",
      "items": 24
    }
  ],
  "recent_topics": ["Claude Code skills", "AI agent tools 2026"]
}
```

**What gets appended to activeContext.md:**
```markdown
## Last run
- **Topic**: Claude Code skills
- **Time**: 2026-03-28 10:00 UTC
- **Elapsed**: 38.4s
- **Confidence**: HIGH
- **Items**: 24 ranked
```

---

## Blackboard pattern (advanced)

For parallel swarms with >4 agents, use the blackboard pattern:

1. Orchestrator creates `/tmp/last30days_board.json` at session start
2. Each discovery agent APPENDS its results to the board (atomic write with file lock)
3. Funnel agent READS the completed board once all agents signal done
4. Signals are a simple counter file: `/tmp/l30_done_{source}` (touch to signal)

```python
# Atomic append pattern (prevents race conditions)
import fcntl, json

def board_append(items: list[dict], source: str) -> None:
    board_path = Path("/tmp/last30days_board.json")
    with open(board_path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        for item in items:
            f.write(json.dumps(item) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
    # Signal completion
    Path(f"/tmp/l30_done_{source}").touch()
```

---

## Token budget

This CONTEXT LOADING section adds approximately **~150 tokens** to each agent's
context window. At 6 agents × 150 tokens = 900 tokens overhead per pipeline run.

At ~$3.00/M tokens (Sonnet), this costs **$0.0027 per full pipeline run** — negligible
compared to the coordination benefit of context-aware agents.

For `--quick` mode: skip Steps 2–4, read only `recent_topics` (Step 3).
Budget: ~50 tokens per agent.
