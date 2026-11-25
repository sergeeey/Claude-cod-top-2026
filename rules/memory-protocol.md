# Memory Protocol

## Project memory (in each project)
```
<project>/.claude/memory/activeContext.md  — what we are doing now
<project>/.claude/memory/decisions.md      — architectural decisions
<project>/.claude/checkpoints/             — save points
```

## Global memory (~/.claude/memory/)
```
user_profile.md  — WHO the user is
patterns.md      — WHAT works ([REPEAT]/[AVOID]/[×N] register)
learning_log.md  — WHAT was learned (concepts + tip-tracker)
goals.md         — WHERE we are heading
decisions.md     — WHY decisions were made
```

### Canonical paths

Each global file lives at the canonical location (`~/.claude/memory/` root). Legacy copies under
`_auto/` are read-only fallbacks; a legacy file whose whole body is a MOVED banner is not content.

Before the first write to `patterns.md` or `decisions.md` in a session, check both paths:
- only canonical exists -> write canonical;
- only legacy exists with real content -> write legacy (do not create an empty canonical);
- both exist with real content -> STOP and reconcile first. Do not guess;
- neither exists -> create canonical.

Reading: check canonical first, then the legacy `_auto/` copy; either path may be read.

Check with `ls`, not with any path table.

Optional history (not needed to apply this rule): the path history and the 2026-07-06 incident are
kept in the owner's private incident notes (`~/.claude/memory/incidents/`). If that file is absent,
the rules above still apply in full.

## Routing table — type of experience → single canonical sink

**Problem this solves:** capture tooling is mature (11 hooks + 5 skills), but nothing
previously said which ONE file a given type of experience belongs to. Result: the same
kind of lesson could land in `patterns.md`, `learning_log.md`, or `cross_domain_insights.md`
depending on which hook fired first — recall then means grepping 3-4 files instead of one.
Verified 2026-07-06 by reading hook source directly (not names alone).

| Type of experience | Canonical sink (ONE) | Owning hook/skill [VERIFIED] | Trigger |
|---|---|---|---|
| Recurring mistake / anti-pattern | `patterns.md` `[AVOID]` | `pattern_extractor.py`, `pattern_escalation_review.py` | commit `fix:` / pattern recurs |
| Validated approach worth repeating | `patterns.md` `[REPEAT]` | `pattern_extractor.py` | commit, or `/error-to-lesson` |
| Architectural / design decision | `decisions.md` | `post_commit_memory.py` | any commit |
| Raw session observation (unsorted) | `_auto/raw/session-{date}.md` | `observation_capture.py` | session end |
| Cross-domain structural bridge | `cross_domain_insights.md` | `/cross-domain` skill | manual invocation |
| Side-asset / harvestable value | `pearl_registry/INDEX.md` | `/harvest` skill | manual invocation |
| Experiment REJECT / ARCHIVE verdict | `null_results/INDEX.md` (REJECT) or `parked/INDEX.md` (ARCHIVE) | `experiment_insight.py` | experiment `decision.md` written |
| Unsorted raw note → structured entry | `_auto/wiki/` (from `raw/`) | `inbox_review.py`, `raw-to-wiki` skill | manual or session end |

**Read-only auto-outputs — NEVER hand-write, not valid capture targets:**
- `learning_log.md` — pure commit↔tip-id correlation table (`learning_tracker.py`), tabular stats only
- `playbook.md` — pure approach helpful/harmful counters (`ace_reflector.py`), file itself says "do not hand-edit"

Corrected 2026-07-06: an earlier version of this table listed both as manual "concept learned"
targets (including a since-removed "Reusable execution step (ACE) → playbook.md" row, which
directly contradicted this correction by still listing playbook.md as a writable sink) —
verified wrong by reading the actual file contents, not just hook names. Any future capture
tooling must exclude these two from its writable-sink list.

**Hard rule:** when a new experience doesn't cleanly match one row, do NOT split it across
multiple files "to be safe" — pick the single best-fit row above. If genuinely none fit,
default to `raw/` (unsorted inbox) rather than inventing a new top-level sink file.

**Gap partially closed 2026-07-06:** all auto-triggered rows above still fire only on a git
commit or an explicit per-sink skill invocation (`/harvest`, `/cross-domain`, etc). A "soft"
lesson noticed mid-session (no commit, no per-sink skill called) previously had no manual
entry point either — the assistant had to pick a row and write to it by hand each time, with
no dedup/gate discipline enforced. `/capture` (a personal skill; not shipped by this repository) now
provides that manual entry point: Zero-Signal Gate → classify against this exact routing
table → dedup-check the target file → write in its real format. Still requires an **explicit**
call (`/capture` or equivalent) — no dispatcher automatically detects and routes free-form
experience without being asked; that part of the gap remains open.

## After each git commit
1. Update activeContext.md
2. Complex bug → patterns.md (auto-prompted by pattern_extractor.py for fix: commits)
3. Architectural decision → decisions.md

## Checkpoint Fidelity

A checkpoint must let a new agent or external reviewer reconstruct current claim
statuses WITHOUT reading the full session transcript. Criterion: **state can be
reconstructed without the full transcript.**

| Keep as active state | Do NOT carry forward as active truth |
|---|---|
| FACTS, ACTIVE CLAIMS, ASSUMPTIONS, UNKNOWNS | repetitions and stale plans |
| DECISIONS, CERTIFICATES, BROKEN DEPENDENCIES | narrative summaries without provenance |
| SUPERSEDED ITEMS and the reason for the version change | old hypotheses without status |
| OPEN QUESTIONS and remaining uncertainty | internal chain-of-thought reasoning |

**Why this matters here, concretely:** a "~600/701 orphaned git.exe processes"
claim propagated unverified across 9+ sessions in this exact project's
activeContext.md — a right-column failure (narrative without provenance carried
forward as if it were left-column fact). `hooks/activeContext_hygiene.py`
soft-nudges on this specific shape (approximate numeric claims / hedge verbs
without an evidence marker) — see its module docstring for the DDD skeptic
verdict (BUILD_LIGHT) that scoped it.

## Pattern tags in patterns.md
- `[REPEAT]` — proven approach, use again in similar situations
- `[AVOID]` — mistake or anti-pattern, do not repeat
- `[×N]` — occurrence counter. [×3] = seen 3 times, treat as hard rule
- When a known pattern recurs: increment counter [×N] → [×N+1], add "- Recurrence [date]: ..."

**Cross-project transfer step (added 2026-08-16):** lessons captured in `patterns.md`
stay scoped to the project that wrote them — nothing propagates them to a sibling
repo automatically. Confirmed real cost, not hypothetical: the same spatial-CV
methodology error was independently rediscovered under three different names across
three different repos (an ADR, a cross-province AUC collapse, a numbered rule),
months apart, because nothing asked "does this apply elsewhere?" at write time.

When writing a new `[AVOID]` entry, before moving on: ask *"which other repos of
mine could this apply to?"* and run `graphify-query.py find-all <keyword(s) from
the pattern>` (or `cross-repo <component>` if the pattern centers on a specific
named component) against the meta-graph. If it surfaces a plausible match in
another project, leave a one-line pointer in that pattern's entry (or the other
project's own `patterns.md`) rather than letting the graph query be the only
record.

**Known limit of this step, stated so it isn't mistaken for a closed loop:**
`find-all`/`cross-repo` match on node names/keywords in the graph — they catch a
lesson recurring under a *similar* name, not one rediscovered under a genuinely
different name or framing (which is exactly how the spatial-CV lesson slipped
through 3 times: each rediscovery used its own vocabulary). A clean `find-all`
result is weak evidence of "not applicable elsewhere," not proof — treat it
accordingly, don't over-trust a no-match.

## Hot-Path Capture — mid-conversation, not deferred to /capture or session-end

**Convention:** when either the user or the model notices, mid-conversation,
that something is clearly worth persisting — a corrected assumption, a
validated non-obvious choice, a decision with a real WHY, a fact that will
matter next session — do not wait for a git commit, a skill invocation, or
session end. Say so explicitly (e.g. "saving this now: ...") and write it
immediately, through the same § Routing table above: same target-file choice,
same dedup check (§ Rule for WRITING), same evidence markers (`integrity.md`).

**What this does NOT change:** § Routing table's own gap note still stands.
This is an explicit act — the model or user choosing, in the moment, to say
"this is worth saving" — not an automatic background dispatcher that scans
every message for capture-worthy content. It only removes the requirement
that the trigger be a slash command or a commit; noticing is enough to act on.

## Feedback memory
When the user corrects your approach ("no, don't do that", "instead do X"):
1. Save immediately to auto memory as type `feedback`
2. Include WHY the user gave this feedback
3. Include WHEN to apply it (context/trigger)
4. Check existing feedback memories first — update instead of duplicating

## Context Overflow (70% threshold)
1. Update activeContext.md
2. /clear
3. Load context → continue

## Checkpoints — before risky operations
- git rebase/merge into main, large-scale refactoring
- DB migration, architecture change, release
- checkpoint_guard.py will remind you automatically

## Parallel Workstreams (in activeContext.md)

**Why this exists:** `activeContext.md` is one running log — fine for a single
thread of work, but it silently loses "which of the 3 things I'm juggling is
this note about?" once more than one is active at once. Extracted 2026-08-04
from evaluating (and then deleting) the GSD framework's `gsd-workstreams`
concept — the underlying need (track parallel efforts explicitly) was real,
the 65-skill scaffolding built around it was not; almost everything else GSD
did already existed here under a different name (codex-skeptic ≈ its cross-AI
plan review, Evaluator-Optimizer Guard ≈ its audit-fix loop, this file's own
Checkpoint Fidelity table ≈ its milestone-summary). This is the one piece
worth keeping, added as a convention instead of imported machinery.

**Convention:** when ≥2 genuinely independent efforts are active in the same
project at once, tag each `CURRENT STATE`/`Current Focus` entry with a short
`[WS: <slug>]` marker (e.g. `[WS: skills-cleanup]`, `[WS: pr-251]`). One
active effort → no tag needed, don't add ceremony for a single thread.

**Closing a workstream:** append `[WS: <slug>] CLOSED — <one-line why>` so a
later read of the log doesn't have to infer whether it's still open.

## Unclaimed Work Ownership (multiple sessions/tabs, same repo)

**Why this exists:** two Claude Code sessions (tabs, terminals, or machines) can
point at the same repo at once. An unfamiliar, uncommitted file or directory
found mid-session isn't automatically stale clutter — it may be another
session's in-progress work. Already practiced ad hoc (Claude-cod-top-2026,
2026-07-24: mid-merge, fetched and found real concurrent work had landed from
another machine, hand-reconciled instead of overwriting) — naming it here
makes it a rule instead of something to remember to be careful about each time.

**Convention:** an unfamiliar, uncommitted file/directory is not fair game
until its origin and completion status are known. A commit, a `decision.md` /
equivalent completion artifact, or simply asking, are valid completion
signals — absence of all of them means treat it as someone else's active
work: read-only, don't edit, don't stage, don't delete.

**Stage what you touched, not everything:** `git add <specific files>`, not
`git add .` / `git add -A`, whenever another session's work might be
interleaved in the same working tree — already default git-safety practice in
this stack; named here to tie it explicitly to the ownership rule above.

## Preview-Before-Write Gate (any hook/skill that writes to CLAUDE.md/memory/skills)

**Why this exists:** "I'll show you a preview before writing" is currently an
honor-system promise the model makes to itself each time, not a mechanical
guarantee. Extracted 2026-08-30 from auditing `Distill-Yourself`
(github.com/QuantaAlpha/Distill-Yourself, evaluated for its session-history
distillation pipeline) — its `evolve-sync` command hard-codes this as the
default: writes to `~/.claude/CLAUDE.md`/memory require an explicit
`--execute` flag; omitting it always returns a preview, never a write. The
same discipline is worth adopting as a convention here, since nothing today
stops a hook or skill from writing to CLAUDE.md/memory/skills in one shot with
no dry-run path.

**Convention:** any hook or skill capable of writing to `CLAUDE.md`, `~/.claude/memory/`,
or `~/.claude/skills/` should default to preview/no-write, and require an
explicit opt-in (a flag, a second confirmed call, an explicit user "yes") to
actually persist. Do not rely on "I'll ask before writing" as prose alone when
the action is scriptable — make the default the safe one.

## Explicit Truncation Marker (any hook/skill reading or summarizing large content)

**Why this exists:** `falsification-ladder.md`'s "no silent caps" rule already
states the principle ("if a workflow bounds coverage, log what was dropped")
but nothing in this stack enforces it mechanically — a hook can clip output
and the caller has no structured way to tell "this is everything" from "this
was cut off" apart from re-reading prose. Same `Distill-Yourself` audit
(2026-08-30) showed the concrete shape: its `read-window`/`tool-search`
commands return an explicit `truncated: bool` field alongside clipped text,
computed by a `truncate_utf8()` helper that clips at a byte budget without
splitting a UTF-8 codepoint — not a comment, a field the caller can branch on.

**Convention:** when a hook or skill bounds/clips its own output (byte limit,
line limit, top-N), include an explicit boolean/count field in the returned
structure (not just prose) saying whether truncation happened — so a caller
(model or script) can detect "some coverage was silently dropped" without
re-parsing free text.
