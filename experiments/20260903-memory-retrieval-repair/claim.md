# claim.md — 20260903-memory-retrieval-repair (PR-1: corpus fingerprint + rglob)

> Scope note: this experiment folder covers the memory-retrieval-repair Full
> Ladder as a whole (`docs/memory-retrieval-repair-tz.md`, 7 PRs). This file's
> claim is scoped to **PR-1 only** — the fingerprint gate and the `glob`→`rglob`
> fix. PR-2 through PR-7 each get their own dated sub-claim appended below (or
> a fresh `decision.md` entry) as they land, per the TZ's own PR sequencing.

## Zero-Signal Gate

| Field | Value |
|-------|-------|
| **Entity** | `hooks/vector_store.py::rebuild_index()` and its corpus-scanning helper |
| **Falsifiable predicate** | Files under a PARA sub-directory of `wiki/` (e.g. `wiki/projects/`) are indexed and become searchable; an unchanged corpus produces no re-indexing work on a second call |
| **Measurable outcome** | `pytest tests/test_vector_store.py tests/test_memory_retrieval_chain.py -q` — specific tests named below either pass or fail |

Gate passes: entity, predicate, and outcome are all concrete.

## L0: Question Type

- [x] Descriptive — "does the indexing function, as changed, cover the actual file layout it is run against, and does it skip re-embedding an unchanged corpus?"
- [ ] Predictive
- [ ] Causal

This is a software-correctness claim about a deterministic function, not a
population estimate — no estimand.md / DAG is applicable (see TZ §2 Non-goals).

## Natural Language Statement

> We claim that `rebuild_index()`, after the PR-1 change, indexes every
> Markdown note under `wiki/` recursively (including PARA sub-directories),
> excludes `daily/` notes and index/chunk files exactly as before, and skips
> re-indexing entirely when the corpus fingerprint (SHA-256 over sorted
> `rel_path:size:mtime_ns` tuples, stored in a sidecar file) is unchanged.

## Claim Entropy

| Component | Count |
|---|---|
| Unsupported HIGH claims | 0 |
| Hidden assumptions | 0 — fingerprint sidecar is a separate file, never a key inside `tf_index.json` (this was the concrete crash risk Codex's review on PR #332 caught and this code already avoids) |
| Missing negative controls | 0 — see controls.md |
| Ambiguous definitions | 0 — "PARA sub-directory" = any directory under `wiki/` reachable by `rglob("*.md")` except `daily/` |
| Unresolved blockers | 0 |
| **Total claim_entropy** | **0** |

## What This Result Does NOT Mean

1. Does NOT mean semantic (dense-vector) search finds these notes with any
   particular ranking quality — that is PR-5's scope (HOT-tier scoring fix),
   gated by §5.3 of the TZ.
2. Does NOT mean the TF-IDF weights themselves are statistically correct
   across the whole corpus after an incremental add — that is PR-4's scope
   (real corpus-wide IDF reweighting).
3. Does NOT establish anything about `knowledge_librarian.py`'s HOT/WARM/COLD
   tiering — PR-1 touches only `vector_store.py` and `raw_to_wiki.py`'s call
   site.
