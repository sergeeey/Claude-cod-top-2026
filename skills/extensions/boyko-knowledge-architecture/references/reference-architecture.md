# Reference architecture: designing project memory from zero

Read this when the user starts a new project (or a project with no memory system) and asks for
its memory structure. It uses the same principles the audit checks, so building and auditing
cannot drift apart. It names functions and folders, not technologies.

**Invariant.** Design the smallest memory architecture that preserves what the project cannot
afford to lose, keeps it discoverable to its people and agents, and adds no layer without a
named operational need. When unsure between two profiles, take the smaller.

## Six principles (the same ones the audit checks)

1. **One owner per kind of fact.** A catalog, graph or index is a cache; the governing file
   (for an experiment, its closing verdict) wins.
2. **Private is separated at the start.** Secrets, correspondence and sealed-evaluation material
   live in an ignored local folder from the first commit, never in git.
3. **Every store is named in the entry document** (`CLAUDE.md` or equivalent), with when to read
   it. A store the agent does not know about does not exist for it.
4. **Raw becomes durable on closure.** Finished work gets a closing record; a result that
   exists only in raw notes is not kept.
5. **Recovery is proportional.** Pushed git needs no second copy; unique local-only state whose
   loss matters gets a minimal backup, or an owner-accepted risk (see below).
6. **Every layer has an activation condition.** Nothing is created "in case".

## Choosing the profile

Do not ask the user to pick. Ask the questions, recommend the smallest sufficient profile, and
state why, what was left out, and what would justify moving up.

Questions (skip any already answered): code, research, or both? alone or with others/agents?
any private material (correspondence, secrets, sealed evaluations)? where does code live and
what may be lost? many experiments expected?

| Profile | Use when | Creates |
|---|---|---|
| `LIGHT` | small or code-only project, one person, few decisions | `CLAUDE.md`, `.gitignore`; optionally one `decisions.md` once a durable decision exists |
| `STANDARD` | agents or several people, private context, repeated work cycles | repo: `CLAUDE.md`, `decisions/`, `docs/`; local ignored folder for private notes and raw material |
| `RESEARCH` | a series of experiments with verdicts is expected | `STANDARD` plus `experiments/<id>/` with `claim.md`, `decision.md`, `evidence/`; a closing-record template |

`RESEARCH` does not include a graph, a vector index, a registry or a catalog. Those are layers.

## Layers and their activation conditions

| Layer | Create only when | Never needed for |
|---|---|---|
| Experiment folders | a second experiment is planned | a code-only project |
| Catalog of experiments | an agent, given only the idea, fails to find an existing experiment (discovery pressure) | fewer than about a dozen experiments, as a rule of thumb, not a measured threshold |
| Graph or vector index | a measured retrieval gain over plain search on real questions | any backup (it is derived) |
| Private backup | unique local-only state whose loss is not accepted | anything already pushed to a remote |
| Registry of skills, services or hooks | the same inventory question is asked and answered wrongly twice | a single-person LIGHT project |

## Risk disposition (a separate axis, not a memory status)

A known residual risk gets one of: `OPEN`, `MITIGATED`, `ACCEPTED_BY_OWNER`, `UNKNOWN`. When the
owner accepts a risk (for example, private notes with no backup), record it once in the entry
document with the date and the reopen condition (a lost note, a failing disk, the vault becoming
critical). A later audit shows it once as accepted and does not re-raise it unless the condition
fires. The word belongs to the risk, never to an experiment or a memory object.

## What to hand back

1. Recommended profile, with the one-line reason.
2. The folder tree for that profile, and the exact `.gitignore` lines for the private folder.
3. A short block for the entry document naming each store and when to read it.
4. For `RESEARCH`: the closing-record template (verdict, conditions, evidence pointers, date).
5. Left out on purpose, each with its activation condition.
6. Accepted risks, if the owner named any.

Create nothing until the user approves the tree (the same gate as `IMPLEMENT`). Then create only
what the profile lists.
