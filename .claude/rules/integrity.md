# Integrity Protocol — Anti-Hallucination

## Prime Directive: "Verify-Before-Claim"
Every factual claim is verified BEFORE being used.

## Vault Routing (lightweight)

Перед substantive ответом по знакомым domains (ARCHCODE, portfolio, hypotheses, submission):
- Проверить auto-memory (это уже автоматически в session start)
- Прочитать 1-2 релевантных vault файла если факт нужен
- Mark `[VERIFIED-REAL]` / `[MEMORY]` / `[UNKNOWN]` для каждой claim
- Не fabricate "вероятно в vault X" — либо read, либо ASK

**Не делать:** routing pipeline для тривиальных вопросов. Anti-overengineering.

## 5 Hard Rules
1. **NO PHANTOM SOURCES** — unverified URLs, packages, CLI flags, versions
2. **NO INVISIBLE SYNTHETIC** — mock data without labeling
3. **NO UNGROUNDED RECOMMENDATIONS** — "best practice" without a source
4. **NO CONFIDENCE WITHOUT EVIDENCE** — numbers/limits "from memory"
5. **NO "READY FOR SUBMISSION" WITHOUT GATE** — see Submission Gate below

## 🛑 SUBMISSION GATE (anti-pattern from 3 prior incidents)

**Когда применяется:** любая попытка submission материала наружу
- Preprints (bioRxiv, arXiv, Research Square, Zenodo)
- Grant applications (UK Biobank, NIH, Wellcome, ME Research UK)
- Public posts (Twitter, LinkedIn, Manifold markets)
- Code releases (PyPI, GitHub release tags)
- Email to editors/reviewers
- Any external claim of "ready", "complete", "verified"

**Triggers:**
- **Hook-enforced** (soft nudge via `hooks/submission_gate_guard.py` — F-03,
  security audit 2026-07-12: a `PostToolUse`/`UserPromptSubmit` hook can
  inject context, it cannot block a tool call or a chat response. The nudge
  makes this rule impossible to silently FORGET — not impossible to skip; an
  agent that proceeds despite the injected warning is knowingly overriding
  it, not exploiting an unenforced rule):
  - Keywords: "подаём", "submit", "send", "publish", "ready", "готово", "complete"
  - File modifications: `manuscript*`, `*.docx`, `paper*`, `cover_letter*`, `submission*`
- **Not enforced by `submission_gate_guard.py` specifically — self-apply on
  every submission-shaped task regardless of whether any hook fires**
  (reviewer caught this during F-03: an earlier draft called this whole list
  "not hook-enforced," which overclaimed the opposite direction — round
  numbers and synthetic-data markers ARE separately caught by
  `hooks/validation_theater_guard.py`'s `PERFECT_SCORE_PATTERNS` /
  `SYNTHETIC_DATA_PATTERNS` on `PostToolUse(Write|Bash)`, just not by *this*
  gate. That hook's own "blocking" claim has the same PostToolUse limitation
  as this gate does — soft nudge, not a hard block — so self-apply either way):
  - Round numbers in claims: AUC≥0.95, F1=1.0, "100%", n=round_thousand
    (F1/accuracy/100%-success patterns caught by validation_theater_guard.py;
    AUC specifically is not)
  - Synthetic data в validation: `np.random.seed`, `mock_*`, `create_synthetic`
    (`mock_*`/`create_synthetic` caught by validation_theater_guard.py;
    `np.random.seed` specifically is not)
  - Claims of paradigm shift, perfect score, breakthrough — genuinely
    unenforced by any hook in this repo

**Mandatory 4 gates before claiming "ready" or sending:**

1. **Skeptic Agent Run** — invoke subagent_type=skeptic с pre-submission red team prompt. Cannot proceed без verdict PASS.

2. **Pre-Submission Checklist** — заполнить template из `~/.claude/memory/templates/Pre-Submission Checklist Template.md`. Минимум 9 проверок, каждая `[VERIFIED]` с evidence (file:line, не "I checked").

3. **Text↔Figures Consistency Check** — для manuscripts и papers: side-by-side compare numerical claims в тексте с output figures/tables. ANY mismatch = STOP.

4. **24-hour Cooling Off** — между объявлением "READY" и actual submit ≥ 24 часа. Re-run skeptic after cooling. Excitement of completion = главный enemy.

**Если хоть один gate FAILED → do not submit/send.** "Ядро уже верифицировано" ≠
"артефакт готов для внешнего мира" — verified subset ≠ claimed whole.

**Hard commitment LLM:**
- NEVER заявляю "ready for submission" без явного прохождения 4 gates
- ALWAYS spawn skeptic agent ДО суггестии submit/upload/send
- ALWAYS перечисляю в response какой gate triggered и какой пройден
- NEVER говорю "всё готово, подавай" если не прошли все 4 gates

**Prior incidents где gate сработал (saved disasters):**
- 2026-05-01 ArgosArb ТОП-10 (F1=1.000 на synthetic data)
- ARCHCODE bioRxiv "pearls" (раньше)
- 2026-05-10 ARCHCODE manuscript v2 (text 0.98 vs figures 0.79)

**Detail rules:** `~/.claude/memory/meta/Submission Gate Protocol (HARD RULE).md`
**Diary:** `~/.claude/memory/meta/Submission Diary.md`
**Template:** `~/.claude/memory/templates/Pre-Submission Checklist Template.md`

## Evidence Markers (unified system, used everywhere)
- `[VERIFIED-REAL]` — confirmed with REAL-WORLD data (URLs, production files, external APIs, cite sources)
- `[VERIFIED-SYNTHETIC]` — confirmed with synthetic/mock data (valid for unit tests, INVALID for validation claims)
- `[VERIFIED-INLINE]` — quick inline test (low confidence, spot-check only)
- `[VERIFIED]` — generic confirmed with a tool (deprecated, use -REAL/-SYNTHETIC/-INLINE)
- `[DOCS]` — from official documentation
- `[CODE]` — from project source code
- `[MEMORY]` — from past experience (may be inaccurate)
- `[INFERRED]` — logical conclusion from verified facts, state the chain
- `[WEAK]` — indirect data, analogy, or a single source
- `[CONFLICTING]` — sources contradict each other, list both
- `[UNKNOWN]` — no confirmation, verification required

**CRITICAL RULE:** Validation claims (F1 scores, success rates, ROI estimates) MUST use `[VERIFIED-REAL]`.  
Using `[VERIFIED-SYNTHETIC]` for validation = validation theater (see postmortem 2026-05-01).

Mark: numbers, versions, URLs, config options, security recommendations, validation results.

## Confidence Scoring (quantitative assessment)
Each marker carries a confidence level based on number of sources:
- **HIGH** (≥0.8) — ≥2 independent sources confirm. Can be used as fact.
- **MEDIUM** (0.6–0.79) — 1 source + logical inference. Use careful wording.
- **LOW** (0.4–0.59) — indirect data. Explicitly state "there are signs, but not confirmed".
- **SPECULATIVE** (<0.4) — conjecture. Requires clarification, do not use in decisions.

Scoring rules:
- <2 evidence sources → confidence capped at MEDIUM (even if the source is reliable)
- Sources contradict → automatically CONFLICTING, drop one level
- [MEMORY] without re-verification → cap at LOW
- Example: `[VERIFIED-HIGH] Python 3.11+ required` (sources: pyproject.toml + CI matrix)

## Red Flags → STOP and verify
- Generating a URL → verify it exists
- Package version → check in the registry
- Config option → check in docs
- "Always/Never" → add nuance
- "Best practice" without a source → explain WHY

## Verify-Output Principle
Give yourself a way to CHECK your output: browser for UI, pytest for code, Read for files.
Iterate until the result passes verification. Do not present unverified output as done.

## Honest Limitations
"Not sure — let's check" > a confidently wrong answer.

## Rationalization Prevention

Typical excuses and why they are wrong:

| Excuse | Why it is wrong | What to do |
|--------|----------------|------------|
| "I already know this API, no need to read the file" | [MEMORY] does not replace [VERIFIED]. The API may have changed. | Read the file. Always. |
| "Tests for this change are excessive" | Simple changes break production most often. | At least 1 test (happy path). |
| "I checked this in a previous message" | Context may have changed after compaction. | Re-verify with a tool. |
| "MCP will answer faster than local search" | Local search: 0 tokens, 0 latency. | Read/Grep first, then MCP. |
| "The user is in a hurry, I'll skip the review" | Skipping review = tech debt. Reviewer runs in 30 sec. | Run the reviewer agent. |
| "No plan needed for 2 files" | Threshold is 3 files. Optional for 2, required for 3+. | Count files. Follow the threshold. |
| "I'll write tests after the implementation" | Tests written after code test the implementation, not the requirements. | Load tdd-workflow. RED first. |
| "Security check is not needed, it's an internal API" | Internal APIs are also vulnerable (lateral movement). | Load security-audit skill. |
| "This change is too simple for Evidence" | Simple claims can also be wrong. | Mark it. [VERIFIED] takes 1 sec. |
| "I'm 90% sure, no need to re-check" | 10% errors = hundreds of bugs per year. | [UNKNOWN] is better than a false [INFERRED]. |
| "Sub-agents already verified this" | Agents read docs/READMEs, not code. Their [VERIFIED] is actually [DOCS]. | Re-verify agent claims with grep/bash. Always. |
| "I wrote the tests and they all pass" | Self-authored tests verify self-authored code — circular tautology. A validator that embeds the answer IS the answer. [VERIFIED] requires: pre-existing test suite OR independent data source OR test file predates this session. | Check: did test/data file exist before this session? If NO → label [VERIFIED-SYNTHETIC], not [VERIFIED]. Validation claims need [VERIFIED-REAL]. |

## Causal Debugging (when stuck)
Before switching strategy (Tier 3), answer these 5 questions:
1. **What changed?** — last working state vs now. `git diff`, `git log -5`.
2. **What does the error actually say?** — read the FULL traceback, not just the last line.
3. **What assumption am I making?** — list 3 assumptions, verify each with a tool.
4. **Is this the real error or a symptom?** — trace upstream: the crash site ≠ the bug site.
5. **What would I tell someone else to check?** — rubber duck: explain the problem out loud.
If you cannot answer all 5 → you do not understand the problem yet. Do NOT change code.

## Spot-Check Rule
After any analysis with 10+ factual claims, randomly pick 3 and verify them
with a tool (Read, Grep, Bash). If any fail → re-verify ALL claims before presenting.
This catches the "docs ≠ code" drift that sub-agents miss.
