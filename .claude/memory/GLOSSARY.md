---
name: project-glossary
description: Formal definitions of all core concepts in Claude-cod-top-2026. Read before implementing any hook, agent, or rule to prevent semantic drift between sessions.
metadata:
  type: reference
---

# Claude-cod-top-2026 — Formal Glossary

Borrowed from OpenCode's `CONTEXT.md` pattern: one file, precise definitions, agents read this at
session start to share vocabulary. Each term links to where it lives in the codebase.

---

## Evidence & Integrity

**[VERIFIED-REAL]** — Claim confirmed with real-world data (external URL, production file, live API
response). Required for hypothesis validation claims. `[VERIFIED-SYNTHETIC]` is NOT a substitute.
→ `rules/integrity.md`

**[VERIFIED-SYNTHETIC]** — Confirmed with synthetic/mock data. Valid for unit tests, INVALID for
hypothesis validation claims. Using this for validation = Validation Theater.

**[INFERRED]** — Logical conclusion from ≥1 verified fact. Must state the inference chain explicitly.

**[UNKNOWN]** — No confirmation exists. Preferred over a false [INFERRED].

**Validation Theater** — Presenting synthetic test results as real-world validation (e.g., F1=1.000
on self-generated data). Auto-detected by `hooks/validation_theater_guard.py`. Cardinal sin:
self-authored test + self-reported success without external data source.
→ `rules/skeptic-triggers.md` Trigger 5

**Submission Gate** — 4 mandatory checks before any external publication: (1) Skeptic agent run,
(2) Pre-submission checklist, (3) Text↔figures consistency check, (4) 24h cooling period.
No exceptions. → `rules/integrity.md` § SUBMISSION GATE

**Claim Scope Discipline** — The scope verified must equal the scope claimed. Running `mypy hooks/`
and claiming "mypy clean" (whole repo) is a violation. → `CLAUDE.md § CLAIM SCOPE DISCIPLINE`

---

## Falsification System

**FL (Falsification Ladder)** — Three-tier validation system. Micro: PR-inline 4 lines (question
type + claim + check + caveat). Standard: `experiments/<id>/` folder with claim.md + controls.md +
decision.md. Full: all 14 steps including estimand.md + DAG + skeptic Step 8a.
→ `rules/falsification-ladder.md`

**Zero-Signal Gate (Step -5)** — MANDATORY first step before any experiment: requires all three of
`(∃ entity) ∧ (∃ falsifiable predicate) ∧ (∃ measurable outcome)`. If any missing → emit
`REFUSE(no_falsifiable_claim)` and STOP. Structuring noise is a bug, not a feature.

**EstimandOps / L0 Classification** — Design-time layer before FL. Step 0: classify the research
question as Descriptive / Predictive / Causal. Then define estimand: population + intervention +
comparator + endpoint + summary measure + MCID + ICE strategy. Required before claim.md for
Full-Ladder. → `rules/estimand-ops.md`

**Claim Entropy** — Monotone invariant (Perelman): `N_unsupported_HIGH + N_hidden_assumptions +
N_missing_controls + N_ambiguous_definitions`. Must decrease at each valid step. If it doesn't
decrease, the step doesn't count. → `rules/perelman-audit.md`

**Kill Analysis** — Required in every REJECT `decision.md`: (1) what the null killed specifically,
(2) what was NOT killed (surviving assumptions), (3) Relaxation Map with one assumption changed
per variant. Missing Kill Analysis → `reject_gate_guard.py` emits a nudge.

**AOG (Anti-Overfitting Gate)** — 5 checks before promoting a hypothesis revision after a null
result: AOG-1 pre-registration, AOG-2 specificity, AOG-3 novel prediction, AOG-4 non-triviality,
AOG-5 independent motivation. Requires ≥3/5 to promote to `weak_alive`.

**CDT (Cheapest Differentiating Test)** — Test that maximizes
`(differentiation + kill_power + reuse_value) / cost`. Must be non-circular (cannot assume its
own conclusion). A cheap non-differentiating test is NOT a valid CDT.

**null_results/** — Directory for REJECTED experiments. Entry format:
`| id | date | slug | REJECT | why in 10 words |`. Never delete. Pre-checked by
`hooks/null_retroscan.py` on new NULL entry.

**parked/** — Directory for valid-but-deprioritized experiments (ARCHIVE verdict). Each entry
requires: original branch + what was killed + what survives + revival condition (explicit,
measurable) + next_check date.

**Pearl Registry** — `pearl_registry/INDEX.md`. Captures unexpected testable insights from
experiment side-effects. Required fields: `observation` + `falsifiable_prediction` +
`trigger_condition` + `next_check` date. Without `next_check` → pearl decays in 2 weeks.

---

## Agent Methodology

**DDD (Doubt-Driven Development)** — Red-team non-trivial decisions BEFORE implementation. Two
modes: DDD-skeptic gets full context + reasoning (design review: "right approach?"). FL-skeptic
gets ONLY claim.md + code, NO history (artifact review: "does it work?"). Both required for
Full-Ladder. → `rules/doubt-driven-development.md`

**Context Asymmetry** — FL Step 8a rule: skeptic receives ONLY `claim.md` + code, never session
history, reasoning chain, or success logs. Prevents agreeableness bias. Violating = invalid
skeptic pass.

**Skeptic Auto-Triggers** — 5 conditions that auto-invoke skeptic without user approval:
(1) ≥90% confidence / "100% SUCCESS", (2) success rate >2.5× base rate, (3) zero failures across
≥5 tests, (4) round numbers (F1=1.000), (5) synthetic evidence ([VERIFIED-SYNTHETIC] for
validation claim). → `rules/skeptic-triggers.md`

**Dispatcher** — `hooks/project_classifier.py`. Classifies project at session start as
research / production / MVP / data-science / unonboarded. Injects `[dispatcher]` verdict that
determines which methodology loads. Override in project `CLAUDE.md` if needed.

**Dual-Loop Engine (раскрытие⇅перепроверка)** — Two symmetric loops in research:
Divergent loop (раскрытие): generate hypothesis space, find falsifiable predictions, capture
pearls. Convergent loop (перепроверка): asymmetric audit, classify errors (4 types), promotion
gate, null-retroscan. Arbiter chooses loop by research stage. Default: skeptic-leaning (blocks
PROMOTE, not generation). → `rules/research-methodology.md`

**Perelman Audit** — Full research promotion protocol: claim_entropy decreases each step,
no-collapse tests (7 types: data swap, noise, scale, convention, negative control, adversarial,
alt-tool), surgery log for component replacements, external reconstruction required for HIGH
claims. 5 promotion conditions must ALL hold. → `rules/perelman-audit.md`

**whenToUse** — YAML frontmatter field in `agents/*.md`. Borrowed from OpenCode. Precise signal
to Dispatcher and skill-scout for agent routing. More reliable than prose descriptions.
Format: one sentence, imperative, includes trigger condition.

---

## State & Hooks

**HookState** — `hooks/hook_state.py`. Atomic JSON state store for stateful hooks. Centralizes
`<cwd>/.claude/state/<name>.json` path logic, atomic writes (tmp→rename), and load/save
boilerplate. Stdlib-only. Use instead of hand-rolling `_load_state`/`_save_state` in each hook.

**commit_test_gate** — Stateful hook (uses HookState("commit_test_gate")). Tracks `last_edit`
(any source .py modified) and `last_test` (any real pytest run). Warns at `git commit` if
`last_edit > last_test`. Soft nudge only.

**iteration_guard** — Stateful hook (uses HookState("eo_loop")). Counts consecutive non-LGTM
reviewer verdicts per `session_id`. Escalates at cap=3. LGTM resets counter.

**null_retroscan** — Fires on writes to `null_results/INDEX.md`. Tokenizes new NULL slug, scans
active PROMOTE `experiments/*/decision.md` for token overlap (≥2 tokens). Implements
research-methodology.md Principle 5: immediate retroscan on new NULL.

**reject_gate_guard** — Guards REJECT verdicts in `experiments/*/decision.md`. Requires non-empty
Kill Analysis and Relaxation Map. Soft nudge via `additionalContext`.

**Recursion Guard** — Every hook that reads memory or calls Claude MUST check
`os.environ.get("CLAUDE_INVOKED_BY")` → `sys.exit(0)` if set. Missing = infinite loop in
Agent SDK. No exceptions.

**Async Wrapper pattern** — `hooks/async_wrapper.py` runs a hook in background (stdout goes to
DEVNULL). NEVER wrap a hook that needs `emit_hook_result` — its stdout will be discarded silently.
→ `hooks/CLAUDE.md`

---

## Memory System

**activeContext.md** — Single source of truth for current session focus. All agents read at start
(Context Loading Protocol). Max 200 lines. Updated after each git commit. Summarized entries
marked `[summarized]`.

**Memory Protocol Dual-Path** — Each global memory file may exist at BOTH `~/.claude/memory/`
(canonical, preferred for edits) AND `~/.claude/memory/_auto/` (legacy auto-generated location).
ALWAYS check BOTH paths before declaring a file absent. Single-path absence ≠ "doesn't exist".
→ `rules/memory-protocol.md`, `rules/audit-verification-gate.md § Glob Path Trap`

**Glob Path Trap** — Searching ONE canonical path, getting "No files found," and claiming the
file doesn't exist. Requires checking ALL canonical paths (repo + `~/.claude/memory/` + project
memory) before using `[VERIFIED-ABSENT]`. Single-path = `[INFERRED-ABSENT]` only.
→ `rules/audit-verification-gate.md § Glob Path Trap`

---

## Permission System

**Permission Pattern** — String format: `ToolName(glob)` or `mcp__server__tool`. Valid tool
prefixes: Bash, Read, Write, Edit, Grep, Glob, Task, WebFetch, WebSearch, Skill, NotebookEdit,
Agent, mcp__. Validated by `scripts/validate_permissions.py`.

**PermissionRequest hook** — `hooks/permission_policy.py`. Programmatic auto-allow/deny for
Claude Code permission prompts. Resolves ~75% of prompts without user interaction. Three possible
outputs: `allow` (with optional `updatedInput`), `deny` (with `reason`), or exit 0 (pass to user).

---

## OTel / Observability

**model_usage_tracker** — `hooks/model_usage_tracker.py`. PostToolUse hook. Appends a JSONL
entry per tool call: `{ts, sid, tool, resp_bytes, inp_bytes, est_out_tok, est_in_tok}`. Byte-size
proxy for token estimation (accurate to ~4 chars/token). File: `~/.claude/logs/model_usage.jsonl`.

**otel_exporter** — `scripts/otel_exporter.py`. Reads `model_usage.jsonl` and either prints a
console summary or exports to an OTLP endpoint (requires `opentelemetry-sdk`). Degrades gracefully
without OTel installed. Supports `--tail` (follow mode), `--since`, `--otlp`, `--top N`.
