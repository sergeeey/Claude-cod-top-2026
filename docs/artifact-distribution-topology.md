# Artifact Distribution Topology — analysis, plus one live finding

**Status: RESEARCH.** No mechanism is built here. The question is deliberately
narrow, and it is *not* "how do we build a unified inventory":

> Can the existing installer / drift / plugin / counter surfaces be derived from
> a source of truth that **already exists**, without creating a second registry
> layer?

That framing matters. This repo already holds `hooks/registry.yaml`,
`skills/registry.yaml`, agent frontmatter, `plugin.json`, `hooks.json`, and the
copy list inside `install.sh`. Adding `artifact-registry.yaml` on top would make
six sources of truth and call it one.

## Measured topology (2026-09-11, read from `origin/main`)

| artifact | install.sh | live_drift_guard | sync_doc_counts | plugin export | registry |
|---|---|---|---|---|---|
| hooks `*.py` | ✅ L410 | ✅ content + wiring | ✅ L81, minus `_HOOK_EXCLUDED` | ✅ `hooks.json` | `hooks/registry.yaml` |
| rules `*.md` | ✅ L390 **+ L402 nested** | ✅ content + missing-from-repo | ✅ L91 `rglob` | ❌ | — |
| skills | ✅ global sync | ❌ **blind** | ✅ L83 `**` | ✅ core + extensions | `skills/registry.yaml` |
| agents | ✅ L807 | ❌ blind | ✅ L82, minus `CLAUDE.md` | ❌ | frontmatter `name:` |
| commands | ⚠️ **L477, wrong source — see finding** | ❌ blind | ❌ uncounted | ❌ | — |
| `CLAUDE.md` | ✅ L381 | ❌ | — | — | — |
| `settings.json` | ✅ L414 | ✅ since #417 | — | — | — |

Every surface hardcodes its own path list; none derives from another. That is
why each gap had to be found separately — #407 taught the guard about `rules/`,
#417 fixed its settings path, #420 shipped a skill the guard structurally could
not see, and `install.sh:402` is a hand-written second call because
`safe_copy_dir` globs flat.

## LIVE FINDING — two divergent `commands/` trees, installer reads the wrong one

This started as a prediction ("`commands/` is the next miss waiting to happen").
Checking it turned it into a finding.

There are **two** command directories in the repo, with **different content**:

```
commands/            evolve-solution.md  release-scout.md  revive-project.md
.claude/commands/    evolve-solution.md                    revive-project.md
```

```
install.sh:473   local src="$SCRIPT_DIR/.claude/commands"
```

Consequences, each verified rather than inferred:

1. **`release-scout.md` is never installed.** It exists only in `commands/`,
   which no install path reads. A clean install does not get it. (It is present
   at `~/.claude/commands/` on the maintainer's machine — placed by hand or by
   an older install path — which is exactly why the gap stayed invisible.)
2. **The two shared files are not copies.** Both differ by content hash:
   `evolve-solution` `4deac9df…` vs `2756f6b6…`; `revive-project` `e6c041da…`
   vs `d0f5eb44…`. The installer ships the `.claude/commands/` variant, and
   nothing states which is canonical.
3. **Nothing would have caught either.** `commands/` is uncounted by
   `sync_doc_counts` and invisible to `live_drift_guard`. The guard's only
   occurrence of the word "commands" is a comment about *shell* commands
   (`live_drift_guard.py:149`) — checked, because a bare `grep -c` made it look
   covered.

This is the **sixth** artifact of the distribution-drift class this week, and
the first running in the opposite direction: *in the repo, missing from the
distribution*, rather than *in the install, missing from the repo*.

Not fixed here. It is a separate change, and this document is the analysis step.

## The candidate that does not add a sixth registry

`install.sh` is already the only place that knows the complete mapping — it must
be, or nothing installs. Its problem is that the mapping is **imperative**: a
sequence of `safe_copy_dir` calls no other tool can read.

So the shape worth investigating is inversion, not addition:

```
  install.sh's copy list ──(extract)──> one declarative table
                                              │
                         ┌────────────────────┼────────────────────┐
                    install.sh          live_drift_guard      sync_doc_counts
                   (consumes it)         (consumes it)        (consumes it)
```

Nothing new is declared. The list that already exists stops being
executable-only and becomes readable. Drift coverage then follows from the table
instead of from someone remembering to add another branch — and a second tree
like `commands/` vs `.claude/commands/` becomes a contradiction in one file
rather than a discrepancy nobody is looking for.

## Why this is not being built today

1. **The extraction is the risky part, not the design.** `install.sh` has
   conditional destinations: `--target` redirects, `--sync-global-skills` is
   on/off by context, `--link` symlinks instead of copying. A table that cannot
   express those would silently narrow the installer — a worse failure than the
   one it fixes.
2. **A cheaper falsifiable test comes first.** Extend `live_drift_guard` to
   `skills/`, `agents/` and `commands/` using its existing rules-tree logic. If
   that closes the observed gap class, the table is unnecessary. If a *new*
   artifact kind drifts anyway, the table earns its place on evidence.
3. **This repo's own rule says so.** `pearl_registry/INDEX.md`, on the
   typed-claim-graph entry: *"do not build a typed graph on a modeled failure
   mode alone"*. The same discipline applies to a typed artifact graph.

## Recorded prediction

```
Change:        none — this is the analysis step
Prediction:    extending live_drift_guard to skills/ + agents/ + commands/
               closes the observed drift class without a new registry
Falsified if:  a drift incident occurs in an artifact kind the EXTENDED guard
               already covers — which would mean per-kind coverage is the wrong
               abstraction and the declarative table is needed sooner
Check after:   the next 5 distribution-related findings, or 2026-10-11
```

---

**Source:** external product audit, 2026-09-11, which proposed a unified
inventory. Narrowed here to *derive, do not add*, per the maintainer's framing:
a registry built to synchronise registries is the failure mode, not the fix.
