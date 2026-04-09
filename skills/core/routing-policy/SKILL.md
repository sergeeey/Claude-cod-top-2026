---
name: routing-policy
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-13]
  ALWAYS CHECK before starting ANY task. Decision routing matrix for
  task→skill→agent→tools selection. Determines optimal execution path.
  Triggers: any task, start of work, new request, plan, task,
  implement, fix, debug, review, add, create, build, change.
---

# Routing Policy — Task Routing Matrix

## Current State (auto-injected)
```
!`git status --short 2>/dev/null | head -15`
```
```
!`git diff --stat 2>/dev/null | tail -5`
```

## How to Use

Before starting ANY task, identify its type and follow the route.

## 4-Stage Workflow

Every task passes through these stages in order. Use them as a mental checklist:

| Stage | Goal | Maps to |
|-------|------|---------|
| **1 — Research** | Understand before acting | Type 1, or Explore agent for Types 2-5 |
| **2 — Planning** | Design before coding | Types 2-3 (brief plan or EnterPlanMode) |
| **3 — Acting** | Execute with evidence | Types 2-6 execution routes |
| **4 — Review** | Verify and capture | reviewer agent + session-retrospective skill |

**Hard rule:** Never skip Stage 1 to jump directly to Stage 3.
Symptoms of skipping: editing without reading, committing without testing, closing task without review.

## Routing Matrix

### Type 1: Research / Question
**Signals:** "what is this", "how does it work", "where is it", "why", explain, find, search

**Route:**
1. Explore subagent → Read/Grep/Glob (local tools)
2. If not found locally → MCP (Context7, PubMed, WebSearch)
3. Mark every fact according to Evidence Policy

**Hard rule:** local tools first, then MCP. Do not call MCP without first trying locally.

### Type 2: Code Change (1-2 files)
**Signals:** "change", "add", "fix" + specific file/function

**Route:**
1. Read target file(s) in full
2. Brief plan in response (not EnterPlanMode)
3. Edit/Write
4. Run tests (`pytest -x -q` or equivalent)
5. If tests fail → Read the error, understand the cause, THEN fix
6. Commit

### Type 3: Code Change (3+ files)
**Signals:** "refactor", "new feature", "migration", multi-file change

**Route:**
1. EnterPlanMode (plan_mode_guard fires automatically)
2. navigator agent (Opus) → decompose into tasks
3. builder agent (Sonnet) → implement each file
4. tester agent (Sonnet) → tests
5. reviewer agent (Opus) → code review
6. Commit

### Type 4: Writing Tests / TDD
**Signals:** "tests", "test", "coverage", "TDD", "with tests", "cover with tests"

**Route:**
1. Load tdd-workflow skill (auto-loaded by trigger)
2. RED → GREEN → REFACTOR
3. NEVER write implementation before tests

### Type 5: Debugging
**Signals:** "crashes", "error", "not working", "bug", error, fail, broken, debug

**Route:**
1. Read full traceback / error message
2. Explore subagent → search context in codebase
3. Hypothesis [INFERRED] with chain of reasoning
4. Verify hypothesis with a tool → [VERIFIED]
5. If 3 attempts failed → Stuck Detection → STOP → ask user

### Type 6: Security / Compliance
**Signals:** "audit", "security", PII, SQL, auth, payments, .env

**Route:**
1. Load security-audit skill
2. reviewer agent → code review
3. Check deny-list (17 patterns)
4. If working with PII → confirm redaction hook is active

## Hard Guards — Absolute Rules

These rules override ANY rationalization:

| Guard | Rule | Prevents |
|-------|------|---------|
| **Read Before Edit** | Do NOT edit a file without reading it first | Hallucination Loops |
| **Local Before MCP** | Do NOT call MCP without trying locally first | Wasted tokens |
| **Plan Before Multi-Edit** | Do NOT edit 3+ files without a plan | Chaotic changes |
| **Test Before Commit** | Do NOT commit without running tests (if tests exist) | Broken commits |
| **Evidence Before Claim** | Do NOT assert a fact without an Evidence Policy marker | Hallucinations |

## Task Type Identification

If the task does not clearly fall into one type:
- Contains "test/coverage" → **Type 4** (TDD) takes priority
- Contains "error/bug" → **Type 5** (Debugging) takes priority
- Contains "security/PII/auth" → **Type 6** (Security) takes priority
- Touches 3+ files → **Type 3** (Multi-file) is mandatory
- Anything else → **Type 2** (Simple change) by default

## Skill Execution Order (Layers)

When multiple skills could activate, follow this priority:

| Layer | Priority | Skills | Rule |
|-------|----------|--------|------|
| 1 — SAFETY | Mandatory, always first | security-audit, routing-policy | Never skip. Check before any code change touching auth/PII/payments |
| 2 — QUALITY | Before implementation | tdd-workflow, brainstorming (if 3+ files) | RED before GREEN. Design before code |
| 3 — EXECUTION | Task-specific work | archcode-genomics, geoscan, notebooklm, mentor-mode, reference-registry | Load on trigger, one at a time |
| 4 — ENHANCEMENT | Post-task | git-worktrees, last30days, research-pipeline | Isolation, research, supplementary |
| 5 — REVIEW | Post-task | session-retrospective | Capture decisions, patterns, next focus |

If skills conflict: higher layer wins. Layer 1 can block Layer 3 (security blocks unsafe code). Layer 5 always runs last — it reviews, never blocks.

## Gotchas
- This skill is meta — it routes, not executes. Don't let it become a bottleneck
- If task type is unclear after 5 seconds — default to Type 3 (code change)
