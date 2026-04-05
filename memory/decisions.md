# Architectural Decisions — Claude Code Config

## Format
### [DATE] Decision Name
- **Problem:** what needed solving
- **Decision:** what was chosen
- **Rationale:** why this approach
- **Status:** active / superseded / revisited

---

### [2026-04-04] Fix regex replacement in webhook_notify.py
- **Problem:** `_SECRET_PATTERN.sub(r"\1=[REDACTED]", summary)` raised `PatternError`
  on Python 3.13 — all alternations used non-capturing `(?:...)`, so `\1` was invalid.
- **Decision:** Changed to `_SECRET_PATTERN.sub("[REDACTED]", summary)` — replace full match.
- **Rationale:** Simpler and correct. The capture group was never needed; we want to replace
  the entire secret match, not a sub-group of it.
- **Status:** active

### [2026-04-04] Coverage gate: 38% → 45%, target next: 60%
- **Problem:** CI gated at 38% — honest but too low for "production-grade" claim.
- **Decision:** Added 168 tests across 5 zero-coverage hooks. Gate raised to 45%.
- **Rationale:** Risk-weighted approach — covered keyword_router, permission_policy,
  evidence_guard, security_verify, webhook_notify first (all HIGH-RISK, all were 0%).
- **Status:** active — next step: scripts/ coverage (doctor.py, weekly_review.py)

### [2026-04-04] Eval job: workflow_dispatch + schedule, continue-on-error
- **Problem:** Eval corpus existed (6 TCs) but was never run in CI — manual only.
- **Decision:** Added `eval` CI job triggered by `workflow_dispatch` and weekly cron
  (Monday 06:00 UTC). `continue-on-error: true` — eval is informational, not a gate.
- **Rationale:** LLM responses are non-deterministic and API calls cost money. Running
  on every push would waste budget and create flaky CI. Weekly + manual is the right cadence.
- **Status:** active

### [2026-03-31] v3.2.0: 5 new hook events (TaskCreated, TaskCompleted, InstructionsLoaded, Elicitation, ElicitationResult)
- **Problem:** TaskCreated/Completed events not hooked — no visibility into agent task lifecycle.
- **Decision:** Added task_audit.py, instructions_audit.py, elicitation_guard.py, subagent_verify.py.
- **Rationale:** Full 25/25 hook event coverage. Observability layer for agent quality.
- **Status:** active

### [2026-03-31] 4 agents restored from _archived/ (security-guard, scope-guard, fe-mentor, skill-suggester)
- **Problem:** Agent count dropped to 9 after cleanup — useful agents were archived too aggressively.
- **Decision:** Restored all 4 with `effort` field and `permissionMode: acceptEdits` for builder/tester.
- **Rationale:** All 4 serve distinct purposes with no overlap. Archiving them reduced coverage.
- **Status:** active — 13 agents + 3 teams

### [2026-03-30] v3.0.0: Split monolithic CLAUDE.md → modular 6-layer architecture
- **Problem:** Single CLAUDE.md grew to 3000+ tokens, loaded on every message.
- **Decision:** Layer 1 (CLAUDE.md, 500 tok, always) + Layer 2 (rules, 0 tok, on-demand)
  + Layer 3 (skills, triggered) + Layer 4 (agents, isolated) + Layer 5 (hooks, 0 tok runtime)
  + Layer 6 (MCP profiles, switchable).
- **Rationale:** Token economy: ~500 tokens/message vs 3000+. Hooks enforce policy
  deterministically without consuming context window.
- **Status:** active — core architecture

### [2026-03-30] Hooks enforce policy, not instructions
- **Problem:** CLAUDE.md documented Evidence Policy, TDD, PII rules — but nothing enforced them.
  Claude could ignore any instruction.
- **Decision:** Move enforcement to Python hooks (PreToolUse, PostToolUse, UserPromptSubmit).
  Hooks run 100% of the time, cannot be skipped by the model.
- **Rationale:** `[VERIFIED] vs [INFERRED]` distinction: hook execution is deterministic,
  prompt instructions are probabilistic. Hard guards belong in hooks.
- **Status:** active

### [2026-03-30] permission_policy: dangerous patterns checked BEFORE chain operators
- **Problem:** Design question — which check has priority: dangerous pattern or chain operator?
- **Decision:** Check DANGEROUS_PATTERNS first, CHAIN_OPERATORS second, SAFE_PREFIXES third.
- **Rationale:** A command with a dangerous pattern (`rm -rf`) is always denied regardless of
  chain operators. Chain operators only escalate to "ask" when no dangerous pattern is found.
  Deny > Ask > Allow is the correct security ordering.
- **Status:** active — verified by test_permission_policy.py::TestDecidePriority

### [2026-03-30] MCP CircuitBreaker: CLOSED/OPEN/HALF_OPEN with 60s recovery
- **Problem:** MCP server failures caused session hangs — no automatic recovery.
- **Decision:** CircuitBreaker with state machine: CLOSED (normal) → OPEN (3 failures) →
  HALF_OPEN (probe after 60s) → CLOSED (probe succeeds) or OPEN (probe fails).
- **Rationale:** Standard resilience pattern. 60s recovery window prevents thundering herd.
  mcp_circuit_breaker.py at 98% coverage — highest-coverage hook.
- **Status:** active
