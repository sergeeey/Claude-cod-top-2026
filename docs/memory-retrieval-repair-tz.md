# Memory: retrieval repair + gated hybrid extension — technical specification

**Date:** 2026-09-03 · **Status:** DRAFT for owner review · **Supersedes nothing** — extends
`docs/memory-architecture.md` (2026-07-16, updated 2026-08-28), which stays the design doc.

**Origin:** two external (GPT-authored) analyses of this repo's memory layer were reviewed
against the actual code. Every factual claim in both was independently verified with tools
(`grep`/`Read`/`git`) before this spec was written — 11 of 11 code-level claims held; one was
*understated* (see §0.4). Their *plans* were not adopted as-is: both propose more machinery than
this repo's own rules allow at this stage (see §2 Non-goals and §6 Ordering rationale).

A **second** external review then checked the first draft of this spec itself and correctly
caught a real drafting error: §4.1 and the §2 Non-goals row for "coordinator package" both
claimed a `CLAUDE.md § KNOWLEDGE STORES` routing table already existed *in this repo* — it does
not (`[VERIFIED]`, see §4.1). That review's *second* technical claim (real IDF can't be added
without an incremental-update inconsistency) held up only partially at first check: no
incremental caller exists *today* (`[VERIFIED]` via call-graph `grep`), so the specific mechanism
the review named wasn't live. The fix applied at the time (require an `idf` parameter as a
guard) turned out to be an incomplete answer to the review's underlying instinct — see the
fourth review below, which found the deeper problem that fix didn't actually solve.

A **fourth** review (GitHub's Codex bot, on the PR carrying this spec itself, #332) then found
that the round-2 concern was more right than round 2's own first check gave it credit for. A
required `idf` parameter cannot make incremental TF-IDF writes safe: real corpus-wide IDF is a
property of the *whole* corpus, so any single document added, removed, or edited invalidates
every OTHER document's already-stored weight, not just the new one's — a required parameter
guards against the wrong failure mode. PR-4 below (renumbered from the original PR-5 slot; see
next paragraph) now makes IDF a full-corpus-only reweight step inside `rebuild_index()`,
`index_wiki_entry()` never takes an `idf` argument at all. Round 4 also caught: PR-1's fingerprint
would have crashed the existing TF-index reader if stored inline (fixed: moved to a sidecar,
see PR-1); PR-4 (real IDF) needed to move ahead of what is now PR-5 (semantic wiring), since
§5.3's gate must measure the final ranking algorithm, not a TF-only placeholder about to change
underneath it; "Recall@3" as originally defined didn't match the multi-label benchmark design
(fixed: renamed to Hit Rate@3 with the distinction stated explicitly, §5.3); Gate 5.2's 100%
claim didn't account for retrieval-time failures distinct from rebuild-time ones (fixed: scope
narrowed explicitly, §5.2); and the whole phase was misclassified as Standard-Ladder when
`rules/falsification-ladder.md:81-86` puts schema/architecture changes in Full (fixed above).
All outcomes from all four reviews are folded into the sections below rather than kept as a
separate errata list.

A **third** external review then checked this spec's implementation plan against the code more
deeply. Five of its eight technical findings held and are folded into §3/§4/§5 below (with
`[VERIFIED]` citations at each): the `rel_path`-vs-`ids=[title]` contradiction, the
unconditional-per-Stop-rebuild performance risk, the HOT-tier scoring gap for dense hits, the
incomplete IDF design (query-time weighting, versioned schema), and the mandatory-reviewer rule
being misquoted. Two of its claims did **not** hold and were **not** applied:
1. It said `decisions.md` calls commit `34adca6` "fabricated." `[VERIFIED]`:
   `git cat-file -t 34adca6` returns a real commit — this repo's own `activeContext.md` lists it
   plainly as a normal auto-logged entry, never disputed. The review appears to have confused it
   with a *different* hash (`3d05924`) that a GitHub Codex bot cited in an actually-hallucinated
   PR finding earlier the same night (confirmed nonexistent via `git cat-file`) — a real
   incident, just not the one attached to this hash. No memory-file correction was made on this
   basis.
2. It said `activeContext.md` claims "all four audit numbers matched exactly" despite
   `81 != 74`. `[VERIFIED]`: the actual sentence is "every one of the 4 ... turned out exact,"
   immediately followed in the same cell by "74 genuinely-unused noqa directives ... (audit said
   81; my first pass's '33' was a flawed grep)" — the real number and the discrepancy are stated
   openly, not hidden. The summary phrase is a little loose across all 4 items (3 matched
   exactly, the 4th confirmed the same real defect at a corrected count), but it is not the
   "false claim of exact equality" the review described. No `PR-0 memory correction` was opened
   on this basis — the artifact it was meant to fix does not, on inspection, contain the error.
This is recorded here rather than silently accepted or silently dropped, per this repo's own
`audit-verification-gate.md`.

---

## 0. Verified ground truth (what is actually broken today)

All paths relative to repo root. `[VERIFIED]` = confirmed by reading the code on `main` @ `1908530`.

| # | Defect | Evidence | Effect |
|---|---|---|---|
| 0.1 | Vector index ignores PARA sub-directories | `hooks/vector_store.py:363` — `for f in sorted(wiki_dir.glob("*.md"))`, non-recursive, while `hooks/raw_to_wiki.py` routes entries into `wiki/{projects,areas,resources,archives}/` | Every entry routed to a PARA folder is invisible to `semantic_search()`. Only flat legacy files are indexed. |
| 0.2 | Index key ≠ file key (title vs stem) | `raw_to_wiki.py:523,532,543` write `[[{e['title']}]]` (H1 or title-cased stem). `knowledge_librarian.py:275-306` returns those titles. `knowledge_librarian.py:495-520` `_read_wiki_content(stem)` opens `WIKI_DIR/<stem>.md` (+ PARA fallback, same stem). Chroma also keys by title: `vector_store.py:259` `ids=[title]`. No frontmatter join key exists (`raw_to_wiki.py` writes only `processed: true`). | HOT-tier snippet rendering cannot open the file it just matched whenever title ≠ filename — i.e. almost always (dated slugs like `2026-09-02_auc_red_flags.md` vs title `AUC Red Flags`). |
| 0.3 | `semantic_search()` has no production caller | `_query_wiki()` (the only caller, `knowledge_librarian.py:232,266`) is referenced only in docstrings (`:278,:280`). `main()` calls `_query_wiki_raw_titles()` (`:675`), whose docstring says "No semantic-search supplement here" (`:673`). | The whole ChromaDB / TF fallback layer is built, tested (29 unit tests), and disconnected from the SessionStart injection path. Retrieval in production is lexical only. |
| 0.4 | `rebuild_index()` never removes stale entries — in **either** backend | `vector_store.py:356` comment says "Reset TF-IDF index (ChromaDB collection handles upsert natively)". The code under it only does `mkdir` — the TF JSON index is never cleared. Chroma `upsert` (`:258`) adds/updates, never deletes. | Deleted or renamed wiki files keep returning as search hits forever. The external analysis flagged only the Chroma half; the TF half is also broken and the comment is false. |
| 0.5 | "TF-IDF" is TF-only | `vector_store.py:175-185` `_compute_tf_normalized` docstring: "named TF (not TF-IDF) because IDF requires corpus statistics". Module docstring (`:5,:10`) and names (`_TFIDF_INDEX_FILE`, `_load_tfidf_index`) still say TF-IDF. | Mislabelled capability. Note: `rebuild_index()` *does* see the whole corpus, so IDF is only ever correct as a full-corpus rebuild step there, never an incremental one (see PR-4). |
| 0.6 | No end-to-end test of the chain | `tests/test_vector_store.py` (29 tests) covers tokenize/TF/cosine/index/search in isolation. `grep -rn "projects/\|rglob" tests/test_vector_store.py tests/test_knowledge_librarian*.py` → 0 hits. | 0.1–0.4 shipped with a green suite. Unit coverage without an integration path is exactly the "registered ≠ working" failure this repo already has a named pattern for. |
| 0.7 | Stale memory claim | `.claude/memory/goals.md:18`: "✅ data_bridge.py — семантический мост META_GRAPH_V8 ↔ Obsidian (2026-06-20)". `find . -name "data_bridge*"` → nothing. Only `hooks/doc_bridge.py` exists; root `CLAUDE.md` says `data-bridge` is a *personal skill* outside this repo. | A memory file asserts a repo artifact that does not exist. |
| 0.8 | Legacy root `memory/` still present | `memory/{activeContext.md,decisions.md,templates/}` exist. `docs/memory-architecture.md:70-71` lists retiring it as a target, pending a `find_file_upward` resolution check. | The "four overlapping systems" debt is still four. |

What is **already good** and must not be regressed: `post_commit_memory.py` daily archive + 15-entry cap
(`:37,:59`); the 2026-08-28 `activeContext.md` split; PARA routing; attention decay
(`knowledge_librarian.py:155 _score_entry`, single definition); `processed: true` idempotency;
all memory hooks are `class: observability`, `fail_mode: open` in `hooks/registry.yaml` — they
must stay non-blocking.

---

## 1. Goal

Make the memory layer that **already exists** actually work end-to-end, prove with a measurement
that its semantic component earns its place, and only then — gated on that measurement and on a
recorded real need — extend it with an episodic (dialogue/event) layer.

Success is defined by §5 acceptance gates, not by feature count.

## 2. Non-goals (explicit, with the rule that forbids each)

| Not in scope | Why |
|---|---|
| A new memory framework / `hooks/lib/memory/{coordinator,router,adapters}` package + 4 JSON schemas | Structure-Bias Guard (`rules/falsification-ladder.md`): structure the *output contract*, not the reasoning layer. **Corrected 2026-09-03** (an earlier draft wrongly claimed a `CLAUDE.md § KNOWLEDGE STORES` table already routes this *in the repo* — `[VERIFIED]`: `git grep` finds it nowhere in tracked files; it is the maintainer's personal config, see §4.1). The real justification is simpler: everything this PACKAGE's ambition covers that is actually IN this repo (`activeContext.md`, `decisions.md`, `history/`, `patterns.md`) already has direct, working readers (`session_start.py`, `knowledge_librarian.py`) — a dispatcher over 4 files in one directory is overhead, not a gap. Routing across the maintainer's *personal* cross-tool stack (Obsidian/Graphify/NotebookLM) is real but out of this repo's product boundary entirely (§4.1 decision (a)), not something this repo's code needs to arbitrate. |
| Episodic dialogue store (`events.sqlite`, transcript import, consolidation, supersede/expire/forget, FTS5+RRF) **in this iteration** | `decisions.md § 2026-09-02` ("B now, A later") and the same-day RetroBench/VerificationOps deferral: no Product Constitution §7 (stable-pack) infra ahead of a measured need. The schema is *agreed* here (§4.3) so it is not re-designed later; building it is Phase 3, conditional. |
| Graphify write access, automatic per-session Graphify calls, bidirectional Obsidian↔memory sync | Both external analyses agree; this repo's own `[AVOID]` history (2026-07-06 dual-write split of `decisions.md`) shows what multi-writer memory does. |
| Replacing Markdown/Git as source of truth with a DB | LongMemEval-V2 (file-based AgentRunbook 72.5% vs RAG 48.5%) and this repo's whole provenance model. Indexes are rebuildable projections, never truth. |
| Touching native Auto Memory (`~/.claude/projects/<p>/memory/`) | It is Claude Code's own mechanism with its own loader (200 lines / 25 KB index). Custom memory covers what it deliberately does not: git-anchored state, evidence, decisions, tool events. |

---

## 3. Phase 1 — Repair the existing chain (7 PRs, sequential — no fixed calendar estimate)

**Revised 2026-09-03 after a third external review** — verified against the code, not adopted
as-is (verdict trail in the amendment note above §0). Two real design flaws in the first draft
are fixed here: `rel_path` was declared authoritative while Chroma kept `ids=[title]` (direct
contradiction with Gate 5.1's exact-equality requirement, and would not even fix the
duplicate-title collision it was meant to fix); and PR-1 alone would make the already-unconditional
per-Stop full reindex (`raw_to_wiki.py:930-937`, `[VERIFIED]` — comments there literally say
"always regenerate") scan a larger recursive tree and re-embed every document every time,
regardless of whether anything changed.

**Corrected rule:** root `CLAUDE.md:133` says reviewer is mandatory for this repo, full stop —
not gated at "3+ files" (that threshold is this session's own personal-account convention,
conflated into the first draft by mistake). Every PR below gets a reviewer pass, run in an
**isolated `git worktree`** (`decisions.md § 2026-09-03`); check PR review-bot comments, not
only CI status, before merging; `pytest tests/ -q`, `ruff check .`,
`mypy --ignore-missing-imports hooks/ scripts/`, `check_architecture.py --check`,
`gen_hook_matrix.py --check` all green; README test count synced from the PR's own CI line.
**FL tier, corrected to Full (Codex review, PR #332):** `rules/falsification-ladder.md:81-86`
puts "schema, architecture" changes in the Full tier, not Standard — this phase introduces a
versioned on-disk index schema (PR-4 below) and a shared data model
(`WikiRef`/`SearchHit`/`RebuildReport`), squarely matching that trigger. Full-Ladder artifacts
under `experiments/20260903-memory-retrieval-repair/`: `claim.md`, `controls.md`,
`stress_tests.md` (adversarial cases: a corpus with 1000+ entries for fingerprint-hash cost, a
file that changes mid-rebuild, a Unicode/RTL title, a zero-byte `.md` file), `decision.md`. Most
of the ladder's other machinery is already present under this spec's own names rather than
FL's: §0's verified ground truth table *is* the claim's evidence base; §5's floor-ceiling gate
*is* FL Step 4a; the "checked, not adopted" review trail in the Origin note *is* the Step 8a
skeptic-response pattern. One experiment folder covers the whole phase, not one per PR — the
phase is one claim ("this retrieval chain now works end-to-end and the semantic layer earns its
keep"), not seven independent ones.
"One day" was a guess, not a commitment — dropped.

### Shared data model (introduced in PR-1, used by every PR after it)

```python
# hooks/lib/wiki_types.py (new, stdlib-only — shared by vector_store.py and knowledge_librarian.py)
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class WikiRef:
    """The one join key between index and file, everywhere. rel_path is
    POSIX-style, relative to WIKI_DIR (e.g. 'projects/2026-09-02_x.md')."""
    rel_path: str
    title: str  # display only, never a lookup key

@dataclass(frozen=True)
class SearchHit:
    ref: WikiRef
    score: float  # keyword-overlap score OR cosine similarity, per `source`
    source: Literal["keyword", "dense"]

@dataclass(frozen=True)
class RebuildReport:
    scanned: int
    indexed: int
    deleted: int
    failed: int
    skipped: int      # unchanged per corpus fingerprint (PR-1) — not re-embedded
    backend: Literal["chroma", "tf"]
    changed: bool      # False when the whole rebuild was a fingerprint no-op
```

`ids=[title]` is retired immediately, not phased out — `Structure-Bias Guard` and this repo's
own Non-goals (§2: "indexes are rebuildable projections, never truth") both say a stale on-disk
index is a `rebuild_index()` call away from correct, so there is no real migration cost to
avoid. `format_version: 2` is introduced in PR-4 (not here in PR-1 — see PR-1's amended
fingerprint-storage note below for why) as a root-level key in the TF index JSON, so a pre-PR-4
index is detected and forces one rebuild rather than being silently misread. Chroma has no
equivalent "file" to version — `rel_path`-keyed `ids` from PR-2 onward are self-describing
without a separate version marker; a stale Chroma collection using `title` as `ids` is simply
overwritten by the next `rebuild_index()` regardless.

### PR-1 — Corpus fingerprint gate + recursive indexing + the missing integration test (fixes 0.1, 0.6, and the Stop-hook cost risk found in review 3)

- **Fingerprint first, recursion second:** `_corpus_fingerprint(wiki_dir) -> str` hashes the
  sorted `(rel_path, size, mtime)` triples of every indexable file (same exclusions as below).
  **Stored in a sidecar file (`corpus_fingerprint.txt` next to `tf_index.json`), not as a field
  inside the TF index JSON itself** — a Codex review on PR #332 correctly caught that
  `_load_tfidf_index()` currently treats every top-level JSON key as a document vector and
  `semantic_search()` feeds each one straight into `_cosine()`; a root-level
  `format_version`/`corpus_fingerprint` key there would be silently treated as a malformed
  "document" and crash `_cosine()` inside the fail-open search path, returning `[]` instead of
  real results — breaking PR-1's own acceptance test while looking, from the fail-open catch,
  like nothing happened. The sidecar avoids touching the TF index's on-disk shape at all in this
  PR; the versioned wrapper schema described in the shared data model above is introduced
  properly in this branch's PR-4 (real IDF), not bolted onto PR-1's fast path. `rebuild_index()`
  compares the fresh fingerprint against the sidecar's stored value; if equal, return a
  `RebuildReport(changed=False, skipped=<all>, ...)` immediately — no file reads, no embedder
  load, no TF recompute. This directly answers review 3's finding: PARA recursion makes the
  corpus larger, but an unchanged corpus after this PR costs one hash comparison plus one small
  sidecar read, not a full re-embed, on every Stop.
- **Test first (RED):** `tests/test_memory_retrieval_chain.py` — write a raw note →
  `raw_to_wiki` routes it into `wiki/projects/` → `rebuild_index(wiki)` → `semantic_search(<its
  key terms>)` returns it. Must fail on `main` today (`glob` skips `projects/`). A second test:
  calling `rebuild_index()` twice with no filesystem change between calls produces
  `changed=False` on the second call and does not invoke the embedder (patch it and assert
  `call_count == 0`).
- **Fix:** `vector_store.py:363` `glob("*.md")` → `rglob("*.md")`, excluding `daily/` and
  `index.md` exactly as `knowledge_librarian._query_wiki_raw_titles` already does (`:312-317`),
  so the two scanners agree on the corpus.
- **Acceptance:** both new tests GREEN; `test_skips_index_md` / `test_skips_chunk_files` still
  pass; a PARA-routed entry appears in `semantic_search()` results; measured wall-clock for an
  unchanged-corpus `rebuild_index()` call is reported in `metrics/run.json` (must be sub-second
  regardless of wiki size — it's a hash comparison, not a scan of file contents).

### PR-2 — `rel_path` is the real key, everywhere, from the start (fixes 0.2)

- **Decision (corrected):** `rel_path` is the Chroma `id` and the TF JSON key, immediately — not
  a metadata field alongside a legacy `title`-keyed `id`. Two files sharing an H1 title no longer
  collide (each gets its own `rel_path`).
- **Changes:**
  - `vector_store.index_wiki_entry(ref: WikiRef, body, tags)` replaces the
    `(title, body, tags)` signature — `ref.rel_path` is `ids=[...]` for Chroma and the TF
    record key; `ref.title` is stored as display metadata only.
  - `semantic_search_paths(query, top_k) -> list[SearchHit]` (new function) is the production
    entry point; the old `semantic_search() -> list[str]` (title strings) is kept only for its
    existing 29 unit tests and marked deprecated in its docstring — no production caller left
    after PR-5.
  - `raw_to_wiki.update_wiki_index()` writes real Obsidian alias syntax:
    `- [[projects/2026-09-02_x|AUC Red Flags]]`, not an HTML comment. `[VERIFIED]`:
    `knowledge_librarian.py:164,590` already does `title.split("|")[0]` — confirmed via grep
    this is currently *unreached defensive code* (nothing writes a `|`-bearing title today), so
    switching to real alias syntax activates an existing code path rather than adding a second,
    parallel, invisible markup convention. The extraction regex in `_query_wiki_raw_titles`
    (`re.findall(r"\[\[([^\]]+)\]\]", ...)`) needs no change — it captures the whole
    `path|title` string; splitting happens where `_score_entry` already splits it.
  - `knowledge_librarian._read_wiki_content(ref: WikiRef)` takes the dataclass directly — no
    more stem-guessing fallback chain for entries that went through the new index; the PARA
    fallback (`:515-519`) stays only for legacy pre-migration entries.
  - `_score_entry(ref: WikiRef)` updated to accept the dataclass instead of a bare title string
    (it already computes the stem via the same `split("|")` logic — now redundant with
    `ref.rel_path`, simplified to use it directly).
- **Acceptance:** extend PR-1's chain test: the HOT-tier path opens the matched file and returns
  non-`None` content for an entry whose title ≠ stem (the exact `_read_wiki_content("AUC Red
  Flags") → None` reproduction becomes a regression test). **New:** two distinct files sharing an
  identical H1 title are both indexed and both individually retrievable (the collision test the
  first draft was missing). Security tests from PR #106 (`../`, NUL, path escape) still pass —
  `rel_path` goes through the same `resolve()`/`relative_to(WIKI_DIR)` boundary check.

### PR-3 — Atomic, reported rebuild (fixes 0.4, and the fail-open/partial-index gap found in review 3)

- **Ordering, not just "clear then reindex":** `[VERIFIED]` — the current fail-open
  `except Exception: pass` inside `rebuild_index()`'s loop means a mid-rebuild crash after a
  destructive clear would leave a genuinely empty index, worse than the stale one it replaced.
  New sequence: (1) scan + build every `WikiRef`/vector into an in-memory batch, tolerating
  per-file failures (`failed` count, file skipped, loop continues — unchanged fail-open
  philosophy for individual bad files); (2) write the TF batch to a temp file, `os.replace()`
  onto the real index path (atomic on both POSIX and Windows); (3) for Chroma, batch `upsert`
  the new set, then `collection.delete(ids=<ids present before this run, absent from this run>)`
  — delete only fires after the upsert succeeds, so a batch failure leaves the old collection
  untouched rather than partially cleared.
- Fix the false comment at `vector_store.py:356` ("Reset TF-IDF index... ChromaDB handles upsert
  natively" — neither backend was actually clearing stale entries; say what the code now does).
- `rebuild_index()` returns `RebuildReport`, not a bare `int` — `raw_to_wiki.py:937`'s call site
  updated to log the structured report (scanned/indexed/deleted/failed/skipped) instead of a
  single count, so a bad run is visible in Stop-hook output, not silently folded into "N indexed."
- **Acceptance:** test — index A and B, delete B's file, rebuild, search for B's terms → not
  returned, in both backends (Chroma path mocked as in
  `test_semantic_search_fails_open_without_chromadb`). **New:** a rebuild where file 2 of 3
  raises during read leaves files 1 and 3 correctly indexed and reports `failed=1`, not a
  half-written index or a report claiming `indexed=3`.

### PR-4 — Honest naming, and real TF-IDF as a full-corpus-only operation (fixes 0.5) — **moved ahead of the old PR-5 slot, per Codex review on PR #332**

**Reordering rationale:** §5.3's floor–ceiling benchmark is meant to measure the *final*
ranking algorithm's efficiency. With the old PR-4/PR-5 order, §5.3 would have run against
TF-only vectors (real IDF not yet landed), then IDF would land afterward and silently change the
ranking the gate had just measured — the gate's own pass/fail verdict would not describe the
system that ships. Real IDF now lands before the semantic-wiring PR that the gate covers.

- **Consistency check `[VERIFIED]` (kept from the earlier draft, still holds):**
  `grep -rln "index_wiki_entry(" hooks/ scripts/` → only `vector_store.py` calls it;
  `grep -rn "rebuild_index(" hooks/*.py` → only `raw_to_wiki.py:937` calls that. Every index
  write today is a full-corpus `rebuild_index()` sweep — no incremental single-document write
  path exists in production.
- **Design corrected (Codex review, PR #332, P1 — the earlier `idf` parameter design was wrong,
  not just incomplete):** an earlier draft proposed `index_wiki_entry(ref, body, tags, idf=...)`
  with a required `idf` argument as an "incremental-write guard." That does not work: real
  corpus-wide IDF (`log(N / document_frequency)`) is a property of the *whole corpus* — adding,
  removing, or editing even one document changes `N` and every term's document frequency,
  which invalidates the stored weight of **every other document already in the index**, not just
  the one being written. A required `idf` parameter cannot prevent this; a caller can pass a
  stale-but-present `idf` dict and produce a silently inconsistent index, which is worse than an
  honest TF-only one. **There is no safe incremental TF-IDF update — full re-derivation is the
  only correct operation, so this PR does not touch `index_wiki_entry()`'s signature at all.**
  Instead:
  1. `index_wiki_entry()` stays exactly as before this PR — TF-only, per-document, no `idf`
     parameter, matching its only real caller (`rebuild_index()`) and its already-honest
     docstring once PR renames land (see below).
  2. `rebuild_index()` gets a **second pass**, after all documents are TF-indexed for this run:
     compute real corpus-wide `idf` from the freshly built document set, then re-weight every
     in-memory vector by it before the atomic write (PR-3's snapshot-then-swap covers the write
     itself). This is the only place IDF is ever computed or applied — it is inherent to
     "rebuild the whole index," not bolted onto an incremental path that doesn't exist.
  3. The versioned schema (introduced here, not in PR-1 — see PR-1's amended fingerprint note
     above) carries the corpus-wide `idf` alongside the reweighted documents:
     ```json
     {
       "format_version": 2,
       "corpus_fingerprint": "<PR-1's sidecar value, now co-located here>",
       "idf": {"term": 1.83, "...": "..."},
       "documents": {"projects/x.md": {"title": "...", "vector": {"term": 0.4}}}
     }
     ```
     `semantic_search_paths()`'s TF-fallback path loads this `idf` dict and applies it to the
     **query** vector before cosine similarity (an index with IDF-weighted documents scored
     against a plain-TF query vector is not real TF-IDF similarity — both sides need the same
     weighting).
  4. Once this schema lands, PR-1's separate `corpus_fingerprint.txt` sidecar is retired — the
     fingerprint moves into this same versioned file, one source of truth instead of two.
- Rename module docstring / constants from "TF-IDF" to "TF (per-document, incremental-safe) /
  TF-IDF (corpus-wide, rebuild-only)" so the name matches what each function actually computes.
  Keep `tf_index.json` filename (on-disk compatibility; `format_version` inside signals the
  schema change).
- **Acceptance:** a query whose relevant term is rare corpus-wide ranks above a query match on a
  common term with the same raw count (the actual behavioural difference real IDF is for) —
  regression test comparing ranking with the reweight step disabled (pure TF) vs enabled (real
  IDF). **New (closing the design gap directly):** a test that mutates the corpus (adds one
  document) between two `rebuild_index()` calls and asserts every document's stored IDF weight
  changed accordingly — not just the new document's — proving the whole-corpus reweight actually
  ran, not a per-document patch.

### PR-5 — Wire semantic retrieval into the production path, with real HOT-tier scoring — **gated by §5.3** (fixes 0.3, and the HOT-tier scoring gap found in review 3) — depends on PR-4 landing first

- In `_query_wiki_raw_titles()`: when keyword hits `< TIER_CANDIDATE_LIMIT`, top up from
  `semantic_search_paths()` (dedup by `rel_path`), returning `list[SearchHit]` instead of
  `list[str]` so the tier classifier downstream can tell keyword hits from dense hits.
- **HOT-tier fix (the gap the first draft missed):** `[VERIFIED]` —
  `knowledge_librarian.py:444-450`'s relevance formula is 50% keyword overlap + 50%
  recency/frequency; a dense-only hit (found by meaning, zero literal keyword overlap) scores at
  most 0.5 and structurally cannot cross `HOT_THRESHOLD=0.65` — it would always render as WARM
  (title-only) or COLD, never as a full HOT snippet, defeating the point of adding semantic
  search at all. Fix: for a `SearchHit` with `source="dense"`, substitute its cosine similarity
  for the keyword-overlap term in the same 50/50 blend (a strong dense match IS the relevance
  signal for that hit, the same role keyword overlap plays for a lexical hit) — do not invent a
  second threshold or scoring path, reuse the existing HOT/WARM/COLD constants unchanged.
- Delete `_query_wiki()` (dead; also closes the C901/duplication item recorded 2026-09-03).
- **Do not merge until §5.3's floor–ceiling measurement shows the supplement helps.** Because
  PR-4 now lands first, this measurement runs against the real TF-IDF ranking, not a TF-only
  placeholder that would be replaced immediately after. If §5.3 fails, this PR becomes "delete
  `_query_wiki`; keep Chroma optional but off by default" and the `chromadb` extra is documented
  as experimental.
- **Acceptance:** the exact scenario review 3 named — a query using a synonym with zero literal
  keyword overlap — retrieves the entry via `semantic_search_paths`, `_read_wiki_content`
  successfully opens it by `rel_path`, and the corrected scoring renders it HOT (full snippet),
  not silently downgraded to WARM.

### PR-6 — Memory hygiene items already owed by `docs/memory-architecture.md` (fixes 0.7, 0.8) — split into two independent PRs per review 3

- **PR-6a:** `goals.md:18` — change the ✅ to the truth: "personal skill `data-bridge` on the
  maintainer's machine; no `data_bridge.py` in this repo." One line, no code, Micro-Ladder.
- **PR-6b (independent, can land before or after 6a):** retire legacy root `memory/` — add a
  test that `find_file_upward`/`find_decisions_file()` resolve to `.claude/memory/` from the
  repo root and from a nested cwd; then delete `memory/{activeContext.md,decisions.md}` (keep
  `memory/templates/` only if something imports it — grep first). Exact precondition the design
  doc already set (`docs/memory-architecture.md:70-71`).

### PR-7 — Path-drift cleanup in `rules/memory-protocol.md` (new, found while implementing)

- `rules/memory-protocol.md` documents `~/.claude/memory/raw/`; `raw_to_wiki.py` and
  `raw_to_wiki.main()`'s own print statements actually use `~/.claude/memory/_auto/raw/` and
  `_auto/wiki/`. Fix the doc to match the code (the code is load-bearing and correct; the doc
  drifted). One-line-per-mention Micro-Ladder fix, no code change.

---

## 4. Contracts agreed now, built later

### 4.1 Source-routing table — scope correction (2026-09-03, second review caught this)

**Correction:** an earlier draft of this section said "extend root `CLAUDE.md § KNOWLEDGE
STORES`", treating that table as part of this repo. `[VERIFIED]`: `git grep -l "KNOWLEDGE
STORES"` across the whole tracked repo returns **zero matches**; the table exists only in the
maintainer's personal `~/.claude/CLAUDE.md` (private global config, not distributed with this
project). Neither `CLAUDE.md` (repo root) nor `claude-md/CLAUDE.md` (the installable template)
contains anything like it. There is nothing in this repository to "extend."

Two honest options, not one:
- **(a) Out of scope.** The routing table is the maintainer's own personal practice, orthogonal
  to a repo whose product is hooks/agents/skills for *other* installs. Do nothing here; drop this
  subsection.
- **(b) In scope, but newly authored.** If a source-routing convention is meant to ship with this
  repo (so any installer's Claude gets the "when NOT to call an external store" discipline too),
  it must be *written*, not extended, in `docs/memory-architecture.md` or `claude-md/CLAUDE.md`
  — as a NEW section, scoped only to sources this repo actually ships (Obsidian hooks,
  `null_results/`, `patterns.md`) — never referencing graphify/NotebookLM/Perplexity, which are
  the maintainer's personal tooling, absent from `requirements.txt` and from the installable
  template.

**Decision for this ТЗ: (a).** This phase is about repairing `hooks/vector_store.py`/
`knowledge_librarian.py`, both shipped repo code — not about codifying the maintainer's personal
knowledge-store habits into the distributable product. If a documented routing convention is
wanted for repo contributors later, it is a separate, small Micro-Ladder doc PR against
`docs/memory-architecture.md`, decided independently of this repair.

### 4.2 Ownership tables — split by root, per review 3's correct catch

The first draft put project-tracked, global-personal, and derived-cache paths in one table,
which read as though they share a trust/lifecycle model. They don't — split by root, with
`[VERIFIED]` real paths (not the `memory-protocol.md`-documented ones, which drifted — PR-7).

**1. Project (repo-tracked, in Git, `<repo>/.claude/memory/`):**

| Path | Writer | Everyone else |
|---|---|---|
| `activeContext.md` | orchestrator session (direct edit) **+ `post_commit_memory.py` hook** (automatic per-commit append — this is the one exception to "orchestrator only," and it's a hook, not a sub-agent, so it doesn't violate the sub-agent-write restriction) | read |
| `decisions.md` | controlled append via hooks / `/capture` | read; see `memory-protocol.md` dual-path rule |
| `goals.md` | orchestrator/hooks | read |
| `history/` | archive pipeline (`post_commit_memory.py`) | read |

**2. Global/personal (`~/.claude/memory/`, outside this repo, not distributed):**

| Path | Writer | Everyone else |
|---|---|---|
| `_auto/raw/` (inbox) | human / Obsidian web clipper | read |
| `_auto/wiki/**` | `raw_to_wiki.py` only | read |
| `_auto/wiki/index.md` | `update_wiki_index()` only | never hand-edit |
| `patterns.md`, `playbook.md` | auto-generated (`pattern_extractor.py`, `ace_reflector.py`) | never hand-edit, per `memory-protocol.md`'s own existing rule |

**3. Derived cache (rebuildable projections, never a source of truth):**

| Path | Writer | Everyone else |
|---|---|---|
| `~/.claude/cache/vector_db/tf_index.json` | `rebuild_index()` only, atomic replace (PR-3) | never hand-edit; safe to delete, next `rebuild_index()` regenerates it |
| ChromaDB collection (if configured) | `rebuild_index()`/`index_wiki_entry()` only | same — safe to drop and rebuild |

Goes into `docs/memory-architecture.md`. Enforce later only if a violation is observed.

### 4.3 Episodic event record (agreed schema; Phase 3 only)

```yaml
id: mem_<ulid>
type: episode | fact | decision | procedure | feedback
scope: {repository, worktree, branch}
session_id: <claude session id>
observed_at: <ISO-8601 UTC>
content: <text>
source: {kind: dialogue|tool|commit, transcript: <path>, turn_ids: [...], commit_sha: <sha|null>}
trust: verified | tool_observed | user_asserted | assistant_claim
status: candidate | active | superseded | expired | deleted
supersedes: <id|null>
valid_from / valid_to: <ISO-8601|null>
confidence: 0..1
sensitivity: internal | private
```

Hard rule inherited from `integrity.md`: an `assistant_claim` never auto-promotes to `fact`.
Promotion requires `tool_observed` or `verified` evidence attached.

### 4.4 Graphify result stamp (read-only candidate source)

Any Graphify-derived suggestion carries `{source: graphify, graph_version, generated_at,
input_snapshot: {repo: sha}, query, status: candidate}` and enters memory only through the
same promotion gate as 4.3. Never writes `activeContext.md`/`decisions.md` directly.

---

## 5. Acceptance gates and metrics (3 hard gates, not 9 soft ones)

| Gate | Measure | Pass |
|---|---|---|
| 5.1 Index consistency | After `rebuild_index`, set(index ids) == set(wiki files minus `index.md`/chunks/`daily/`), for TF and Chroma. IDs are `rel_path` after PR-2 — no title collisions to average away. | exact equality (test in PR-3) |
| 5.2 HOT-tier read success | **Revised to 100%, not ≥0.95, per review 3; scope narrowed per review 4 (Codex, PR #332):** after PR-2, every entry indexed through the new `WikiRef`-keyed pipeline has a `rel_path` that resolves directly at rebuild time — `RebuildReport.failed` counts every failure `rebuild_index()` itself can observe. This gate covers exactly that population. It does **not** cover a file deleted, corrupted, or grown past the size cap in the window between a rebuild and a later `SessionStart` query — that is a real, separate, narrower failure class (retrieval-time, not rebuild-time), correctly out of scope for this specific gate rather than silently absorbed into it. | 100% of `RebuildReport`-observable outcomes at rebuild time; any exception there is a counted, visible `failed`, not a tolerated fraction. Retrieval-time failures (rare: file removed after indexing) are not claimed by this gate — if `_read_wiki_content()` ever returns `None` for a `rel_path` that `RebuildReport` marked successful, that is a bug report, not a gate violation, since the corpus changed after the measurement. |
| 5.3 Floor–ceiling efficiency of the semantic supplement (`rules/falsification-ladder.md` Step 4a) | **Public/private split, per review 3** (an earlier draft would have committed real personal wiki paths and titles to this public repo): <br>**(a) Public fixture** — `tests/fixtures/memory_retrieval/` — a small, synthetic, sanitized wiki (a handful of `.md` files with made-up titles/content, some with duplicate H1s, some in PARA subdirs) checked into Git. Exercises the mechanics (PR-1's fingerprint gate, PR-2's collision handling, PR-3's atomic rebuild, PR-4's IDF ranking) in CI, with zero personal data. <br>**(b) Private benchmark** — `~/.claude/memory/benchmarks/retrieval_v1.jsonl` (outside Git, never committed), **frozen** before PR-5 is written: ≥30 real questions mined from `history/` and Obsidian session notes, each with `relevant_rel_paths: [...]` (a list — a query can have more than one right answer, not just one), reviewed by a second, context-blind pass for "is this actually the best match" before freezing. Split into RU/EN sub-slices and reported separately, not pooled (`[HYPOTHESIS]`, per review 3: the embedder may perform asymmetrically across languages — this is what would show it, an unverified guess otherwise). **Floor** = keyword-only `_query_wiki_raw_titles`. **Ceiling** = the human pick (1.0). **Observed** = keyword + semantic top-up. **Metric corrected to Hit Rate@3, not Recall@3, per review 4 (Codex, P1):** since a query can have multiple `relevant_rel_paths`, a binary "found at least one of them in the top 3" tally is Hit Rate@3 (a.k.a. Success@3) — true Recall@3 would instead average, per query, `|retrieved ∩ relevant| / |relevant|`, which the described raw-pass-count tally does not compute (finding 1 of 3 relevant entries would count as a full pass under the tally, but has recall 1/3). Hit Rate@3 is the metric actually being measured and is adequate for a ≥30-query gate; report it by that name, as **raw pass counts** (e.g. "9/30" not just "30%") for floor, ceiling, and observed, each language slice separately, plus the pooled figure. | Merge PR-5 only if observed − floor ≥ 0.10 absolute Hit Rate@3 on the frozen private benchmark, **and** the public fixture's mechanical tests (collision, atomicity, ranking) all pass in CI. If the private-benchmark gate fails, PR-5 degenerates to "remove dead `_query_wiki`, keep Chroma off by default, document as experimental" — the public fixture's tests still land regardless, since they test mechanics, not the efficiency claim. |

Also report (not gates): retrieval latency P50/P95 for keyword vs +semantic; injected characters
per SessionStart before/after; unchanged-corpus `rebuild_index()` wall-clock (PR-1's fingerprint
gate — should be near-constant regardless of wiki size). Record all numbers in
`experiments/20260903-memory-retrieval-repair/metrics/run.json` (public numbers only — no
private benchmark content) and the verdict in `decision.md`.

---

## 6. Phase 3 — Episodic layer (conditional; not scheduled)

**Trigger, all three required:**
1. §5.3 PROMOTE recorded (retrieval provably works), and
2. ≥ 3 logged real occurrences of "did we already discuss / try this?" being answered wrongly or
   not at all, recorded in `pearl_registry/INDEX.md` with dates, and
3. the owner picks it as the next **Product Constitution §7 (stable-pack) item**, ahead of
   pending §8 (experimental-pack) work — not to be confused with this document's own §7/§8 below.

**Shape when built:** append-only `~/.claude/memory/events.jsonl` (outside Git; private),
records per §4.3, imported from `transcript_path` at Stop; background consolidation (not on the
hot path); FTS5 first, embeddings only if §5.3-style measurement justifies them; `forget
--dry-run` returning candidates before deletion; cascade to derived memories and indexes.

Ordering rationale: the same reasoning that deferred VerificationOps and RetroBench on
2026-09-02 — instrument the existing thing, measure, then load. Building an episodic store on
top of a retrieval chain that cannot open its own hits would only make the failure larger.

---

## 7. Risks and rollback

| Risk | Mitigation |
|---|---|
| On-disk index format change breaks live `~/.claude/cache/vector_db/` (`[VERIFIED]` real path — a prior draft of this row named `~/.claude/memory/_auto/vector_db/`, which does not exist) | PR-4's `format_version` stamp (introduced there, not PR-1 — PR-1 only adds a separate fingerprint sidecar, per review 4's correction) makes a v1 index self-identifying; any reader sees the wrong version and forces one `rebuild_index()` rather than misreading `title`-keyed data as `rel_path`-keyed. No transitional dual-key period (§3 shared data model) — the index is a rebuildable projection, one rebuild fixes it. Live drift is already tracked by `live_drift_guard.py` — redeploy is explicit. |
| `rglob` picks up `daily/` or archived noise, or makes every Stop slower | Same exclusion list as the librarian; PR-1's corpus-fingerprint gate makes an unchanged corpus a no-op rebuild (hash compare only, no re-embed) — this is the actual mitigation for the performance risk review 3 raised, not just an exclusion list. |
| Semantic top-up injects irrelevant context (token cost) | Gated by §5.3; `TIER_CANDIDATE_LIMIT` unchanged; report injected chars. |
| Retiring `memory/` changes hook resolution | PR-6b's own test runs from root and nested cwd before deletion; revert = `git revert` of one PR (6b only — 6a is independent). |
| Reviewer collides with concurrent branch switches | Isolated worktree per review (established 2026-09-03). |
| Private benchmark (§5.3b) accidentally committed | It lives under `~/.claude/memory/benchmarks/`, outside this repo's working tree entirely — not a `.gitignore` reliance, a different filesystem root. `experiments/.../metrics/run.json` records only aggregate numbers, never benchmark question text or `rel_path` values. |

Each PR is independently revertible; none changes hook `class`/`fail_mode` (all stay
`observability` / `open`).

---

## 8. Out-of-scope follow-ups (recorded so they are not lost)

- `instructions_audit.py`-seeded `/config-explain` (design doc §"Also flagged").
- `paths:`-scoped rules to cut instruction noise (design doc).
- `.claude/memory/procedures/` (procedural memory) — target-table item, still absent.
- Cross-agent memory portability (Codex/Gemini) — year horizon in the external analysis; not before Phase 3.
