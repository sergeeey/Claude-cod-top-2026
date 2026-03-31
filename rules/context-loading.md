# Context Loading Protocol

## Purpose
Every subagent reads shared project state before taking any action.
This prevents duplicate work, contradictory decisions, and stale output.
Cost: ~50–80 tokens per agent. Benefit: eliminates full re-runs.

## Protocol (5 steps, in order)

**Step 1 — Read activeContext**
```
.claude/memory/activeContext.md
```
This is the single source of truth for what is happening right now.
If the file does not exist, skip to Step 5.

**Step 2 — Extract current focus**
Locate the `## Current Focus` section. This is the task the orchestrator
assigned. All agent output must serve this focus unless explicitly told otherwise.

**Step 3 — Check recent topics**
If a state file or `## Recent Topics` section exists, scan it to avoid
repeating analysis already done in this session.

**Step 4 — Read sprint goals (if present)**
```
.claude/memory/goals.md  OR  ## Sprint Goals  in activeContext
```
Align deliverables with sprint scope. Do not gold-plate outside it.

**Step 5 — Proceed, carrying context forward**
Return results tagged with which context item they address.
Example: `[Focus: auth-refactor] Removed 3 redundant token checks.`

## Agent-Specific Rules

| Agent | What to read | Why |
|---|---|---|
| explorer / navigator | `recent_topics` in activeContext | Avoid re-discovering known facts; weight findings by current focus |
| builder / tester | `decisions.md` | Respect architectural constraints already decided |
| reviewer / verifier | `patterns.md` | Flag recurrences of known issues (`[AVOID]`, `[×N]`) |
| sec-auditor / security-guard | `activeContext` → data flows section | Identify which data crosses trust boundaries |
| architect | `decisions.md` + `goals.md` | Avoid contradicting prior ADRs; stay within sprint scope |

## Writing Back — Orchestrator Only

Agents do **not** write to memory files directly.
Agents **return** structured results to the orchestrator.
Orchestrator decides what, if anything, gets persisted.

Reason: concurrent writes from multiple agents corrupt shared state.

Exception: `tester` may append a single line to `activeContext.md`
under `## Test Status` when running in solo mode (no orchestrator present).

## Graceful Degradation

Missing file → proceed normally, do not error, do not fabricate content.

| Missing file | Fallback |
|---|---|
| `activeContext.md` | Use task description from the prompt |
| `decisions.md` | Apply project-wide defaults from `CLAUDE.md` |
| `patterns.md` | Skip pattern-check step, note it was skipped |
| `goals.md` | Treat current task as the full scope |

Context is a **bonus**, not a blocker. Absence of a file is not a failure.

## Inter-Agent File Contracts

When one agent produces output for another, use a file contract:
- Agent A writes result to a temp file (e.g., `/tmp/plan.md` or `.claude/memory/handoff.md`)
- Agent B's prompt includes: "Read [path] — this is your spec from [Agent A]"
- The file IS the contract: if it's missing or empty, Agent B stops and reports.

This is more reliable than passing context through the orchestrator prompt,
because files survive context compaction and can be inspected for debugging.

## Token Budget

- Read `activeContext.md`: ~30–50 tokens (file is kept ≤ 200 lines by protocol)
- Read one additional file (`decisions.md` etc.): ~20–30 tokens
- Total overhead per agent invocation: **50–80 tokens**
- This is negligible against the cost of re-doing work from scratch
