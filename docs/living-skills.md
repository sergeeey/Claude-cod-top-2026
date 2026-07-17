# Living skills — feedback-driven skill maintenance

Added 2026-07-17. Not an official Anthropic feature — an engineering pattern
(originated as a YouTube creator's "живые скиллы" concept) adapted here with a
review-vs-autonomy tradeoff made deliberately, not copied blindly.

## Problem this solves

Skills accumulate silently over time — a trigger phrase stops matching how
people actually phrase requests, a workflow step turns out to be wrong in
practice, an edge case keeps tripping the same skill up. Nobody notices until
a manual audit (like the `/skill-audit`, `deep-research`/`validate-blind`
cleanup done 2026-07-16/17) finds it, often months later.

## What this is NOT

- Not a native Claude Code feature — `/loop` and `CronCreate` are both
  session-scoped (verified: `CronCreate`'s own tool description states jobs
  "live only in this Claude session... gone when Claude exits", auto-expire
  after 7 days even if the session stays open).
- Not the same as `/self-improve skill <path>` — that's a manual, on-demand
  Critic↔Author loop with no persistent feedback log and no schedule.
- Not the same as `skill-creator`'s eval loop — that IS Anthropic's own
  feedback-collection pattern (viewer UI → `feedback.json` → next iteration),
  but it's human-driven per iteration, not autonomous/scheduled.

## What this repo actually has

| Mechanism | Scope | Autonomy | Rewrites SKILL.md? |
|---|---|---|---|
| `hooks/ace_reflector.py` (SubagentStop) | Generic approach effectiveness, all agent runs | Fully automatic, infers success/failure from output | No — writes to shared `playbook.md` |
| `hooks/pattern_extractor.py` | Generic patterns, triggered on `fix:` commits | Automatic | No — writes to `patterns.md` |
| `/self-improve skill <path>` | Per-skill, on demand | Manual trigger | Yes, interactively |
| `skill-creator`'s eval loop | Per-skill, during development | Human reviews each iteration | Yes, with human in the loop |
| **`skill-self-update` (this)** | **Per-skill, opt-in** | **Scheduled + autonomous, git-committed** | **Yes** |

This fills the one gap: nothing here was both per-skill AND autonomous AND
scheduled. `skill-self-update` (`skills/core/skill-self-update/SKILL.md`) is
the new piece.

## Design decisions (and why)

**Auto-apply, not propose-only.** Considered a `SKILL.md.proposed` +
notify-only design (safer — no unattended write to a file that governs future
agent behavior). User explicitly chose auto-apply instead. Mitigation:
`SKILL.md` is git-tracked, so an auto-applied change is a diffable, revertible
commit — not a silent, untracked corruption. The automation always commits
locally (never pushes) with a message prefixed `auto(skill-feedback):`, so it
is trivially distinguishable from human commits in `git log` and revertable
with a single `git revert` if a bad update ever lands.

**Anti-overfitting floor: N≥2 feedback entries before any edit.** A single
comment is noise, not a pattern — see `skill-self-update/SKILL.md` Step 3
(lightweight analog of the Anti-Overfitting Gate in
`rules/falsification-ladder.md`, scaled down for skill instructions rather
than scientific claims).

**Opt-in per skill, not global.** Adding a "please rate this" interruption to
every skill invocation would be noise for skills nobody complains about.
Only skills with the explicit feedback-collection directive in their own
`SKILL.md` participate.

## How to opt a skill in

Add this to the target skill's `SKILL.md` (adapt wording to the skill's own
voice — see `skills/extensions/research-audit/SKILL.md` for the reference
instance):

```markdown
## Feedback (living-skill opt-in)

После завершения задачи этим скиллом: если у пользователя есть замечание —
что зашло, что нет, что стоит изменить — допиши его одной строкой в
`feedback.log` рядом с этим SKILL.md, в формате:
[YYYY-MM-DD] <фидбек как есть>
Не спрашивай, если пользователь явно спешит / в Speed Mode.
```

Then create an empty `<skill-dir>/feedback.log` (the skill itself won't
auto-create it — opt-in must be an explicit human action, not a first-run
side effect; see `skill-self-update/SKILL.md` Step 1).

## Scheduling (machine-specific, lives outside this repo)

Same pattern as `weekly-intel` (`~/.claude/skills/weekly-intel/SKILL.md`,
`~/.claude/scripts/weekly-intel-report.ps1`, `~/.claude/scripts/register-all-tasks.ps1`):

- `~/.claude/scripts/skill-feedback-update.ps1` — generic runner, takes a
  skill-dir parameter, logs to `~/.claude/logs/`, calls
  `claude -p "/skill-self-update <skill-dir>"`.
- Registered via Windows Task Scheduler, twice a week (Wednesday + Saturday
  early morning — off-hours, same slot pattern as the weekly-intel tasks).

This lives in `~/.claude/scripts/`, not in this repo, because it's
machine-specific automation (Windows Task Scheduler, local absolute paths),
not portable config — same reasoning already applied to `agents/navigator.md`'s
rejected `mcp__basic-memory__` dependency and the removed `lit-search`/
`research-strategist`/`stat-validate` references: this repo should not assume
infrastructure that isn't there when someone else installs it.

## Pilot

`skills/extensions/research-audit` is the first (and currently only) opted-in
skill. Expand to others only after this one has run for a few cycles and
proven the loop actually produces sensible edits, not noise.
