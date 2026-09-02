# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **not an application** — it's a distributable Claude Code configuration:
hooks, skills, agents, and rules that other people install into their own
`~/.claude/`. `claude-md/CLAUDE.md` is the actual deliverable (a template
`install.sh` copies to `~/.claude/CLAUDE.md` on the end user's machine) — it
is a separate artifact from this file, not something to edit when working on
the repo itself. This file (root `CLAUDE.md`) is for developing *this repo*.

## Commands

```bash
pip install -r requirements.txt

# Full suite (what CI runs, minus the Linux/Windows-only steps)
pytest tests/ -q
ruff check .
mypy --ignore-missing-imports hooks/ scripts/

# Single test
pytest tests/test_architecture.py::TestClassName::test_name -q
pytest tests/test_weakened_test_guard.py -k "hook_main" -q

# Architecture/registry gates (all must pass before merge — see below)
python scripts/check_architecture.py --check
python scripts/gen_hook_matrix.py --check
python scripts/sync_doc_counts.py --check
python scripts/sync_plugin_hooks.py --check

# Shell/install smoke tests
bash tests/test_all.sh
```

CI is Linux (`ubuntu-latest`, Python 3.11 + 3.12); local Windows runs collect
a handful more/fewer environment-dependent tests (some hooks need the live
`~/.claude` global install). **When updating README badges, use the exact
`Actual: N tests, M% coverage` line CI prints — never a local count**
(`scripts/sync_readme_from_ci.py` does this from the latest main run; for an
open PR, read the number directly from that PR's own CI log).

Use `datetime.now(timezone.utc)`, never `datetime.utcnow()` (ruff's `DTZ`
rule enforces this; a few pre-existing hooks are grandfathered via
per-file-ignores in `pyproject.toml`).

## Architecture

### The core mechanism: registries + gates, not code review

Three declarative registries are the source of truth for what's installed;
Python scripts cross-check each registry's *claims* against the *actual*
files/wiring on disk, and CI hard-fails on any mismatch:

| Registry | Declares | Checked by |
|---|---|---|
| `hooks/registry.yaml` | every hook's `class`/`fail_mode`/`event`/`escalation` | `scripts/gen_hook_matrix.py --check` (generates `docs/hook-control-matrix.md`) |
| `skills/registry.yaml` | every skill's `kind`/`maturity`/`depends_on`/capability contract | `scripts/check_architecture.py --check` (11 numbered gates, see its own module docstring) |
| `agents/*.md` frontmatter | an agent's real identity (`name:`, not filename) | gate 9 in `check_architecture.py`, resolves both filename and frontmatter name |

**Do not add a hook/skill/agent without updating its registry entry in the
same PR** — CI will catch the drift, but the fix belongs with the change,
not as a follow-up. When touching `hooks/registry.yaml`'s `fail_mode`, note
it is **orthogonal** to a hook's own `hook_main(fn, fail_closed=...)` call
(`hooks/lib/runtime.py`): `fail_mode` describes the hook's internal
business-logic error path; `fail_closed` describes the infrastructure
crash/timeout path. A hook can legitimately be `fail_mode: open` and still
call `hook_main(main, fail_closed=True)` — see `input_guard.py`. Every
PREVENT-class hook (`escalation: block`) must call `hook_main()` with an
**explicit** `fail_closed=` keyword — `scripts/gen_hook_matrix.py`'s
`check_prevent_hooks_explicit_fail_closed()` enforces this.

### PreToolUse vs PostToolUse blocking — do not mix

Full protocol lives in `hooks/lib/runtime.py`'s module docstring; the short
version:
- **PreToolUse** blocks via `emit_permission_decision()` — `sys.exit(1)` does
  nothing here.
- **PostToolUse** blocks via `sys.exit(1)` — it cannot use
  `emit_permission_decision()`.

### `hooks/utils.py` is a facade, not the source

Shared hook code lives in `hooks/lib/{runtime,state,discovery,security}.py`,
split by responsibility. `utils.py` re-exports everything for backward
compatibility (most existing hooks still `from utils import X`); **new code
should import directly from `hooks/lib/`**. See `hooks/CLAUDE.md` for the
full hook-authoring checklist (recursion guards, exit codes, anti-patterns).

### Two deployment surfaces, easy to desync

`hooks/settings.json` / `hooks/hooks.json` are two independent manifests for
the same hook set (install-script template vs plugin-distribution format) —
they must be kept in sync manually; `scripts/sync_plugin_hooks.py --check`
verifies it. Separately, the **live, installed** copy at a user's
`~/.claude/` can drift from what's in this repo (a hook fixed here isn't
live until reinstalled/redeployed) — several bugs this project has hit were
exactly this: the repo was correct, the live machine wasn't.

### Personal-only consumers are not dead code

Some `hooks/registry.yaml` entries marked `class: library`
(`expert_registry.py`, `doc_bridge.py`, `doc_registry.py`) have zero callers
*inside this repo* by design — their real consumers are personal skills
(`expert-compiler`, `data-bridge`) that exist only on the maintainer's
machine, never contributed here. A `grep`-based "no callers found" finding
against this repo alone is not sufficient evidence of dead code for these
specific files — check outside the repo boundary first.

### Memory files

`.claude/memory/activeContext.md`'s `CURRENT STATE` table must stay short
and current — narrative/historical content belongs in
`.claude/memory/history/`, not accumulated inline (a prior version grew a
single cell to 52K characters, breaking the `Read` tool). Don't let this
regress.

### Import from other AI-agent configs

This repo also has `.codex/` (OpenAI Codex CLI config) present locally, and
the user has `~/.codex/config.toml`. If asked to import settings from Codex
or Gemini CLI configs, use Claude Code's own `/import` flow (`/import` to
scan, `/import --yes=<digest>` to apply) rather than reading/copying those
files by hand — it applies the same safe-name/path-traversal guards as the
interactive picker.

## Workflow conventions (from this repo's own history, not generic advice)

- **One fix per PR.** Even a one-line doc-drift fix gets its own branch/PR —
  makes `git bisect` and rollback trivial, and keeps CI failures attributable.
- **Reviewer + tests are mandatory** (this repo is "production"-classified) —
  but if the automated reviewer's Evaluator-Optimizer Guard cap is closed
  (3 non-LGTM verdicts without a reset), that's a real block, not
  bypassable silently; escalate to the user rather than skip review.
- Every PR needs: `pytest tests/ -q` clean, `ruff check .` clean,
  `mypy --ignore-missing-imports hooks/ scripts/` clean, and both
  `check_architecture.py --check` / `gen_hook_matrix.py --check` green.
- No `git push --force`/`git reset --hard`, no commit without an explicit
  request, no direct commits to `main` (a pre-commit hook blocks it — work
  on a feature branch).

<!-- gitnexus:start -->
## GitNexus — Code Intelligence *(optional MCP)*

> **GitNexus not installed?** Skip this section — use `Grep(pattern, path)` and `Read` instead.
> Install: `npm install -g gitnexus && npx gitnexus analyze` → restart Claude Code.

### Always Do *(if GitNexus available)*

- **MUST run impact analysis before editing any symbol:**
  `gitnexus_impact({target: "symbolName", direction: "upstream"})`
  *Fallback:* `Grep("function_name", "hooks/")` — find callers manually.
- **MUST run `gitnexus_detect_changes()` before committing.**
  *Fallback:* `git diff --stat HEAD`
- **MUST warn user** if impact returns HIGH or CRITICAL risk.

### Never Do

- NEVER edit a function without running `gitnexus_impact` first.
- NEVER ignore HIGH/CRITICAL risk warnings.
- NEVER rename with find-and-replace — use `gitnexus_rename` (graph-aware).
- NEVER commit without `gitnexus_detect_changes()`.

### Skills Reference

| Task | Skill file |
|------|-----------|
| Architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Debug / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools & schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |

> After `git commit`: run `npx gitnexus analyze` to refresh index (hook does this automatically).
<!-- gitnexus:end -->
