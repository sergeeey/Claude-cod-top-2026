---
name: release-scout
description: >
  Semi-autonomous self-development scout. Watches for new Claude Code releases,
  upstream repo changes, and relevant papers/tools, runs each candidate through the
  FL pre-gates (source trace + novelty), and drops a structured inbox entry for human
  review. Read-only, Green-tier: it PROPOSES, it never applies. Triggers:
  /release-scout, "scout releases", "what's new to adopt", "self-dev scan".
  NOT for: applying a change (that is a human "go" + a normal experiment).
---

# /release-scout — Self-Development Scout (propose-only)

> Find what the outside world shipped that this repo could adopt, vet it cheaply, and
> leave a reviewable proposal. Adopting anything is a separate, human-approved step.

## Autonomy contract (hard)

- **Risk tier: Green** (`.claude/rules/autonomy-budget.md`). Read-only. Writes exactly
  one artifact per run: inbox entries under `~/.claude/memory/inbox/`. Zero project-code
  edits, zero git, zero installs, zero sends.
- **It never applies a candidate.** Output is a proposal. Application = the user says
  "go" on a specific inbox entry → a normal `experiments/<id>/` FL run → promote/reject.
- If a step needs a network tool that is unavailable (`gh`, WebSearch), it says so and
  degrades — it does not fabricate results.

## Sources (scan in this order, stop early if budget is tight)

| # | Source | How |
|---|--------|-----|
| A | Claude Code releases | Diff the current changelog/release notes against `claude-md/RELEASES.md`. New wired-feature candidates = anything in the notes not already inventoried there. |
| B | Watched repos | For each entry in `docs/research-sources.yaml` with `watch: true`, check for a newer release/commit than its `reviewed_version`. |
| C | Papers / tools / trends | Reuse existing skills — `github-scout` (OSINT repo search) and `last30days` (multi-platform trend scan) — scoped to this repo's actual bottlenecks from `activeContext.md`. |

## Per-candidate gates (FL pre-gates -4 and -3 — cheap, minutes)

For every candidate before it becomes an inbox entry:

1. **Step -4 Source Trace.** Does a real primary source exist (release URL, commit SHA,
   DOI/arXiv, repo)? Verify it, do not trust a summary. No verifiable source → **drop**
   (mark `KILL: no source`).
2. **Step -3 Novelty.** `grep -i "<keyword>"` across `null_results/INDEX.md`,
   `parked/INDEX.md`, `pearl_registry/INDEX.md`. Already rejected → **drop** (cite the
   null_result). Already parked → note the prior decision. Already present in the repo →
   **drop** (`KILL: already have it`).

A candidate that survives both gates gets an inbox entry. One that does not is logged in
the run summary as dropped-with-reason (silent drops hide coverage — never do that).

## Inbox entry format (one file per surviving candidate)

Write to `~/.claude/memory/inbox/release-scout-<YYYYMMDD>-<slug>.md`:

```markdown
# candidate: <short name>

- **source:** <primary URL / SHA / DOI — verified, not summarized>
- **what it gives:** <one line — the capability, not the hype>
- **core-loop stage it improves:** <Goal | Plan | Capability-Selection | Execute | Verify | Remember>
  (a candidate that improves NO stage is noise — drop it instead of filing it)
- **FL pre-gate verdict:** source=<ok> novelty=<new|parked|dup>
- **proposed experiment:** <the smallest falsifiable test that would decide adopt/reject>
- **cost estimate:** <rough — is this a doc, a hook, or an architecture change?>
- **status:** PROPOSED (awaiting human "go")
```

## Run summary (always print, even if nothing survives)

```
[release-scout <date>] scanned: A=<n> B=<n> C=<n>
  surviving -> inbox: <count> (<slugs>)
  dropped:   <count> (<reason per candidate — no source / already rejected / already have / improves no stage>)
```

Reporting the drops is the point: "scanned 20, 0 survived" with reasons is a *useful*
run; "found nothing" with no accounting looks like coverage when it may be a broken scan.

## Relationship to the rest of the system

- Feeds `scripts/inbox_review.py` (which already batch-processes `~/.claude/memory/inbox/`).
- Records adopted/rejected external ideas in `docs/research-sources.yaml` so an idea
  cannot silently become an internal "fact" without a provenance row.
- Scheduling this weekly is a **standing-config** decision (a cron/scheduled task) — set
  up by the user, not by this command. The command is the payload; the schedule is opt-in.

## Gotchas

- Do not let source B/C balloon token budget — cap each source, log what was capped.
- A newer version existing ≠ worth adopting. The inbox entry proposes a TEST, not an upgrade.
- Never write outside `~/.claude/memory/inbox/`. That single-writer rule is what keeps
  this Green-tier.
