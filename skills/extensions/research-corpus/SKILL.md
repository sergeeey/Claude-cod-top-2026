---
name: research-corpus
tokens: ~350
description: >
  Use when user wants to analyze a corpus of research papers, academic texts,
  or any document collection. Triggers: "corpus analysis", "analyze papers",
  "literature review", "research review", "analyze studies", "research mode",
  "/research", "погнали корпус", "анализ корпуса", "разбери статьи".
  Runs structured 10-step analysis chain with fact/inference/unknown taxonomy.
---

# Research Corpus Analyzer

Structured multi-step analysis system for academic and research corpora.
Separates fact / inference / unknown at every step to prevent hallucination.

## Universal Prefix

Prepend this to EVERY prompt in the chain:

```
Work only from the uploaded materials. Explicitly tag every claim:
- <fact> — directly confirmed in the corpus
- <inference> — reasonable conclusion from the corpus
- <unknown> — insufficient data to conclude

Rules:
1. Do not invent sources, authors, quotes, consensus, or gaps not in the corpus.
2. For each strong claim, state which works support it.
3. If the corpus cannot support a confident conclusion, say so explicitly.
4. Do not use external knowledge unless separately requested.
5. Do not summarise in generalities where you can show structure, contradiction, or limitation.
```

---

## Modes

### /research quick
Runs steps 1 → 6 → 10 only.
Use when: fast overview needed, corpus is small (< 5 papers), time-constrained.

### /research full
Runs the complete chain: **1 → 2 → 5 → 7 → 4 → 6 → 8 → 3 → 9 → 10**
Use when: serious research work, thesis support, deep literature review.

### /research mode:[N]
Runs a single step N (1–10) in isolation.
Use when: user already has prior steps done and needs one specific analysis.

### /research stop-check
Runs step 9 only. Use BEFORE committing to a full chain.
If corpus coverage < 60% or critical bias found → stop and report what to add.

---

## Step Definitions

### STEP 1 — Corpus Intake
```
I am going to upload [X] works on the topic [TOPIC].

Before answering any further questions, perform intake analysis only.

Task:
1. List each work:
   - Author(s), Year, Title
   - Type: empirical / review / meta-analysis / theoretical / case study
   - 1 main claim in 1 sentence
2. Group works into clusters by:
   - shared research question
   - shared assumptions
   - shared method
3. Flag separately:
   - works that directly contradict each other
   - works that repeat an existing line
   - works that are methodologically distinct
4. Do NOT make a final synthesis yet.
5. Build a "landscape map", not conclusions.

Output format:
A. Works table
B. Clusters
C. Explicit contradictions
D. What remains <unknown> without further analysis
```

### STEP 2 — Contradiction Finder
```
Across the entire uploaded corpus, find only cases where two or more works:
- reach incompatible conclusions,
- interpret the same effect differently,
- or give different answers to the same question.

For each contradiction:
1. The core conflict in 1 sentence
2. Position A
3. Position B
4. Which works represent each side
5. Possible reasons for divergence:
   - methodology
   - sample / data
   - period / context
   - definition of key terms
   - study design quality
6. Assessment:
   - <fact> what directly conflicts
   - <inference> why they likely diverge
   - <unknown> what is missing to resolve it

Do NOT call a difference in emphasis a contradiction.
Show only genuine semantic conflicts.

Format: table
Columns: [Question] [Work A] [Work B] [Conflict] [Likely cause] [Confidence]
```

### STEP 3 — Idea Genealogy
```
Select the 3 most central concepts in the uploaded corpus.

For each concept, reconstruct the intellectual lineage using only uploaded works:
1. Who introduces or earliest formulates the concept in this corpus
2. Who refines or develops it
3. Who critiques, limits, or contests it
4. Status of the concept within this corpus:
   - stable / contested / fragmented / unclear

Rules:
- Do not claim "who was first in history" unless provable from the corpus.
- If the corpus does not cover early history, mark as <unknown>.
- Do not substitute citability for importance unless directly visible in the texts.

Output format per concept:
A. Brief definition
B. Development line
C. Who strengthened / who challenged
D. Current status in corpus
E. What remains <unknown>
```

### STEP 4 — Research Gap Scanner
```
From the uploaded corpus, identify the 5 most well-grounded research gaps.

Define "gap" strictly:
- question is clearly important to the topic, AND
- the corpus leaves it unanswered, partially answered, contradictory,
  or answered by methodology too weak to be reliable.

For each gap:
1. Question formulation
2. Why this is a real gap, not just a new idea
3. Which works came closest to answering it
4. What exactly they left unclosed
5. What type of research is likely needed next
6. Confidence: strong gap / plausible gap / weak/uncertain gap

Prohibited:
- writing "no one answered" when the corpus simply has little data
- inventing gaps for originality

Format: [Gap] [Why gap] [Closest works] [What unclosed] [What needed] [Confidence]
```

### STEP 5 — Methodology Audit
```
Compare the methodologies of all works in the corpus.

Group by type:
- theoretical / observational / survey / experimental /
  quasi-experimental / simulation / case study / review/meta-analytic

Then assess:
1. Which methodologies dominate
2. Which are underrepresented
3. Which provide the strongest basis for conclusions on this topic
4. Where methodology systematically constrains the field
5. Which corpus conclusions may be overrated due to weak design

Rules:
- Do not rate "stronger/weaker" abstractly — tie to the research question.
- If a work is methodologically weak, explain specifically why.
- Separate:
  <fact> what was used
  <inference> what this means for field quality
  <unknown> what cannot be assessed without external information

Output:
A. Per-work table
B. Methodological distribution picture
C. Main corpus limitations
D. What this changes in interpreting results
```

### STEP 6 — Master Synthesis (no filler)
```
Now, based on all prior analysis, produce a final synthesis of the corpus.

But:
- do not retell work by work
- do not produce a regular summary
- do not simulate consensus where none exists

Synthesis structure:
1. What looks most stable in the corpus (<fact>)
2. What conclusions look probable but not final (<inference>)
3. Where the main lines of dispute run
4. Which methodological limits prevent strong conclusions
5. The single main unresolved question remaining after reading the full corpus

Constraint:
- max 400 words
- no introductory filler
- every claim must be <fact>, <inference>, or <unknown>

Format: short paragraphs with <fact> / <inference> / <unknown> tags
```

### STEP 7 — Assumption Killer
```
List the key assumptions on which a significant portion of the uploaded corpus rests,
but which are:
- rarely tested directly
- often taken as background
- or insufficiently justified

For each assumption:
1. Clear formulation
2. Which works rely on it most heavily
3. Are there attempts to test it within the corpus
4. What changes for the whole field if the assumption is false
5. How central it is:
   - central / important but local / peripheral

Rules:
- Do not confuse an assumption with a popular idea.
- Show the hidden load-bearing structure of reasoning.

Format: [Assumption] [Who relies on it] [Tested?] [What collapses if false] [Importance]
```

### STEP 8 — Knowledge Map Builder
```
Build a structured knowledge map of the entire uploaded corpus.

Goal: not a retelling, but a compact diagram of the field.

Structure:
1. Central question or central claim of the field
2. 3–5 load-bearing pillars
3. 2–3 active contested zones
4. 1–2 boundary questions that remain open
5. 3 most foundational works from the corpus for a newcomer:
   - why exactly these
   - what is impossible to understand without them

Rules:
- Do not call a work "essential" unless justifiable by its role in the corpus.
- If the corpus itself is narrow, say so.
- All map elements must be derived from actually uploaded materials.

Format:
I. Central core
II. Load-bearing pillars
III. Contested zones
IV. Open boundaries
V. 3 entry works for newcomers
```

### STEP 9 — Corpus Boundary Check
```
Assess whether the uploaded corpus is sufficient for strong conclusions on this topic.

Answer:
1. Which parts of the topic are well covered
2. Which parts are weakly covered
3. Is there bias by:
   - era / period
   - geography
   - methodology
   - data type
   - school / research tradition
4. Which strong conclusions CANNOT be made due to corpus limitations

Output:
A. What the corpus allows claiming
B. What the corpus does not allow claiming
C. Which limitations are most dangerous

STOP SIGNAL: If coverage < 60% or critical bias found,
output: "⚠️ SYNTHESIS PREMATURE. Add to corpus: [specific list]"
and do not proceed to steps 6/8/10 without user confirmation.
```

### STEP 10 — Confidence Table
```
Compile a final table of all main conclusions from the corpus.

For each conclusion:
1. Conclusion formulation
2. Type: <fact> / <inference> / <unknown>
3. Which works support it
4. Are there serious objections within the corpus
5. Confidence level: high / medium / low
6. What would raise confidence

Format: strict table
Columns: [Conclusion] [Type] [Supporting works] [Objections] [Confidence] [To raise confidence]
```

---

## Execution Instructions for /research full

When user runs `/research full` or equivalent:

1. Confirm which files are loaded as the corpus.
2. Run STEP 9 (stop-check) first silently.
   - If stop signal triggers → surface warning and pause.
   - If OK → proceed.
3. Run steps in order: **1 → 2 → 5 → 7 → 4 → 6 → 8 → 3 → 9 → 10**
   - Insert STEP 3 after STEP 2 if intellectual genealogy is relevant.
4. Between each step, output:
   `✓ Step [N] complete. Proceeding to step [M]...`
5. After STEP 10, output final summary:
   ```
   ═══ CORPUS ANALYSIS COMPLETE ═══
   Steps completed: [list]
   Total claims: X fact / Y inference / Z unknown
   Main finding: [1 sentence]
   Biggest gap: [1 sentence]
   Confidence ceiling: [high/medium/low] — why
   ```

## Execution Instructions for /research quick

Run: **1 → 6 → 10** only.
Output compact versions of each step.
Flag at end: "Quick mode — steps 2,3,4,5,7,8,9 skipped."

---

## Gotchas

- [2026-04] Do not skip STEP 9 — running synthesis on a weak corpus produces confident-looking garbage.
- [2026-04] STEP 2 must come before STEP 5 — contradiction detection needs raw material before methodology audit interprets it.
- [2026-04] STEP 7 (assumptions) is most often skipped but highest value — do not omit in full mode.
- [2026-04] If corpus has < 3 works, full mode is overkill — default to quick mode and tell user.
- [2026-04] <fact> tags require a specific work citation, not "the corpus suggests".
