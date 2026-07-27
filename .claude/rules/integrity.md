# Integrity Protocol — project addendum

> **This is an ADDENDUM, not a full copy.** The canonical, general Integrity Protocol
> lives in `rules/integrity.md` (installed to `~/.claude/rules/integrity.md` and treated as
> canonical by `hooks/evidence_guard.py`). That file loads alongside this one — do not
> duplicate it here. This file holds ONLY the project/personal-workflow additions that
> extend the canonical: vault routing and the detailed submission-gate protocol.

## Vault Routing (lightweight)

Перед substantive ответом по знакомым domains (ARCHCODE, portfolio, hypotheses, submission):
- Проверить auto-memory (это уже автоматически в session start)
- Прочитать 1-2 релевантных vault файла если факт нужен
- Mark `[VERIFIED-REAL]` / `[MEMORY]` / `[UNKNOWN]` для каждой claim
- Не fabricate "вероятно в vault X" — либо read, либо ASK

**Не делать:** routing pipeline для тривиальных вопросов. Anti-overengineering.


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

