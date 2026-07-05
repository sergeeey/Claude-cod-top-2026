# Global vs Project Overlay Policy

This doc answers one question: **if you install this config both globally
(`~/.claude`) and locally into a project (`--target=<project>/.claude`),
what actually happens when Claude Code runs?**

It matters because Claude Code does not treat project config as a
replacement for global config — it **merges** them. That has real
consequences for a repo like this one that ships 100+ hooks, a large
`CLAUDE.md`, and its own `settings.json`.

## What Claude Code itself does (not this repo's choice — the CLI's design)

Verified against the official docs (`code.claude.com/docs/en/settings`,
`.../memory`, `.../hooks-guide`):

| Config type | Behavior when both scopes exist | Source |
|---|---|---|
| `settings.json` permissions | **Merge, additive** — rules from user and project scope are both active | `docs/en/settings` |
| `settings.json` other keys | 5-tier precedence: Managed > CLI args > `.claude/settings.local.json` > `.claude/settings.json` (project) > `~/.claude/settings.json` (user) | `docs/en/settings` |
| `CLAUDE.md` | **Concatenated**, not overridden — managed policy, then `~/.claude/CLAUDE.md`, then project `CLAUDE.md`/`.claude/CLAUDE.md`, then `CLAUDE.local.md`, in that order (root → cwd) | `docs/en/memory` |
| Hooks (same event, e.g. `PreToolUse`) | **Both fire.** Every matching hook's command runs to completion; results are merged. One hook returning `deny` does not stop the others from running. For `PreToolUse`, the most restrictive verdict wins (`deny` > `defer` > `ask` > `allow`) | `docs/en/hooks-guide` |

**The one-sentence version: nothing here overrides. Everything layers.**

## What this means for this repo specifically

This repo's `install.sh` doesn't implement an "overlay" — it does a **full,
self-contained install to one target directory** (`$HOME/.claude` by
default, or anywhere via `--target=DIR`). It does not know whether another
copy already exists at a different scope, and it doesn't need to — Claude
Code's own merge behavior handles that at runtime, for better and worse.

**The gotcha:** if you install the `standard` or `full` profile globally
(`~/.claude`, no `--target`), *and* separately install it project-locally
(`--target=<project>/.claude`) for the same project, every one of the
~85 hooks in this repo now exists at **both** scopes. Since hooks merge
rather than override, Claude Code fires **both copies on every matching
event** — every `PreToolUse`/`PostToolUse`/etc. call runs the hook twice.
Concretely: `input_guard.py` scans the same tool input twice,
`log_hook_trigger()` writes two telemetry lines instead of one, and
per-call latency roughly doubles for the hooks layer. Nothing breaks
(idempotent hooks stay correct), but it's wasted work and doubled log
volume that's easy to not notice until you're debugging why
`hook_triggers.jsonl` has 2x the entries you expect.

Same logic applies to `CLAUDE.md`: install both scopes and Claude Code
concatenates both copies of this repo's `CLAUDE.md` into context on every
session — redundant tokens, not a correctness bug, but avoidable.

## Recommended pattern

```yaml
recommendation:
  default: "Install once, globally, no --target."
  when_to_add_project_local: >
    Only when you want project-specific ADDITIONS that don't exist
    globally — e.g. a project's own CLAUDE.md notes, or a narrow rule
    file specific to that repo. Use --profile=minimal for the
    project-local install in that case, not standard/full, so you're
    not duplicating the ~85-hook set on top of the global one.
  multi_machine: >
    "install.sh works on 3 machines" (this repo's own Scope Fence
    done-criterion) means re-running the SAME global install
    (--profile=standard --non-interactive, no --target) on each
    machine — it does not mean layering global+project on any one
    machine. Each machine's ~/.claude is independent; Claude Code has
    no cross-machine sync of its own.
  never: >
    Don't install standard/full at both --target=<project>/.claude AND
    globally for the same project on the same machine, unless you've
    deliberately accepted doubled hook execution and telemetry.
```

## Existing project-local duplicates

Checked this repo's own `.claude/` against the policy above, since a
doc about global-vs-project overlay should reflect the repo's actual
state, not just theory.

**No hook duplication today**: `.claude/hooks/` here contains only
`example-hook.py` (a placeholder), and `.claude/settings.local.json`
registers no hooks. Only the global install's ~85 hooks actually fire
while working in this repo — the double-execution gotcha above doesn't
apply here right now.

**One real duplicate, though — rule files, not hooks**: `.claude/rules/`
currently contains 4 files whose names overlap with root `rules/*.md`:

- `integrity`
- `doubt-driven-development`
- `rationalizations`
- `autonomy-budget`

These are not hooks and do not auto-fire — rules are loaded on demand via
`CLAUDE.md`'s routing table, not concatenated into every session like
`CLAUDE.md` itself. So this does not create double execution or doubled
telemetry. But two copies of the same rule can still drift silently:
edit one, forget the other, and the project-level and global-level
guidance quietly diverge with no error to catch it.

Policy for this specific case:

- Keep global/project hook installs non-overlapping (see above).
- Prefer one canonical rule source when the content is meant to be
  identical — a project-local copy of a rule file that's supposed to
  match the global one exactly is a maintenance liability, not a feature.
- Project-local rule copies are legitimate only when they intentionally
  override or narrow behavior for this specific project — not as an
  accidental leftover from an earlier install.

## Relationship to existing memory-scoping

`rules/memory-protocol.md` already documents this exact global-vs-project
split, but only for the `memory/` subsystem specifically (project
`activeContext.md`/`decisions.md` vs global `patterns.md`/`goals.md`/etc.).
This doc generalizes the same split to the full config surface this repo
ships: hooks, skills, agents, rules, `CLAUDE.md`, and `settings.json` —
and adds the one thing `memory-protocol.md` didn't need to cover, because
memory files don't fire on every tool call: **hooks actively double-execute
when duplicated across scopes, memory files just sit there unused.**

## What this doc does not cover

- Public-vs-private repo readiness (secrets, PII, what's safe to publish) —
  out of scope here; see `github-showcase-architect` skill for that audit.
- Personal identity data vs portable methodology (Sergey-specific `CLAUDE.md`
  IDENTITY section vs the generic rules) — a separate, not-yet-written
  policy question.
