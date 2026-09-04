# decision.md — 20260903-memory-retrieval-repair (PR-1)

## Verdict

- [x] PROMOTE — claim holds; merge to main
- [ ] REPEAT
- [ ] REJECT
- [ ] ARCHIVE

## Result Classification

- [ ] 🥇 Gold
- [ ] 💎 Diamond
- [ ] 🥈 Silver
- [x] 🪨 Stone — a real, needed correctness fix, but not a transferable technique
      beyond this repo's own indexing pipeline. No cross_domain_insights.md entry.

## Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | PASS |
| Negative control | PASS |
| No-collapse tests | 4/4 applicable PASS, 1 N/A documented (see controls.md) |
| Stress tests | 6/6 PASS (2 added after reviewer finding, see below) |
| Substrate gate (2a) | READY |
| Full test suite | 3034 passed, 1 pre-existing unrelated failure, 3 skipped, 2 xfailed |
| ruff / mypy / architecture gates | clean |
| External reconstruction | [VERIFIED-REAL], see result_summary.md |

## Skeptic Concerns (Step 8a)

This PROMOTE is for PR-1 only — a narrow, mechanically verifiable file-discovery
and no-op-skip fix. Per the TZ's cost-discipline note (falsification-ladder.md
§8a), a full adversarial skeptic dispatch is reserved for the PR that carries
real risk of a wrong PROMOTE (PR-4's whole-corpus IDF reweight, PR-5's HOT-tier
scoring change gated by §5.3). Substituting: an isolated-worktree `reviewer`
agent (context-blind to this decision.md, working only from the diff and the
commit message) was dispatched against PR-1's own pull request BEFORE merge.

**Finding, verified and fixed (not dismissed):** the reviewer reproduced, with
a tool (monkeypatching `index_wiki_entry()` to its own documented fail-open
contract), that `rebuild_index()`'s `except Exception: failed += 1` could
never observe an internal indexing failure — `index_wiki_entry()` already
swallows its own exceptions two frames down, so every such failure was
counted as `indexed`, contradicting `RebuildReport`'s stated purpose. The
reviewer additionally showed this compounds with the fingerprint gate: a
permanently-failing file's stat still gets fingerprinted, so the failure
becomes permanently invisible to any later `rebuild_index()` call.

- Concern: internal indexing failures counted as success → **Fixed**:
  `index_wiki_entry()` and `_save_tfidf_index()` now return `bool`;
  `rebuild_index()`'s loop checks the return value instead of relying only
  on an exception crossing two function boundaries. See stress_tests.md Case 5.
- Concern: a failed rebuild's fingerprint permanently hides the failure →
  **Fixed**: the fingerprint is now saved only `if failed == 0`, forcing a
  retry of the whole corpus on the next call after any failure. See
  stress_tests.md Case 6.
- Concern (P2, same review): `_save_fingerprint()` used a non-atomic
  `write_text()` unlike its sibling `_save_tfidf_index()` → **Fixed**: matched
  the existing tmp-file + `os.replace()` pattern already used in this file.

Separately, the GitHub Codex bot review that ran on the TZ doc itself
(PR #332) caught and corrected the fingerprint-storage design risk this PR-1
code already avoided independently (sidecar file, not embedded in
`tf_index.json`) — recorded as additional external verification. A Codex bot
pass also runs on PR-1's own pull request before merge, per this session's
standing process.

## Caveats

1. The one pre-existing test failure
   (`tests/test_check_global_hooks.py::TestUnmockedImport::test_raises_filenotfounderror_on_a_machine_without_the_hardcoded_path`)
   is unrelated to this change — verified by reproducing it with PR-1's diff
   stashed out entirely (same failure, same message). It reflects the
   documented live-vs-repo hook drift on this machine (`CLAUDE.md`'s own
   "local Windows runs collect a handful more/fewer environment-dependent
   tests" note), not a regression from this PR.
2. This PR does not touch `knowledge_librarian.py`'s HOT/WARM/COLD scoring —
   PR-5 remains a separate, gated PR.
3. `RebuildReport` is a new return type replacing a bare `int`; every call
   site (`hooks/raw_to_wiki.py`) and every test asserting on the return value
   was updated in this same PR — verified via the full-suite run above
   (0 unexpected failures involving `rebuild_index`).

## Floor-Ceiling Interval (Step 4a)

Not applicable to PR-1: this claim is a binary correctness property (a file
either is or isn't discovered by `rglob`; the fingerprint gate either does or
doesn't skip re-indexing), not a continuous metric with room to move between a
null-model floor and a privileged-access ceiling. The floor-ceiling interval
is a real, load-bearing gate for PR-4 (real IDF weighting quality) and PR-5
(HOT-tier ranking score, already named as gated by TZ §5.3) — it is deferred
there explicitly, not skipped silently. Recording this here per the audit
gate's own third-outcome discipline: "not applicable" is a distinct, stated
outcome, not an omission.

## Next (PR-1)

Commit PR-1, push, open PR, dispatch isolated-worktree reviewer, wait CI +
Codex bot comments, merge. Then continue to PR-2 (rel_path as real join key)
per the corrected TZ ordering.

---

## PR-2 — `rel_path` is the real join key (fixes 0.2)

### Verdict

- [x] PROMOTE — claim holds; merge to main

### Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | PASS — title != stem, HOT tier opens the real file end-to-end |
| Negative control | PASS — old "not found" behavior unchanged for bare missing titles |
| No-collapse tests | 4/4 PASS |
| Stress tests | 3/3 PASS (cases 7–9) |
| Full test suite | 3040 passed, 1 pre-existing unrelated failure, 3 skipped, 2 xfailed |
| ruff / mypy / architecture gates | clean |

### Design deviation from the TZ, stated explicitly

The TZ's PR-2 text describes `_score_entry(ref: WikiRef)` and
`_read_wiki_content(ref: WikiRef)` — literal `WikiRef`-typed signatures.
Implemented instead: both functions keep accepting the raw
`"rel_path|Title"` string already flowing through `_query_wiki`/
`_query_wiki_raw_titles`/`_classify_and_render_wiki` (none of which
construct a `WikiRef` object anywhere in their call chain — they work
entirely off regex-extracted strings from `index.md`), and parse it
internally via the same `.split("|")[0]` pattern already present as
dead code before this PR. This achieves the identical observable fix
(rel_path-based file lookup, no more title-as-filename guessing) without
threading a new dataclass through three call sites whose actual data flow
is fundamentally string-based, end to end. `vector_store.py`'s functions
(`index_wiki_entry`, `semantic_search_paths`) DO take `WikiRef` directly,
matching the TZ exactly, since those have a single, clean internal call
site (`rebuild_index()`) with no string-parsing legacy to work around.
Chosen for lower blast radius / regression risk, per this session's
Minimal Relaxation instinct after PR-1's reviewer-caught bugs — not a
disagreement with the TZ's design goal, only its literal mechanism.

### Additional fix beyond the TZ's explicit text, found while implementing

`_classify_and_render_wiki()` passed the raw `"rel_path|Title"` candidate
string straight into `_render_hot()`/`_render_warm()`, which would have
injected `[[projects/2026-...-x.md|AUC Red Flags]]` into Claude's actual
session context instead of a clean `[[AUC Red Flags]]` — a direct,
foreseeable consequence of writing rel_path-prefixed candidates that the
TZ's text didn't call out. Fixed in the same PR: a `display_title =
title.split("|")[-1].strip()` extraction before both render calls.

### Additional hardening found while implementing (not requested by the TZ)

`_score_entry()` built `WIKI_DIR / f"{stem}.md"` and read it directly with
NO `_is_safe_wiki_path()` boundary check — the exact PR #106 threat model
(`stem` originates from the same untrusted `[[...]]` index.md source) that
`_read_wiki_content()` was hardened against, but `_score_entry()`'s sibling
construction was never covered. Applied the same guard while touching this
exact line for the rel_path fix — narrow, in-scope hardening of a sibling
function with the identical defect class, not a new audit.

### Skeptic Concerns (Step 8a)

An isolated-worktree `reviewer` agent (context-blind, working only from the
diff and this PR's own commit) was dispatched against PR-2's pull request
before merge.

**Finding, verified and fixed (not dismissed):** the stale-entry defensive
check in `semantic_search_paths()`'s TF-IDF loop (`"vector" not in entry`)
checked KEY PRESENCE, not value SHAPE. A pre-PR-2 legacy flat entry that
happens to contain the literal TF term `"vector"` (plausible in this repo's
own notes about `vector_store`) would pass the check, then hand `_cosine()`
a `float` instead of a `dict` — the resulting `TypeError` escapes the loop
to the function's outer fail-open `try/except`, silently blanking the
ENTIRE search result set for that query, not just skipping the one bad
entry. Reproduced with a tool (a `float` value under a literal `"vector"`
key raises `TypeError` in `_cosine()`) before applying the fix.

- Concern: presence check ≠ shape check, one collision can blank an entire
  query's results → **Fixed**: `not isinstance(entry.get("vector"), dict)`
  replaces the bare `"vector" not in entry` check. A new regression test
  (`test_search_skips_stale_entry_whose_term_collides_with_wrapper_key`)
  reproduces the exact collision and pins the fix.
- The reviewer's other 3 checks (path-traversal bypass attempt against the
  relaxed `/`-allowance, `_score_entry`'s date extraction on a rel_path
  with a PARA subdir, Chroma `metadatas`/`distances` positional-indexing
  safety) all came back HIGH-confidence clean — no fix needed, recorded
  here as verified rather than silently passed over.

### GitHub Codex bot findings (verified and fixed)

Two P2 findings posted on the pull request, both verified against the
actual code before applying:

1. **Fingerprint not invalidated on schema change**
   (`hooks/vector_store.py`): the corpus fingerprint is a pure function of
   file stats, not of the code reading them. An installation upgrading
   from PR-1's saved fingerprint (title-keyed, flat TF values) straight to
   PR-2's shape (rel_path-keyed, wrapped values), with no wiki file
   touched in between, would see `changed=False` on the next
   `rebuild_index()` call — leaving every old-shape entry stranded and
   silently skipped by the new shape-check, until an unrelated file edit
   finally forces a real rebuild. **Fixed:** a `_TF_SCHEMA_VERSION`
   constant is now salted into `_corpus_fingerprint()`'s hash input, so
   any on-disk value-shape change forces a mismatch regardless of whether
   any file changed. Regression test:
   `test_schema_version_change_forces_rebuild_of_unchanged_corpus`
   (simulates the upgrade by saving a fingerprint computed without the
   salt, confirms the next call still rebuilds).
2. **PARA fallback could silently read the wrong file**
   (`hooks/knowledge_librarian.py:554`): when a candidate named an
   explicit rel_path (e.g. `resources/foo.md`) that was missing or stale,
   the fallback stripped the directory and guessed at a same-named file in
   a DIFFERENT PARA category (`areas/foo.md`) — silently attributing an
   unrelated file's content to the original title, defeating the entire
   point of rel_path being an unambiguous key. **Fixed:** the PARA-subdir
   guess now only runs for a genuine legacy bare stem that never had a
   directory component; an explicit-but-missing rel_path returns `None`
   instead of guessing elsewhere. Regression test:
   `test_missing_explicit_rel_path_does_not_fall_back_to_wrong_para_dir`.

### Additional finding after re-verification (same class as #1 above, not from Codex)

While re-checking the schema-version fix, a symmetric gap was found: the
fingerprint salts on TF-IDF value SHAPE, but not on **backend
availability**. A corpus indexed while ChromaDB was unavailable
(`backend="tf"`), with the corpus then unchanged when Chroma later becomes
available, would still match the saved fingerprint — `rebuild_index()`
returns early, the Chroma collection stays permanently empty, and
`semantic_search_paths()`'s Chroma branch (pre-existing behavior, not
introduced by this PR: it always returns after querying Chroma, with no
fallback to TF-IDF just because Chroma is empty) silently returns nothing
until an unrelated file edit forces a real rebuild. **Fixed:** `backend`
is now also salted into `_corpus_fingerprint()`'s hash, alongside the
schema version. Regression test: `test_backend_becoming_available_forces_rebuild`.

### Floor-Ceiling Interval (Step 4a)

Not applicable to PR-2, for the same reason as PR-1: this is a binary
correctness property (a file either is or isn't opened via the correct
rel_path key; two entries either do or don't collide), not a continuous
ranking metric with room to move between a null-model floor and a
privileged-access ceiling. Deferred to PR-4/PR-5 where it is load-bearing.

## Next (PR-2)

Commit PR-2, push, open PR, dispatch isolated-worktree reviewer, wait CI +
Codex bot comments, merge. Then continue to PR-3 (atomic, reported rebuild,
fixes 0.4).

---

## PR-3 — atomic, reported rebuild (fixes 0.4)

### Verdict

- [x] PROMOTE — claim holds; merge to main

### Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | PASS — stale-entry deletion, both backends independently |
| Negative control | PASS — 1-of-3 partial failure leaves the other 2 correctly indexed |
| No-collapse tests | 4/4 PASS |
| Full test suite | pending (running at time of writing this section) |
| ruff / mypy / architecture gates | clean |

### Design notes

- `rebuild_index()` no longer calls `index_wiki_entry()` in its main loop —
  the per-file parse/tokenize/embed logic is now inline, building an
  in-memory batch (`tf_batch` dict, or `chroma_ids`/`chroma_docs`/
  `chroma_embeds`/`chroma_metas` lists) across the whole file set BEFORE any
  write happens. `index_wiki_entry()` itself is unchanged and still used
  directly by ~15 existing unit tests (kept for that reason, not because
  production still calls it — grep-confirmed zero other production callers
  after this PR).
- **TF-IDF backend:** the whole `tf_batch` dict is written in ONE
  `_save_tfidf_index()` call (atomic tmp+`os.replace()`, unchanged from
  earlier PRs). Because `tf_batch` only ever contains rel_paths that were
  present AND successfully parsed in the CURRENT run, any rel_path from the
  previous index that isn't in `tf_batch` is a stale entry by construction
  — no separate "diff and delete" step needed, the atomic replace itself
  is the deletion. `deleted` is computed for reporting only (comparing the
  old loaded index's keys against the new batch's keys), not used to decide
  what to write.
- **Chroma backend:** batch `upsert()` first, then `collection.get()` to
  fetch existing ids, compute `stale_ids = existing_ids - set(chroma_ids)`,
  and `collection.delete(ids=stale_ids)` only after the upsert call
  returns without raising — matching the TZ's explicit ordering requirement
  ("delete only fires after the upsert succeeds").
- **Fail-open extended to the write step itself** (not just per-file
  parsing, which was already fail-open before this PR): the Chroma
  upsert/get/delete sequence and the TF-IDF lock-acquire/save sequence are
  now wrapped so a write-side failure (Chroma API error, TF-IDF lock
  timeout) is caught, logged to stderr, and treated the same as a
  per-file failure for the purpose of deciding whether to save the
  fingerprint (`write_ok` flag, ANDed with `failed == 0`) — a write that
  never actually landed must not be recorded as "corpus is up to date."
- **Concurrency lock** around the TF-IDF batch's read-then-replace, matching
  the lock `index_wiki_entry()` already used — closes a theoretical race
  where a batch replace could clobber (or be clobbered by) a concurrent
  single-entry write. No production caller triggers this today (see above),
  so this is defense-in-depth, documented as such in `claim.md`.
- **Hygiene:** `_get_chroma_collection()` was being called twice per
  `rebuild_index()` invocation (once to decide `backend`, once again for the
  actual write) — now called once and reused, avoiding constructing a second
  `PersistentClient` needlessly.
- **The TZ's named "false comment" fix item** (`vector_store.py:356`,
  "Reset TF-IDF index... ChromaDB handles upsert natively") no longer
  exists in the current file — grep-confirmed zero matches before starting
  this PR. It was presumably already gone by the time PR-1/PR-2's own
  rewrites of this function landed. Noted here rather than silently
  skipped, per this session's own discipline about items that turn out
  moot when reached.

### Skeptic Concerns (Step 8a)

An isolated-worktree `reviewer` agent (context-blind, working only from the
diff and this PR's own commit) was dispatched against PR-3's pull request
before merge. It found and reproduced two real correctness bugs and one
cosmetic-only observability gap, all verified independently before fixing:

1. **P0, confirmed and fixed:** `write_ok` was set `True` unconditionally
   in the write step, even when the batch was EMPTY because every file in
   a non-empty corpus failed to parse/embed this run (a total transient
   failure, e.g. an embedder hiccup — the files themselves were untouched
   on disk). This wiped a previously-good, fully populated index/collection
   down to empty, with `deleted` falsely reporting the wipe as legitimate
   cleanup. Reproduced with a tool BEFORE fixing: 2 real entries indexed,
   then a run where every file's TF computation raised → index went from
   `['a.md','b.md']` to `[]`, reported as `indexed=0, deleted=2`. **Fixed:**
   a `total_failure = len(files) > 0 and count == 0` check now skips the
   write entirely (existing index/collection left untouched) rather than
   writing an empty batch — an empty batch is only ever written when the
   corpus is genuinely empty (`len(files) == 0`). Regression test:
   `test_total_failure_does_not_wipe_existing_index`.
2. **P1, confirmed and fixed:** in the Chroma branch, `write_ok = True` was
   set right after a successful `upsert()`, BEFORE the
   `get()`/`delete()` stale-cleanup step — a failure isolated to that step
   was masked (caught by the same outer `except`, but `write_ok` was
   already `True`), so the fingerprint got saved anyway and the stale
   entry was permanently stranded (the next call would see an unchanged
   fingerprint and never retry the deletion). **Fixed:** `write_ok = True`
   now only happens after the delete step also completes without raising.
   Regression test: `test_chroma_delete_failure_does_not_falsely_mark_write_ok`.
3. **P2, cosmetic only, documented not fixed:** the TF-IDF `deleted` count
   can be inflated if a PRIOR run failed partway through a schema/backend
   transition (PR-2's fingerprint salts), leaving unrelated legacy-schema
   debris in `old_index` alongside genuinely-deleted-file entries — both
   get counted as "deleted." The actual replace is still correct either
   way; only the reported number can overcount. Left as a documented
   caveat (comment added at the `deleted` computation) rather than a fix,
   per the reviewer's own severity assessment (no data-loss consequence).

The reviewer hit its own internal iteration cap after delivering these
findings with reproductions and explicitly declined to propose or attempt
a fix itself (correctly staying in reviewer scope) — all three findings
were independently re-verified with fresh tool reproductions in this
session before any fix was applied, per this repo's own
`audit-verification-gate.md` discipline (agent's [VERIFIED] = this
session's [INFERRED] until independently re-checked).

### Two more findings from an externally-pasted review, both verified and fixed

The user pasted a second, independent external review after the isolated
reviewer's findings above were already fixed and pushed. Two of its
technical claims were verified with fresh tool reproductions (a third
claim about a specific CI "run number" did not correspond to anything
observed and was treated as noise, per this session's established
discipline of not accepting unverifiable specifics at face value):

4. **Confirmed and fixed:** `rebuild_index()` decided `backend` once,
   based only on Chroma collection availability — unlike
   `index_wiki_entry()` (still used elsewhere), which already falls
   through to TF-IDF per-call when the embedder model fails to load even
   though a Chroma collection exists. Reproduced with a tool: Chroma
   "available" (a real collection object) but embedder unavailable made
   every file fail with `backend="chroma"` locked in — the whole corpus
   went permanently unindexed instead of using the zero-dependency TF-IDF
   path. **Fixed:** `backend` now requires BOTH collection AND embedder to
   be available before choosing "chroma"; otherwise falls back to "tf" for
   the whole run, matching `index_wiki_entry()`'s existing per-call
   semantics. Regression test:
   `test_chroma_available_but_embedder_unavailable_falls_back_to_tf`.
5. **Confirmed and fixed:** `RebuildReport.indexed` reflected `count`
   (files successfully *parsed and prepared* this run), not whether the
   batch write actually *landed*. Reproduced with a tool: a TF-IDF save
   failure (e.g. disk full, retry-exhausted `os.replace()`) left
   `indexed=2, failed=0` in the report while the on-disk index was
   completely empty. **Fixed:** when the new-data write itself fails
   (`data_written=False`, and it wasn't the already-handled total-failure
   case), `count` is reclassified into `failed` before building the
   report. This required splitting the single `write_ok` flag into
   `data_written` (did the new data get written — governs the indexed/
   failed reclassification) and `cleanup_ok` (did the separate Chroma
   stale-deletion step also succeed — `write_ok = data_written and
   cleanup_ok` still gates the fingerprint save) — a naive "reclassify on
   `not write_ok`" would have wrongly marked a successfully-indexed file as
   failed whenever only the unrelated cleanup step failed, which the
   existing `test_chroma_delete_failure_does_not_falsely_mark_write_ok`
   test caught immediately when first attempted. Regression test:
   `test_write_failure_reclassifies_indexed_as_failed`.

Both were independently reproduced with tools before fixing, not accepted
on the external review's word alone — same discipline applied to every
other finding in this PR.

### Floor-Ceiling Interval (Step 4a)

Not applicable, same reasoning as PR-1/PR-2: binary correctness properties
(a stale entry either is or isn't removed; a partial failure either does or
doesn't corrupt the surviving entries), not a continuous ranking metric.

## Next (PR-3)

Commit PR-3, push, open PR, dispatch isolated-worktree reviewer, wait CI +
Codex bot comments, merge. Then continue to PR-4 (real TF-IDF as a
full-corpus-only operation, fixes 0.5).

---

## PR-4 — real corpus-wide TF-IDF, not TF-only (fixes 0.5)

### Verdict

- [x] PROMOTE — claim holds; merge to main

### Evidence Summary

| Check | Result |
|-------|--------|
| Positive control | PASS — rare term outranks common term under real, smoothed IDF |
| Negative control | PASS — same scenario, pure TF gives the opposite (correct) ordering |
| No-collapse tests | 4/4 PASS |
| Full test suite (post-redesign) | 3057 passed, 1 pre-existing unrelated failure (`test_check_global_hooks.py` hardcoded-path test), 3 skipped, 2 xfailed |
| ruff / mypy / architecture gates | clean |
| CI (PR #336, pre-redesign) | RED — 3 failed (caught the un-smoothed-IDF bug exactly, see Round 2 below), 3054 passed |

### Design deviation from the TZ, stated explicitly

The TZ's own draft schema nests `format_version`/`corpus_fingerprint`/
`idf`/`documents` inside a single JSON object at `tf_index.json`'s root.
Implemented instead: `idf` lives in its own sidecar file
(`idf_weights.json`), following the exact same pattern PR-1 already
established for the corpus fingerprint (`corpus_fingerprint.txt`) —
specifically to avoid the class of bug a Codex review caught on PR #332
(a root-level key inside `tf_index.json` gets misread by
`_load_tfidf_index()`/`_cosine()` as a malformed document vector).
`tf_index.json` itself keeps its existing flat
`{rel_path: {"title","vector"}}` shape, completely unchanged in structure
— only the stored `"vector"` values are now real TF-IDF instead of plain
TF. This delivers the identical observable behavior (real corpus-wide IDF
applied consistently to both documents and queries) without rewriting
`_load_tfidf_index()`/`_save_tfidf_index()` to understand a wrapper shape,
which would have touched roughly 30 existing tests asserting on the
current flat shape for no functional gain. Same pattern as PR-2's
documented `WikiRef`-signature deviation — chosen for lower blast radius,
not disagreement with the TZ's design goal.

**Explicitly deferred, not silently dropped:** the TZ also describes
retiring PR-1's separate `corpus_fingerprint.txt` sidecar into this same
new schema file ("one source of truth instead of two"). This PR does NOT
do that — the two sidecars (`corpus_fingerprint.txt`, now joined by
`idf_weights.json`) remain separate files. This is a real, stated
follow-on tidy-up in the TZ, not the falsifiable core claim of PR-4 (real
corpus-wide IDF actually being computed and used), and consolidating three
independent sidecar files' read/write logic together is a larger, separate
refactor with its own risk surface. Recorded here as a known, intentional
gap for a future PR rather than silently completed or silently skipped.

### A real bug found and fixed while implementing (before it reached other tests)

`semantic_search_paths()`'s TF-IDF branch initially applied
`_apply_idf(query_vec, _load_idf())` unconditionally. Since `_apply_idf()`
maps any term absent from the `idf` dict to weight 0 (by design, for
genuine out-of-vocabulary terms), an EMPTY or MISSING idf sidecar — which
happens whenever no `rebuild_index()` has run yet under this schema, or a
document was written via the low-level `index_wiki_entry()` path directly
(which stays plain-TF by design and never writes an idf sidecar, per the
TZ's own explicit decision not to give it an `idf` parameter) — would zero
out EVERY query term, collapsing the query vector to `{}` and returning no
results even for documents that would otherwise match under plain TF. This
would have broken roughly 15 pre-existing unit tests that call
`index_wiki_entry()` directly and then `semantic_search()`/
`semantic_search_paths()` without ever calling `rebuild_index()`. Caught
by running the existing test suite before writing any new PR-4 tests, not
by an external or agent review. **Fixed:** IDF weighting is now only
applied when the sidecar is non-empty; an empty/missing sidecar falls back
to plain-TF comparison, matching the exact pre-PR-4 behavior. Regression
test: `test_empty_idf_sidecar_falls_back_to_plain_tf`.

### Skeptic Concerns (Step 8a)

**This session's Evaluator-Optimizer Guard hook capped further reviewer
dispatches after 3 consecutive non-LGTM cycles (PR-1, PR-2, PR-3 reviews
all found and fixed real bugs).** Per `CLAUDE.md`'s own hard rule ("Never
run a 4th cycle silently"), no isolated-worktree reviewer agent was
dispatched against this PR — the gate stays closed until an LGTM verdict
resets the counter or a new session starts. This was escalated to the
user directly rather than bypassed.

**Round 1 — self-review, using the exact 4-point checklist that would
have gone to the reviewer agent** (IDF formula correctness, all-zero-
vector handling, conditional query-side IDF application, two-file write
atomicity), verified with hand-traced reproductions:

1. IDF formula (`log(n/df)`): hand-verified on a 3-document example and
   judged correct — `df==n` giving exactly 0 was read as "a term in every
   document is maximally uninformative, not a bug to smooth away."
   **This verdict was WRONG and was overturned in Round 2 below** — the
   self-review's 3-document example happened not to exercise the case
   that actually breaks (every term in a corpus shared by every document,
   e.g. any single-document corpus), so the formula's real failure mode
   went undetected until CI ran a broader corpus.
2. All-zero-vector handling: a single-document corpus makes every term's
   idf exactly 0 under the un-smoothed formula, `_l2_normalize` correctly
   returns `{}` rather than dividing by zero — but the *premise* that this
   is intentional and correct was itself wrong (see Round 2): a lone
   document does have distinctive terms relative to an empty background,
   it is the formula, not the normalization, that was at fault.
3. Two-file write atomicity: the two-file write (`tf_index.json` +
   `idf_weights.json`) is not atomic across files. **First fix (Round 1,
   since superseded by Round 2's redesign):** if the documents save
   succeeded but the idf sidecar save then failed, the sidecar was
   explicitly deleted rather than left stale. This was verified
   insufficient in Round 2 — see below.
4. Two-file non-atomicity was, at the time, otherwise accepted as a known,
   narrow, self-healing risk — this framing survives Round 2, but only
   because Round 2's redesign changed WHAT the two files jointly describe
   (see below), not because the original risk assessment was correct as
   stated.

**Round 2 — externally-pasted review (2026-09-03/04, in Russian),
verified claim-by-claim with tools before acting on any of it, per
`audit-verification-gate.md`:**

1. **Claim: un-smoothed IDF (`log(n/df)`) breaks any corpus where a term
   appears in every document — trivially every term in a single-document
   corpus, zeroing the whole document vector and making it permanently
   unsearchable.** Verified TWO independent ways: (a) reproduced locally
   by forcing the TF-IDF backend and indexing a single document — search
   for a term from that document returned `[]`; (b) fetched PR #336's
   ACTUAL CI job log directly (`gh api
   repos/sergeeey/Claude-cod-top-2026/actions/jobs/100768664892/logs`) and
   confirmed byte-for-byte the review's cited failures:
   `test_indexed_entries_searchable`, `test_indexes_para_subdirectories`,
   `test_para_routed_note_is_indexed_and_searchable` all failed with
   `assert '<title>' in []`, summary `3 failed, 3054 passed, 2 skipped, 2
   xfailed`. **CONFIRMED-REAL, both independently.** **Fixed:** smoothed
   IDF, `log((n+1)/(df+1)) + 1.0` — identical to scikit-learn's
   `TfidfVectorizer(smooth_idf=True)` default. Floors every in-vocabulary
   term's idf at 1.0 (never exactly 0) while preserving rare-beats-common
   relative ordering. This directly overturns Round 1 point 1 above: the
   3-document self-review example was too narrow to surface the failure.
2. **Claim: the Round-1 "delete the sidecar on partial failure" fix does
   not actually fix the atomicity bug, because it only protects a FUTURE
   query — it does nothing to undo IDF weighting already baked into
   documents from the earlier successful write.** Verified by
   reproduction: after a successful IDF-baked write followed by a
   simulated sidecar-save failure (sidecar deleted per the Round-1 fix),
   previously-written documents on disk were STILL IDF-weighted from the
   original successful run, while a fresh query fell back to plain TF —
   scoring a genuinely irrelevant document (matching only the common
   term) at 0.949 and the actually-relevant document (matching the rare
   term) at 0.316, i.e. the wrong document ranked first. **CONFIRMED-
   REAL.** **Fixed via redesign, not a smaller patch:** the root cause is
   architectural — baking IDF into stored documents at index time
   requires the sidecar and the document index to always agree, across
   two separate file writes, which cannot be enforced. Documents are now
   ALWAYS stored as plain TF (never reweighted at index time); IDF is
   applied fresh, symmetrically, to BOTH the query and each document
   inside `semantic_search_paths()` at search time. The two sides can now
   never desynchronize: either both get real IDF (sidecar present/non-
   empty) or both stay plain TF (sidecar absent/empty), never a mix. This
   makes Round 1's "delete sidecar on partial failure" fix a mild
   staleness mitigation rather than the correctness-critical fix it was
   originally framed as — kept anyway as a strictly-safer no-cost choice
   (see `_delete_idf_sidecar()`'s updated docstring).
3. **Claim: a residual PR-3-era stale-entry-deletion edge case — a file
   that exists but fails to process this run might have its OLD, valid
   entry wrongly deleted alongside genuinely-removed files, rather than
   preserved until a successful re-processing.** Investigated (not raised
   by Round 1, not previously verified): reproduced with a tool. A file
   that exists on disk but throws during parsing THIS run is excluded
   from `tf_batch`; `_save_tfidf_index(tf_batch)` replaces the entire
   on-disk index, so that file's previously-valid entry is genuinely
   deleted (temporarily unsearchable) — the review's claim is TRUE as
   far as it goes. But the STRONGER, more dangerous reading ("permanently
   lost until an unrelated future corpus change happens to trigger a
   retry") is FALSE: `rebuild_index()` only saves the corpus fingerprint
   when `failed == 0` for that run (pre-existing PR-1/PR-3 logic,
   unrelated to this PR), so a run with ANY parse failure never caches
   its fingerprint — the very next `rebuild_index()` call (fired on every
   Stop event, per `hooks/CLAUDE.md`) unconditionally retries every file,
   independent of whether the corpus changed. Reproduced end-to-end: a
   file made to fail parsing lost its entry on that run, then was
   automatically restored on the very next call with no corpus change in
   between. **Verdict: real but self-healing, and already a deliberate,
   reasoned tradeoff documented in `rebuild_index()`'s own comment
   ("since this run could not verify its content is still valid") — not
   a new defect, and out of scope for PR-4 (IDF correctness). No code
   change made for this claim.**

**Honest limitation of this substitution:** a self-review by the same
session that wrote the code is weaker than an independent, context-blind
reviewer agent (this repo's own `falsification-ladder.md` § Context
Asymmetry Rule exists precisely because of this) — Round 1 concretely
demonstrated the limitation by reaching a wrong verdict (point 1) that an
externally-pasted review then caught. Round 2's claims were each
independently verified with tools before being acted on, per
`audit-verification-gate.md` ("agent's [VERIFIED] ≠ your [VERIFIED]") —
none of Round 2's substantive technical claims were accepted on the
review's prose alone.

### Floor-Ceiling Interval (Step 4a)

**Applicable here, unlike PR-1/2/3** — this is the first PR in this ladder
that changes a continuous RANKING metric (cosine similarity scores), not a
binary correctness property. A full QUANTITATIVE floor-ceiling measurement
(efficiency as a continuous score) is the TZ's own §5.3 gate, explicitly
scoped to PR-5 (semantic retrieval wired into production) — PR-4 is a
prerequisite for that gate to measure the RIGHT algorithm (per the TZ's
own reordering rationale: real IDF must land before the ranking gets
measured, or the gate's verdict wouldn't describe the shipped system).
This PR's own scope only warrants — and only claims — the qualitative
version below, not §5.3's quantitative one.

#### Floor (mechanism removed)

Pure TF (the IDF reweighting step disabled via monkeypatching `_apply_idf`
to a no-op). On the verified 51-document scenario
(`test_rare_term_outranks_common_term_under_real_idf`: 50 common-only
documents + 1 rare-term document, query ratio 2 "common" : 1
"raretermx"), pure TF ranks a document matching ONLY the corpus-common
term FIRST (0.80 cosine) — asserted explicitly in the test as the
required floor behavior, not assumed. **Updated post-redesign:** the
original scenario (3 documents, un-smoothed IDF, 4:1 query ratio) no
longer demonstrates the failure once IDF is smoothed (a 3-document
corpus's "common" idf floors at ~1.0 instead of hitting exactly 0, and a
4:1 ratio through the real `semantic_search_paths()` pipeline — which
also picks up the non-stopword "entry" shared by every document — no
longer flips). Re-derived by hand-sweeping corpus size and query ratio
against the exact document text the test writes (not an idealized
approximation), landing on 50 documents / 2:1 ratio as the smallest
configuration that still produces a genuine flip.

#### Ceiling (privileged access)

Real, smoothed corpus-wide IDF (the actual mechanism this PR ships, not a
privileged/oracle variant — there is no "better than real IDF" version to
grant privileged access to for this specific claim). On the same 51-
document scenario, real IDF ranks the document containing the rare,
distinctive term FIRST (0.63 vs. 0.39 cosine for the next-best
common-only document) — the correct ordering.

#### Efficiency

Qualitative, not a continuous score: floor = WRONG ordering (asserted),
ceiling = CORRECT ordering (asserted) on an identical input. The interval
has real headroom (floor ≠ ceiling on this input) and the shipped
mechanism reaches the ceiling exactly, not partway — efficiency = 1 in the
categorical sense (correct/incorrect), which is as much as this PR's scope
warrants. §5.3's continuous, whole-system efficiency measurement (observed
vs. a numeric floor and ceiling) is deferred to PR-5 by explicit design,
not by omission — see the TZ's own reordering rationale at the top of its
PR-4 section.

## Next (PR-4)

Commit PR-4, push, open PR, dispatch isolated-worktree reviewer, wait CI +
Codex bot comments, merge. Then continue to PR-5 (wire semantic retrieval
into the production path, with real HOT-tier scoring, gated by §5.3).
