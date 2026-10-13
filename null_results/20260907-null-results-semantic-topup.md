# 20260907-null-results-semantic-topup — REJECT

## Claim

Adding a semantic top-up to `hooks/null_results_pre_check.py` (currently pure
lexical: ≥2 shared tokens between prompt and a null_results slug) would close
its confirmed paraphrase-recall gap — a real duplicate proposal phrased with
different words than the original slug would go undetected. Proposed as a
narrow, verified fix in response to an external critique of this repo's
scientific-memory architecture (the critique's own P0-heavy 50-point table was
mostly rejected on Gate 1 grounds — see `pearl_registry/INDEX.md` — but this
one point was independently confirmed real by reading `null_results_pre_check.py`
source directly, and reusing `vector_store.py`'s existing hybrid pattern, the
same way `knowledge_librarian.py` already does for the wiki corpus, looked like
exactly the kind of small, high-leverage fix this repo's own philosophy favors.)

## Context — why this looked like a good idea

`vector_store.py` already implements a two-tier semantic search (real
sentence-transformer embeddings when available, pure-stdlib TF-IDF cosine as
fallback) and `knowledge_librarian.py` already reuses it for the wiki corpus.
Reusing the SAME technique for `null_results/INDEX.md` (a much smaller corpus:
a handful of rows, each a slug + a ≤10-word "why") seemed like a direct,
low-risk application of an already-proven pattern.

## Test (live, before any hook code was written)

Built two throwaway scripts against real `null_results/INDEX.md` entries and
genuine paraphrase queries with near-zero lexical overlap with their target
entry's slug (e.g. "should we build a rule-based content classifier for
filtering model output" vs. the real entry `regex-composition-response-guard`):

1. **TF-IDF cosine** (`vector_store._tokenize` / `_compute_tf_normalized` /
   `_compute_corpus_idf` / `_apply_idf` / `_cosine`, ad-hoc corpus = the query
   + all null_results entries, fresh IDF computed per call): true-positive
   similarity **0.059 and 0.000** — indistinguishable from the negative
   controls (0.000 both). No usable signal.
2. **Real sentence-transformer embeddings** (`all-MiniLM-L6-v2`, the same
   model `vector_store._get_embedder()` already uses, confirmed installed —
   `sentence-transformers==2.3.1`, `chromadb==1.5.9`): true-positive
   similarity **0.258 and 0.319**, negative controls **≤0.056** — clean,
   well-separated signal. This technique genuinely works.

But: measured cold-start cost of `import sentence_transformers` +
`SentenceTransformer("all-MiniLM-L6-v2")` load, in a fresh process (exactly
how every hook invocation runs): **8143ms import + 3491ms model load = 11.7s
total**, before encoding a single query (encoding itself: 61ms). Checked
`hooks/registry.yaml`: `knowledge_librarian.py` (the hook this pattern was
borrowed from) fires on `SessionStart` — once per session — not on every
prompt. `null_results_pre_check.py` fires on `UserPromptSubmit`, synchronously,
every time a prompt contains a hypothesis/experiment-shaped keyword. Applying
an 11.7-second cold-start cost there is a different, much worse latency
budget than the one the existing pattern was actually designed and accepted
for — not an apples-to-apples reuse, despite calling the same library.

## Verdict: REJECT

Neither tier of the "reuse vector_store.py's hybrid pattern" idea survives
contact with a live measurement:
- cheap tier (TF-IDF) → too weak to detect real paraphrases on this corpus size
- effective tier (embeddings) → correct, but 11.7s per invocation is an
  unacceptable UX regression for a `UserPromptSubmit` hook (existing hooks in
  this repo run in 80-110ms; see this session's own hook-latency benchmark)

## Kill Analysis (Anti-Overfitting Gate)

**What this killed:** "reuse vector_store.py's existing hybrid pattern
as-is for null_results_pre_check.py" — both of its two tiers, at their
current design, for this specific hook's event type.

**What this did NOT kill:**
- The underlying complaint is still real and independently verified:
  `null_results_pre_check.py` genuinely only matches on lexical token overlap
  and will miss a real duplicate phrased in different words.
- Real sentence-transformer embeddings genuinely CAN separate true
  paraphrases from noise on this exact corpus (0.26-0.32 vs ≤0.06) — the
  technique itself is not the problem, only the current unbatched,
  cold-process-per-invocation cost model is.
- `vector_store.py`'s own two-tier design (real embeddings when available,
  honest TF-IDF-only degradation otherwise) remains correct for its actual
  use case (SessionStart, once per session).

**Relaxation Map (untested, not built — do not build without a new trigger):**
- Remove assumption "the embedder must load fresh inside this hook's own
  process": a long-lived embedding service/daemon (or reusing an
  already-warm process another hook keeps alive) would eliminate the 11.7s
  cost, but is real standing infrastructure — disproportionate for one small
  advisory hook, and in tension with this repo's own "инструмент, не
  продукт" scope (`Product Constitution`).
- Remove assumption "the check must run synchronously on UserPromptSubmit":
  an async/background check that surfaces a warning on the NEXT turn instead
  of blocking this one could hide the latency, but changes this hook's
  observable contract (advisory-before-you-act becomes advisory-after) —
  a different design, not a tuning of this one.
- Remove assumption "no dependency budget increase is acceptable": if this
  repo ever adopts a persistent embedding cache/service for another reason,
  `null_results_pre_check.py` could piggyback on it for free — revisit then,
  not before.

## Trigger condition to revisit

A persistent embedding service or always-warm process becomes available in
this repo for an unrelated reason (i.e., someone else pays the standing cost
first) — OR a real duplicate-research incident is observed inside
Claude-cod-top-2026 itself (not borrowed from another project) that this
lexical-only gap actually caused, raising the priority above "known, accepted
recall gap."

## null_retroscan check (Principle 5, immediate retroscan)

`hooks/null_retroscan.py` flagged this REJECT against the active PROMOTE
`20260903-memory-retrieval-repair` (shared tokens: "semantic", "topup").
Checked directly, not dismissed on vocabulary overlap alone: that PROMOTE
(PR-5) fixed `knowledge_librarian.py`'s HOT-tier scoring BLEND (recency vs.
dense-similarity weight) for wiki search at `SessionStart` — a scoring-
accuracy fix, not a claim about embedder load cost, and a different hook
firing on a different event than `null_results_pre_check.py`. No shared
dependency; the two entries share a word ("semantic top-up"), not a subject.
No undercut.

## Evidence

Live-tested with two throwaway scripts, real `null_results/INDEX.md` entries,
genuine near-zero-lexical-overlap paraphrase queries, and a real negative
control (`"fix the button color on the login page"`, `"rename this variable
to something clearer"` — both scored ≤0.056 on embeddings, 0.000 on TF-IDF).
No hook code was changed; this is a pre-implementation kill, not a revert.
