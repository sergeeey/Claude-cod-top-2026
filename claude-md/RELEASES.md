# Claude Code Features — What This Config Actually Wires

**Re-audited 2026-09-10 against a live install of v2.1.263.** The previous
edition was dated 2026-05-21 and described v2.1.141 — roughly 120 releases
behind. Every "we don't use feature X" observation about this repo traced back
to that one fact: the changelog was read once and never again. The re-audit
protocol at the bottom of this file exists so that does not repeat.

Older versions silently ignore unknown event names and missing fields, so this
config stays backward-compatible.

---

## Hook event coverage — measured, not estimated

The docs list **33** hook events. This config registers **24** of them
(counted 2026-09-10 from `hooks/settings.json` against
`code.claude.com/docs/en/hooks`).

**The nine not registered, each with a reason — this table is the point, not
the 24/33 ratio:**

| Event | Status | Why |
|---|---|---|
| `PermissionRequest` | **DELIBERATELY EXCLUDED — do not re-add** | Removed 2026-09-02 after `permission_policy.py` caused a permission-prompt storm in a solo workflow. Re-adding it "for completeness" reproduces a real, logged incident. Any future proposal must read that incident first, not merely note the gap. |
| `PermissionDenied` | **DELIBERATELY EXCLUDED — do not re-add** | Same incident, same reasoning. |
| `PreModelSwitch` | **PENDING — most powerful of the nine** | Fires before a model switch; receives `from_model`/`to_model`; the matcher runs against the canonical name derived from `to_model`; **exit code 2 blocks the switch**. Blocking is more power than this config currently needs — evaluate `PostModelSwitch` first. |
| `PostModelSwitch` | **PENDING — proposed next** | Fires after the model changes, including changes Claude Code makes on its own (e.g. restoring a model on resume). Same `from_model`/`to_model` payload. Asynchronous, with a reduced 30 s default timeout. Observation-only, so it can close the routing-calibration loop — predicted tier vs actual model vs outcome — with no blocking risk. |
| `Setup` | Not evaluated | No concrete use identified yet. |
| `UserPromptExpansion` | Not evaluated | |
| `PostToolBatch` | Not evaluated | |
| `MessageDisplay` | Not evaluated | |
| `DirectoryAdded` | Not evaluated | |

**Hard rule for the two excluded events:** "we only use 24 of 33" is not by
itself an argument for wiring the other nine. Two are excluded on evidence.
Coverage is not the goal; the right events are.

---

## Wired

| Feature | Where | Why it matters |
|---|---|---|
| `PreCompact` hook | `hooks/pre_compact.py` | Extracts TODO/PENDING from activeContext into goals.md BEFORE `/clear` loses them; progressive compression of activeContext.md |
| `PostCompact` hook | `hooks/post_compact.py` | Post-compaction state recovery |
| `WorktreeCreate`/`Remove` | `hooks/worktree_lifecycle.py` | Audit trail of every experiment worktree in `~/.claude/logs/worktrees.jsonl` |
| `worktree.baseRef: "head"` | `hooks/settings.json` | New worktrees branch from local HEAD (preserves unpushed commits) instead of `origin/<default>` |
| `effort.level` payload | `hooks/knowledge_librarian.py` | On `--effort low`, skip knowledge injection — saves ~200 tokens per session |
| `claude agents --json` | external tooling | Status-line scripts / tmux integration |
| Tool-call telemetry | `hooks/model_usage_tracker.py` → `scripts/otel_exporter.py` | Per-call model/tokens/duration to `~/.claude/logs/model_usage.jsonl`; exact `resolvedModel`/`totalTokens` for `Agent` calls, byte-proxy for other tools |

---

## Available and NOT wired — with a reason, so each gap is a decision

| Feature | Version | Status and why |
|---|---|---|
| **`/skill-doctor`** | v2.1.252+ — we run **2.1.263**, so **available today** | **NEXT ACTION.** Reports what each skill costs and how often it is used. With 134 skills here, this is the first first-party way to answer "which of these earn their place" by measurement rather than opinion. Must run in the terminal on the session's own machine — over Remote Control it returns `Skill usage reports are not available on this connection`. |
| **Native OTEL export** | `CLAUDE_CODE_ENABLE_TELEMETRY=1` | **PARTIAL.** This repo has its own tool-call tracker and OTLP exporter but does not consume Claude Code's own export, which adds `claude_code.cost.usage`, `claude_code.token.usage`, `claude_code.active_time.total`, and `cache_read_tokens` / `cache_creation_tokens`. ⚠️ It does **not** publish a cache *hit-ratio* metric, nor any per-skill / per-agent / per-plugin metric — a claim to the contrary was checked against the docs on 2026-09-10 and is wrong. Skill-level economics comes from `/skill-doctor`, not from OTEL. |
| **Bash sandbox** | `/sandbox` | **BLOCKED ON PLATFORM, not on effort.** Filesystem and network boundaries enforced by the OS (Seatbelt on macOS; seccomp/bubblewrap on Linux and WSL2). *Native Windows is not supported* — Claude Code must run inside a WSL2 distribution. The maintainer's machine is MSYS/MINGW64 on native Windows, so adopting this is a platform migration, not a task. Record the decision here when it is made. |
| `maxEffortLevel` | settings | Caps the effort level a user may select. Global, not per-model. |
| `modelSettings` | settings | Stores per-model effort levels — Claude Code saves a level per model. |
| `CLAUDE_CODE_SUBAGENT_MODEL` | env | Default model for subagents/teammates/workflow agents. Relevant to `hooks/resource_router.py`, which today only *advises* a model in prose — part of that routing could become declarative. |
| Managed Agents `Outcomes` | — | Could replace the `max_iterations=3` reviewer→builder loop with a native grader. Requires refactoring review-squad. Still deferred. |
| `PostToolUse updatedToolOutput` | — | No concrete point of application yet. |
| `mcp_tool` hook type | — | Needs a concrete use case (e.g. `mcp__obsidian__write_note` from a hook). |

---

## Re-audit protocol — the actual fix

The failure this file corrects was not a missing feature. It was a **one-shot
audit with no next date**: read 2026-05-21, never re-read, and every downstream
"we don't use X" followed from that.

**Cadence:** every two weeks, or immediately after a Claude Code bump whose
release notes mention hooks, settings, or slash commands.

**Procedure — four steps, each cheap:**

1. `claude --version` — record the installed version in this file's header.
2. Read the release notes since the version recorded last time.
3. For every new hook event / setting / command, add a row to **Wired** or to
   **Available and NOT wired** — *with a reason*. A row with no reason is not a
   completed audit entry.
4. Re-count registered events against the documented list and update the
   coverage section. That count is the cheap tripwire: if it moves without this
   file changing, the audit lapsed again.

**Hard rule:** an entry may stay `PENDING` indefinitely — that is a legitimate,
recorded decision. What is not legitimate is a feature that exists, is unlisted,
and is unlisted only because nobody looked. The distinction between "we decided
not to" and "we never checked" is the entire value of this file.

---

## Compatibility matrix

| Claude Code version | Behaviour |
|---|---|
| **v2.1.252+** | Everything above, including `/skill-doctor` |
| v2.1.141–v2.1.251 | Everything except `/skill-doctor` |
| v2.1.128–v2.1.140 | `PreCompact`/`PostCompact`/`WorktreeCreate`/`WorktreeRemove` active; `worktree.baseRef` honoured; `effort.level` absent → `knowledge_librarian` defaults to medium |
| v2.1.100–v2.1.127 | `PreCompact` active; `worktree.baseRef` ignored; `WorktreeCreate`/`Remove` unknown, silently skipped |
| < v2.1.100 | Unknown event names may break the whole settings file. **Upgrade required.** |

---

**Last audited:** 2026-09-10 against v2.1.263 (installed; verified with `claude --version`)
**Previous audit:** 2026-05-21 against v2.1.141
**Next audit due:** 2026-09-24
**Sources:** `code.claude.com/docs/en/{hooks,sandboxing,monitoring-usage,slash-commands,model-config}`,
each read directly during this audit rather than recalled from memory.
