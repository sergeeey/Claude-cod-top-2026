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

### Step 2.5: Relative Recall against a benchmark set (quantifies "enough searching")

Before concluding, pre-specify **3–5 papers that MUST be found** if the search is
sensitive — known-adjacent work identified in Step 1 or 1.5. Then report:

```
relative_recall = (benchmark papers actually returned) / (benchmark papers pre-specified)
```

Recall **< 1.0 → the search is not sensitive enough to support a "novel" verdict.**
Fix the queries and re-run. This converts "feels unexplored" into a number.

### Step 3: Make Decision

- **Not Novel**: any screener found significantly overlapping work
- **Novel**: BOTH screeners returned nothing overlapping, AND relative recall = 1.0
- **RECALL-FAILURE** (a third outcome, not a form of "novel"): **nothing close was
  found at all.** An idea worth pursuing always has adjacent literature. Zero close
  hits means the vocabulary is wrong, not that the niche is empty. Return to
  Step 1.5 — do **not** report this as novelty.

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
    "benchmark_returned": 3,
    "score": 1.0
  },
  "justification": "...",
  "most_similar_papers": [
    {"title": "...", "year": 2024, "overlap": "...", "found_by": "S2"}
  ],
  "differentiation": "Our idea differs because..."
}
```

`decision: "novel"` is **invalid** unless `screeners.independent = true`,
both screeners returned zero overlap, and `relative_recall.score = 1.0`.

## Rules

- **Two independent screeners, always.** One agent running many rounds is
  single-reviewer screening (13% miss rate) regardless of round count.
- **≥3 vocabularies** named in Step 1.5 before the first query is issued.
- **Round count is not evidence of sensitivity — relative recall is.** The old
  "minimum 3 rounds" rule is retired: 3 rounds in one vocabulary failed three times
  in one session (2026-09-01) while feeling thorough.
- **Zero close hits ⇒ `recall_failure`, never `novel`.** Real ideas have neighbours.
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

## Related Skills
- See also: [related-work-writing](../related-work-writing/)
- `/hd-mavp-router` — calls this as the final step of its `negative_space` run_mode
- `/negative-space-miner` — Stage 8 delegates its mandatory Novelty Check here; without delegation the status caps at `closely related`
