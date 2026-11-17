# Federated memory: several stores, one picture

Read this when the project keeps memory in more than one place (repository, raw session notes
or transcripts, a vault, a graph or search index, an agent memory file, a backup). The ten axes
and the Stage 1 inventory still apply. This adds three checks they do not make explicit. It
names functions and boundaries, not technologies: nothing here requires a vault, a graph or a
catalog format.

## 1. Discovery for every store, not only the catalog

For each store found in Stage 1, answer four questions in order and stop at the first "no":

| Question | If no |
|---|---|
| Does it exist and is it in a known place? | `UNKNOWN` source |
| Is it current (compare its newest entry with the newest thing it should contain)? | stale: report, do not trust |
| Does an entry document (CLAUDE.md, AGENTS.md, a workflow) say it exists and when to use it? | `DISCOVER` fail |
| Does an agent given only the question reach it? | `RETRIEVE` fail |

A store can be perfect and invisible. An index that lists only some of the notes in its own
folder is a freshness defect of that index, not of the notes.

## 2. Promotion: raw material to a durable record

Working or raw material (session notes, transcripts, scratch files) is allowed to stay raw. The
defect is a finding that exists only there while a durable record says the opposite or nothing.

For each raw store, sample the newest items and ask:

1. Does it contain a result, a reversal or a decision (not setup and chatter)?
2. Is that result present in the governing record (the file that owns the verdict)?
3. If not: `PROMOTION_GAP`. The governing record is stale, and anything that reads only it
   (an index, a catalog, a memory file) inherits the stale answer.

Remedy: promote the one finding into its governing record, with a pointer back to the raw file
as evidence. Do not copy raw text wholesale, and do not require every raw note to be promoted.
Private raw material (correspondence) is never promoted verbatim: keep it local, and record at
most a safe derived summary, with the owner's approval.

## 3. Optional layers stay optional until measured

A graph, an embedding index or a generated catalog is derived retrieval. It may not override
primary evidence (see "derived fields are cache" in `research-memory-profile.md`). Check two
things:

- Is the layer wired in as a mandatory first step (for example "always query X first") while
  it is stale or unmeasured? Then a stale layer silently sends agents to wrong answers:
  report it, and downgrade the instruction to "optional, verify against the governing file".
- Does it measurably improve a real lookup (given the same questions, with and without it)?
  No measurement means `KEEP OPTIONAL`: do not extend it, and do not remove it.

## Report fields

Add to the source map, per store: `authority_for`, `not_authority_for`, `privacy_domain`,
`durability` (single machine or replicated), and the discovery result above. Keep it one table.
