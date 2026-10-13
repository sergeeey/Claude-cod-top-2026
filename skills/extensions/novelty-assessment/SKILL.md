---
name: novelty-assessment
description: Assess research idea novelty through systematic literature search. DUAL independent screening in at least two vocabularies (own phrasing + adjacent-field terms), scored by relative recall against a pre-specified benchmark set. Three outcomes — novel / not_novel / recall_failure — because "nothing found" is usually a wrong-vocabulary search, not an empty niche. Use before committing to a research direction.
Triggers: /novelty-assessment, оценка новизны, is this novel, новизна идеи, prior art check.
argument-hint: [idea]
---

# Novelty Assessment

Rigorously assess whether a research idea is novel through systematic literature search.

## Input

- `$0` — Research idea description, title, or JSON file

## Scripts

### Automated novelty check (external script optional — not shipped by this repo)
If you have a `novelty_check.py`-style script installed:
```bash
python novelty_check.py \
  --idea "Your research idea description" \
  --max-rounds 10 --output novelty_report.json
```
Otherwise, run the multi-round search-evaluate loop described in the Workflow
below manually, using WebSearch/WebFetch for each round.

### Literature search (external script optional — not shipped by this repo)
If you have a `search_semantic_scholar.py`-style script installed:
```bash
python search_semantic_scholar.py \
  --query "relevant search query" --max-results 10
```
Otherwise, use `WebFetch https://api.semanticscholar.org/graph/v1/paper/search?query=...`.

## References

- Assessment prompts and criteria: `~/.claude/skills/novelty-assessment/references/assessment-prompts.md`

## Workflow

### Step 1: Understand the Idea
- Identify the core contribution
- List the key technical components
- Determine the research area and subfield

### Step 1.5: Vocabulary Translation (MANDATORY — do this before any search)

**Searching in your own words is the dominant failure mode of this skill.** The
adjacent field names the same thing differently, so a clean result proves the
*term* is free, not the *question*.

Name **at least three** adjacent fields and write how each would phrase this idea:

```
Own phrasing:      "<the idea in your words>"
Field A (<name>):  "<their term>"
Field B (<name>):  "<their term>"
Field C (<name>):  "<their term>"
```

Standard candidate fields: information retrieval · meta-research / scientometrics ·
software engineering (field studies) · human factors / automation · clinical decision
support · safety science · the idea's own home discipline.

Worked failures this rule comes from — all real, all one session:
`"retraction counts understate overturning"` missed Ioannidis's
*"Persistence of contradicted claims"* · `"falsification protocol with a skeptic role"`
missed *"Abyss Falsifier"* · `"cross-individual benchmark"` missed *"modality gap"*.

Then **pre-specify the benchmark set now, before Step 2 launches**: 3–5 known-adjacent
papers that a sensitive search MUST return. Steps 2.3 and 2.5 use it; it is fixed here so
it cannot be chosen after seeing what the screeners found.

### Step 2: DUAL SCREENING (two independent screeners — not one, not sequential)

**Why two.** Measured in systematic-review methodology: single-reviewer screening
misses **13%** of relevant studies; dual screening misses **3%**. A single agent
running N rounds is single-reviewer screening no matter how large N is.

Launch **two screeners in parallel**, and keep them blind to each other:

| screener | gets | must NOT get |
|---|---|---|
| **S1** | the idea in the author's own phrasing | S2's queries or results |
| **S2** | the idea **restated in the adjacent-field vocabulary** from Step 1.5, with the author's phrasing withheld | S1's queries or results |

Independence is the whole mechanism — if S2 sees S1's queries it anchors on them and
the 13%→3% gain is lost. Reconcile only after both have returned.

Each screener runs its own multi-round loop (query → search → review top-10 →
assess overlap). Disagreement between S1 and S2 is **signal, not noise**: it means
one vocabulary reaches literature the other does not, and both sets count.

### Step 2.3: Citation chase — reach what neither vocabulary names

Keyword screening (S1, S2) finds papers that *use your words*. Papers that share your
*ancestry* but not your words are reachable only through the citation graph. Run the chase
**after both screeners have returned** (so it cannot anchor either of them) and **before**
scoring recall.

1. **Seeds (3).** The 3 papers closest to the idea (topic and method) that either screener
   returned — overlapping or not — at most 2 per screener, ties broken by the more recent
   paper. If neither screener returned any paper, use the benchmark set from Step 1.5.
2. **Resolve each seed to an OpenAlex ID:** `https://api.openalex.org/works/doi:<DOI>`
   (or `.../works?search=<exact title>`, then check the title matches). A seed that does
   not resolve is logged `resolved: false` (unknown, not zero citations) and **replaced by
   the next-closest paper**. If the pool runs out before every seed slot is resolved, the
   chase is incomplete (item 6).
3. **Channels per seed** — OpenAlex `works` filters with `&per-page=25`; read up to 4 pages
   (100 results) per pass, and record `total` and `read` for each channel:

   | channel | filter | returns |
   |---|---|---|
   | forward, most cited | `cites:<W-id>` + `&sort=cited_by_count:desc` | works that **cite** the seed (incoming) |
   | forward, newest (first page only) | `cites:<W-id>` + `&sort=publication_date:desc` | the latest citing works — new competitors have few citations and drop out of the most-cited pass |
   | backward | `cited_by:<W-id>` | works the seed **cites** — its references (outgoing) |
   | related | `related_to:<W-id>` | OpenAlex's algorithmic neighbours |

   **Direction:** `cites` is incoming, `cited_by` is outgoing. Checked against the OpenAlex
   docs and a live control on 2026-09-26 (Hijmans 2012, `W2168997286`): `cites` returned 646
   vs the record's `cited_by_count` 649; `cited_by` returned 50 of the record's 54
   `referenced_works` (4 references do not resolve, so coverage is partial); `related_to`
   returned 10 = `related_works`.
4. **Screen** every work not already *seen* (seen = the union of the S1 and S2 result
   lists) by title **and** abstract — a title-only screen does not count. If OpenAlex has
   no abstract for a work, open its landing page or treat the work as borderline.
   "Overlapping" means the paper already claims or demonstrates the idea's core
   contribution, or a trivial variant of it (the Step 3 "Not Novel" test); a borderline
   paper counts as overlapping and is named in the justification. Record it with
   `found_by: "citation_chase"`.
5. **Score the misses.** A *close* paper (overlapping, or one that belongs in the benchmark
   set) that the chase surfaced and neither S1 nor S2 returned is a recall miss for both:
   list it in `missed_by_both_screeners` and add it to the benchmark set as a post-hoc
   addition (`benchmark_added_post_hoc`). It stays in the denominator for the rest of the
   assessment, and "returned" means returned by S1 or S2 — never by the chase — so
   `relative_recall` stays below 1.0 until a re-run of Step 2 returns it.
6. **Completion and coverage.** The chase is complete only if every seed slot resolved and
   every channel of every seed returned a non-error response. Completion is not
   sufficiency: report `read`/`total` per channel, and if any forward channel has more than
   100 works (so it was truncated) the decision's `confidence` cannot be `high`. An
   incomplete chase never supports `novel`: fix and retry once; if it is still incomplete,
   report `recall_failure` (Step 3) with `citation_chase.skipped_reason` saying what could
   not complete.
7. **Re-runs.** Any re-run of Step 2 (Step 2.5's fix-and-re-run) repeats this chase: the
   seeds and the *seen* set change.

Limits: OpenAlex coverage of very recent papers, preprints and older non-English work is
partial, so an empty chase from a resolved seed is weak evidence, not proof. **In the one
case tested, the chase did not cross fields.** Measured on this skill's own worked example
(2026-09-26, without a chase in the original run): a one-hop chase from a regulatory-genomics
seed (Fulco 2019, `W2991283206`; forward 1 207 works, the 100 most-cited read; backward
89/89; related 10/10; the newest-first page was not part of that run) did **not** reach the
ecology paper (Hijmans 2012) that only S2 found. A chase from an S2-vocabulary seed, which
starts inside the other field, is **untested**. Cost: about 11 requests per seed (1 resolve,
up to 4 forward most-cited, 1 forward newest, up to 4 backward, 1 related), about 33 for 3
seeds, plus screening the new titles and abstracts (up to ~700 works at full pages).

### Step 2.5: Relative Recall against a benchmark set (quantifies "enough searching")

Score the benchmark set **pre-specified at the end of Step 1.5** — 3–5 papers that MUST
be found if the search is sensitive (papers added post hoc by Step 2.3 count as not
returned). Then report:

```
relative_recall = (benchmark papers returned by S1 or S2) / (pre-specified + added post hoc by Step 2.3)
```

Recall **< 1.0 → the search is not sensitive enough to support a "novel" verdict.**
Fix the queries and re-run (at most two re-runs; if recall is still below 1.0, report
`recall_failure`). This converts "feels unexplored" into a number.

### Step 3: Make Decision

- **Not Novel**: any screener **or the citation chase (Step 2.3)** found significantly overlapping work
- **Novel**: BOTH screeners returned nothing overlapping, AND relative recall = 1.0, AND the citation chase is **complete** (Step 2.3 item 6) and found nothing overlapping
- **RECALL-FAILURE** (a third outcome, not a form of "novel"): **nothing close was
  found at all.** An idea worth pursuing always has adjacent literature. Zero close
  hits means the vocabulary is wrong, not that the niche is empty. Return to
  Step 1.5 — do **not** report this as novelty. The same outcome is reported when the
  search cannot be shown sensitive for another reason: recall still below 1.0 after two
  re-runs, or an incomplete citation chase. Say which in `justification`, then fix the
  vocabulary (Step 1.5) or the infrastructure problem (the chase) before any verdict.
  **Precedence:** `not_novel` wins whenever any overlap was found; `recall_failure` applies
  only when none was. A `recall_failure` carries `confidence: low`.

### Step 4: Position the Idea
If novel, identify:
- Most similar existing papers (for Related Work)
- How the idea differs from each
- The specific gap this idea fills

## Harsh Critic Persona

```
Be a harsh critic for novelty. Ensure there is a sufficient contribution
for a new conference or workshop paper. A trivial extension of existing
work is NOT novel. The idea must offer a meaningfully different approach,
formulation, or insight.
```

## Output Format

The block is a schema (`|` separates alternatives, `...` is a placeholder), not a parseable
instance.

```json
{
  "decision": "novel" | "not_novel" | "recall_failure",
  "confidence": "high" | "medium" | "low",
  "vocabularies_searched": ["own", "<field A>", "<field B>", "<field C>"],
  "screeners": {
    "S1_own_phrasing":      {"rounds": 4, "overlapping_found": 0},
    "S2_adjacent_vocab":    {"rounds": 4, "overlapping_found": 2},
    "independent": true,
    "agreed": false
  },
  "relative_recall": {
    "benchmark_prespecified": ["...", "...", "..."],
    "benchmark_added_post_hoc": [],
    "benchmark_returned": 3,
    "score": 1.0
  },
  "citation_chase": {
    "seed_source": "screeners" | "benchmark",
    "seeds": [{"title": "...", "openalex_id": "W...", "resolved": true,
               "channels": {"forward_most_cited": {"total": 1207, "read": 100},
                            "forward_newest": {"total": 1207, "read": 25},
                            "backward": {"total": 89, "read": 89},
                            "related": {"total": 10, "read": 10}}}],
    "new_candidates": 41,
    "new_overlapping": 1,
    "missed_by_both_screeners": ["<close paper>"],
    "skipped_reason": null
  },
  "justification": "...",
  "most_similar_papers": [
    {"title": "...", "year": 2024, "overlap": "...", "found_by": "S2"}
  ],
  "differentiation": "Our idea differs because..."
}
```

`decision: "novel"` is **invalid** unless `screeners.independent = true`,
both screeners returned zero overlap, `relative_recall.score = 1.0`, and the citation
chase is complete (Step 2.3 item 6: every seed slot resolved, every channel of every seed
returned without error, `skipped_reason = null`) and found nothing overlapping.
`skipped_reason` may only say why the chase could not complete; a non-null value always
blocks `novel`, and a truncated forward channel caps `confidence` below `high`.

## Rules

- **Two independent screeners, always.** One agent running many rounds is
  single-reviewer screening (13% miss rate) regardless of round count.
- **≥3 vocabularies** named in Step 1.5 before the first query is issued.
- **Round count is not evidence of sensitivity — relative recall is.** The old
  "minimum 3 rounds" rule is retired: 3 rounds in one vocabulary failed three times
  in one session (2026-09-01) while feeling thorough.
- **Zero close hits ⇒ `recall_failure`, never `novel`.** Real ideas have neighbours.
- **Keyword screening finds papers that share your words; the citation graph finds papers
  that share your ancestry.** Complete the chase (Step 2.3) before any `novel` verdict; an
  unresolved seed is logged, never skipped silently, and an incomplete chase never supports
  `novel`.
- A paper idea is NOT novel if it's a trivial extension
- Consider both methodology novelty AND application novelty
- Check for concurrent/recent arXiv submissions
- If the idea is a *method* rather than a *finding*, also search practitioner
  literature (library science, SE practice, clinical guidelines) — techniques are
  often long-standardised somewhere before they are "discovered" in a research
  context. The "two vocabularies" rule itself turned out to be standard MEDLINE
  practice (free-text + MeSH) after being written up as an insight.

## Worked example — the first real run (2026-09-01)

Read this if the dual-screening step feels like overhead. It is the run that
justifies the cost, and the screeners **disagreed**.

**Claim assessed:** in enhancer–gene prediction, a distance-only baseline's AUC is a
monotone function of the candidate-window half-width (measured 0.6725 → 0.8534 across
25→500 kb on one fixed dataset); therefore ΔAUC across papers is incomparable.

| screener | vocabulary | rounds | papers found | verdict |
|---|---|---|---|---|
| **S1** | own — regulatory genomics | 8 | 10 | `novel` ❌ |
| **S2** | ecology · virtual screening · recommenders · link prediction | 10 | 20+ | `not_novel` ✅ |

**S1 was not lazy.** Eight rounds, ten papers, honest `[UNKNOWN]` markers on what it
could not verify. It was thorough *inside one vocabulary* — which is exactly the
failure this procedure exists to catch. Thoroughness is not sensitivity.

**What only S2 could reach** (verified independently before acceptance):

> Hijmans, *Ecology* 93:679–688 (2012) · `10.1890/11-0826.1` · PMID 22624221 —
> **"spatial sorting bias"**. The null model uses *only geographic distance*; the fix
> (*pairwise distance sampling*, matching negatives' distance distribution to
> positives') drives its AUC to ≈0.5. Across 226 species the distance-only null beat
> MaxEnt for 45% and Bioclim for 67%. Shipped in CRAN as **`dismo::ssb()`**.

A library function for the phenomenon is the strongest possible "already known"
signal. The same effect is separately named *representativeness effect* (with `uAUC`
as its published remedy), *artificial enrichment* (DUD-E/MUV/LIT-PCBA), and
*sampler-dependent evaluation* (`arXiv:1912.02263`, `arXiv:2607.27861`).

**Procedure metrics that made the verdict trustworthy:**
- `relative_recall = 3/3 = 1.0` — every pre-specified must-find paper was returned,
  so `not_novel` rests on a sensitive search rather than on an empty result.
- A verdict prediction was recorded **before** the run ("occupied structurally,
  possibly free specifically") and matched the outcome — making the run falsifiable
  in both directions instead of retrospectively unsurprising.
- This run **predates Step 2.3**: it used two screeners and a recall benchmark only. See
  the Step 2.3 limits for what a one-hop chase from an S1-style seed would (not) have reached.

**Cost accounting, measured here rather than quoted:** S1 alone would have returned
`novel` after eight rounds, sending the work into head-on collision with ecology
literature from 2008–2012 — discovered at review, not before. The second screener
cost one parallel call. That is the 13%→3% gain, observed rather than cited.

**What survived** — note the shape, it is the usual one: not the discovery, but the
*transfer*. The correction has been standard in species-distribution modelling and
virtual screening for ~20 years and is **not applied in regulatory genomics**.
Positioning as "we discovered this" collides with prior work; positioning as "here is
the sweep, and here is a known remedy this field has not adopted" survives.

## Empirical basis for the dual-screening design

| claim | source |
|---|---|
| single-reviewer screening misses ~13% of relevant studies; dual screening ~3% | systematic-review screening methodology |
| 92.7% of search strategies in 137 systematic reviews contained errors; **78.1%** of those affected **recall**; commonest error = missing terms in **both** natural and controlled language | Salvador-Oliván, Marco-Cuenca, Arquero-Avilés, *JMLA* 2019 — `10.5195/jmla.2019.567`, PMID 31019390 |
| relative recall against a pre-specified benchmark set as the standard way to evaluate search-string sensitivity | `PMC12621535` |
| falsely-excluded studies are common enough to have their own recovery literature | `PMC9644550` |

**Rationale for Step 2.3 (an analogy, not measured evidence for this skill):** backward citation
searching is a MECIR standard for Cochrane systematic reviews and forward searching a
recommended adjunct (Briscoe et al. 2020, `PMC7079050`; Cochrane Handbook ch. 4). That
concerns reference lists in systematic reviews; the yield of the same idea for prior-art
search is untested here.

## Related Skills
- See also: [related-work-writing](../related-work-writing/)
- `/hd-mavp-router` — calls this as the final step of its `negative_space` run_mode
- `/negative-space-miner` — Stage 8 delegates its mandatory Novelty Check here; without delegation the status caps at `closely related`
