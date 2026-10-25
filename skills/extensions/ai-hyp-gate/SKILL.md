---
name: ai-hyp-gate
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-06-02]
  7-шаговый orchestrator проверки AI-сгенерированной гипотезы ДО включения в research design.
  Цепочка skills: source trace → novelty → falsifiability → independent expert →
  causal structure → pilot → documentation. На каждом шаге явный KILL signal —
  если шаг fail, цепочка останавливается и сообщает причину. Защита от:
  hallucinated sources, pseudo-novelty, unfalsifiable claims, confirmation bias,
  causal/correlational confusion, premature scaling, irreproducibility.
  Базируется на rules/falsification-ladder.md + rules/estimand-ops.md + existing skills
  (поиск литературы, /sci-evidence, /hypothesis-arbiter, Agent(skeptic) с Context Asymmetry).
  Triggers: /ai-hyp-gate, /hyp-gate, /verify-hypothesis, "проверь гипотезу через gate",
  "AI hypothesis gate", "7-шаговая проверка гипотезы", "kill-gate гипотезы",
  "верифицируй гипотезу до эксперимента", "ai hypothesis verification".
  НЕ для: уже подтверждённых гипотез в active experiments (→ /scientific-research),
  одной идеи без AI generation (→ /skeptic Mode 1), code review (→ /code-review).
effort: medium
tokens: ~1500
triggers: [/ai-hyp-gate, /hyp-gate, /verify-hypothesis, "проверь гипотезу через gate", "AI hypothesis gate", "7-шаговая проверка гипотезы", "kill-gate гипотезы", "верифицируй гипотезу до эксперимента", "ai hypothesis verification"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : ai-hyp-gate
TL;DR  : 7-шаговый kill-gate для AI-сгенерированных гипотез до research design
Вызов  : /ai-hyp-gate, "проверь гипотезу", "kill-gate гипотезы"
НЕ для : Уже подтверждённых гипотез, ручных идей без AI, code review
-->

# /ai-hyp-gate — AI Hypothesis Verification Gate

## Purpose

Цепочка 7 проверок которая работает как защитный gate **ДО** того как гипотеза попадёт в research design / эксперимент.

**Принцип:** дешёвые проверки (Шаг 1-3, минуты) идут ПЕРЕД дорогими (Шаг 4-6, часы-дни). Каждый шаг имеет explicit kill signal — если fail, останавливаемся и сообщаем причину.

**Базируется на:**
- `rules/falsification-ladder.md` (FL Steps 0, 3, 6)
- `rules/estimand-ops.md` (L0 gate)
- `Agent(skeptic)` с Context Asymmetry HARD RULE
- Existing skills: поиск литературы, `/sci-evidence`, `/hypothesis-arbiter`

## Hard Rules

- MUST complete все 7 шагов ИЛИ explicit fail с указанием шага
- MUST stop при первом kill signal — не пытаться "обойти" failed step
- MUST output decision document — markdown report недостаточен, нужен `decision.md` с verdict
- Каждый шаг = отдельный sub-process (изолированный контекст)
- Token budget: ~30-50 turns на полный gate
- Default mode: **read-only audit** — не запускаем эксперимент сами

## Input Contract

Принимает на вход:
1. **Гипотеза** в одном предложении (что должно быть истиной)
2. **Источник** — кто сгенерировал (Claude / ChatGPT / Gemini / комбинация)
3. **Целевой эксперимент** — куда планируется включить (project / experiment ID)
4. **Domain** — биомед / физика / ML / экономика / другое

Если что-то не указано — спросить **до** начала Step 1.

## 7-Step Protocol

### Step 1 — Source Trace (Трассировка источника)

**Вопрос:** существует ли реальная первичная публикация для каждого fact-claim в гипотезе?

**Actions:**
1. Извлечь все **specific factual claims** из гипотезы (имена, числа, механизмы, ссылки)
2. Для каждого claim:
   - `Agent(explorer, prompt="Find primary source for: <claim>")` ИЛИ
   - поиск литературы запрос с конкретными keywords
   - Если AI указал DOI/PMID/arXiv ID — verify через WebFetch
3. Mark каждый claim:
   - `[VERIFIED-REAL]` — primary source confirmed (URL/DOI)
   - `[INFERRED]` — derivable из verified facts
   - `[UNVERIFIED]` — claim не найден в literature

**KILL signal:**
> ≥1 claim helper-pivotal для гипотезы со статусом `[UNVERIFIED]` после reasonable search (≥3 поисковых запросов).
>
> **Verdict:** HALLUCINATED SOURCE → STOP. Report which claim, what was searched, что не найдено.

**Output:** `source_register.md` (claim / status / source URL / search trail)

---

### Step 2 — Novelty Check (Проверка новизны)

**Вопрос:** не является ли гипотеза перефразировкой известного результата?

**Actions:**
1. Семантический поиск:
   - поиск литературы с paraphrased queries (3-5 вариаций)
   - Semantic Scholar для recent (последние 5 лет)
   - Google Scholar для broader coverage
2. Pre-work check (наш собственный архив):
   - поиск по своему архиву прошлых экспериментов и отклонённых гипотез (например, `grep -ri "<keyword>" experiments/ null_results/ parked/`), если такой архив есть
3. Если есть похожие найденные работы — оценить delta:
   - Same method, same population, same outcome → **pseudonovelty**
   - Same idea, different domain → **transfer hypothesis** (может быть valid)
   - Same outcome, different mechanism → **alternative explanation** (valid)

**KILL signal:**
> Найдена published работа с same idea AND same approach AND comparable rigor.
>
> **Verdict:** PSEUDONOVELTY → STOP. Report найденный source, объяснить почему gate kill.

**Если в null_results/ или parked/:**
> **Verdict:** REJECTED PREVIOUSLY → STOP. Прочитать decision.md из archive прежде чем re-attempt.

**Output:** `novelty_check.md` (queries / matches / delta analysis / verdict)

---

### Step 3 — Falsifiability (Критерий Поппера)

**Вопрос:** какой конкретный экспериментальный результат опровергнет гипотезу?

**Actions:**
1. Применить FL Step 0 из `rules/falsification-ladder.md`:
   - Write the claim ОДНИМ предложением
   - Identify измеримые quantities
   - Write kill criterion в виде: "Если <metric> <comparator> <threshold>, гипотеза опровергнута"
2. Write Micro 4-liner:
   ```
   Question type: [ ] descriptive  [ ] predictive  [ ] causal
   Claim: <one sentence>
   Check: <how to verify in 7 days>
   What this does NOT mean: <boundary>
   ```
3. Sanity check:
   - Kill criterion должен быть в **abstract numbers**, не в "если эксперимент не подтвердит"
   - Threshold должен быть указан **ДО** эксперимента
   - Должно быть possible получить kill result — иначе гипотеза unfalsifiable

**KILL signal:**
> Невозможно сформулировать concrete numeric kill criterion. ИЛИ kill criterion = "expert judgment" / "if it doesn't work" / "if results are inconsistent" (subjective).
>
> **Verdict:** NOT FALSIFIABLE → STOP. Гипотеза не научна в текущей формулировке.

**Output:** `claim.md` (FL Step 0 артефакт + Micro 4-liner)

---

### Step 4 — Independent Expert Review (с Context Asymmetry)

**Вопрос:** что говорит независимый skeptic не знакомый с историей вопроса?

**Actions:**
1. Подготовить минимальный input для skeptic:
   - `source_register.md` (Step 1 output)
   - `claim.md` (Step 3 output)
   - НИЧЕГО ИЗ session reasoning chain
2. Spawn skeptic с **Context Asymmetry HARD RULE** enforced:
   ```
   Agent(skeptic, prompt="
   Falsification test for claim: <claim.md content>
   Source register: <source_register.md>
   Task: Generate 3 test cases that would FALSIFY this claim.
   Specify exact commands or experiments.
   Report: CONFIRMED / FALSIFIED / NEEDS-REAL-DATA / WEAKENED.
   Do NOT consider how the hypothesis was generated. Only: does the claim hold?
   ")
   ```
3. Для biomed/clinical/engineering domains добавить domain-specific skeptic:
   - (опционально) отдельный domain-specific reviewer, если он есть в вашей установке

**KILL signal:**
> Skeptic verdict = `FALSIFIED` ИЛИ skeptic находит fundamental flaw в methodology.
>
> **Verdict:** SKEPTIC REJECTED → STOP. Report skeptic's reasoning + suggested falsification tests.

**WEAKEN signal:**
> Skeptic verdict = `WEAKENED` — гипотеза держится но с serious caveats.
>
> **Action:** добавить caveats в `claim.md`, NARROW scope гипотезы, продолжить с уменьшённым confidence.

**Output:** `skeptic_review.md` (skeptic's verdict + 3 falsification tests)

---

### Step 5 — Causal Structure (EstimandOps L0)

**Вопрос:** заявляет ли гипотеза причинность? Если да — обоснован ли механизм?

**Actions:**
1. Apply `rules/estimand-ops.md` L0 gate:
   - **Descriptive:** "What is X in population P?" → no causal interpretation
   - **Predictive:** "What will X be for new case?" → no causal interpretation
   - **Causal:** "What would change if we did A?" → требует causal layer
2. Если classification = causal:
   - Draw DAG (nodes + edges)
   - Check 4 identifiability assumptions:
     - **Consistency:** Y = Y^a when A=a
     - **Positivity:** P(A=a|L) > 0 для всех a и L в support
     - **Exchangeability:** Y^a ⊥ A | L (no unmeasured confounders)
     - **SUTVA:** no interference, no hidden treatment versions
   - Name identification strategy (randomization / IV / RD / DiD / g-formula / TMLE)
   - List unmeasured confounders
3. Check noncollapsibility: если outcome heterogeneous population, prefer risk difference (RD) или restricted mean survival time (RMST) over hazard ratio (HR) или odds ratio (OR)
4. LLM-specific check: **causal parrots warning** — LLMs systematically conflate correlation with causation. Re-read original claim — действительно ли он implies causation?

**KILL signal:**
> Заявлена causation НО:
> - Identification assumptions нарушены AND cannot be recovered by design ИЛИ
> - Нет DAG ИЛИ
> - Нет identification strategy named
>
> **Verdict:** UNIDENTIFIABLE CAUSAL CLAIM → STOP. Choices: redesign as descriptive ИЛИ change study design.

**DOWNGRADE signal:**
> Гипотеза заявляет причинность но evidence supports только correlation.
>
> **Action:** rewrite claim.md как associational, добавить "what this does NOT mean: causation".

**Output:** `estimand.md` (full canvas: population/intervention/comparator/endpoint/summary measure/MCID/ICE) + optional `dag.md`

---

### Step 6 — Pilot Experiment (Минимальный тест)

**Вопрос:** воспроизводится ли expected behavior на small real data перед полным запуском?

**Actions:**
1. Apply FL Standard Ladder Steps 3-6 из `rules/falsification-ladder.md`:
   - **Step 3:** Positive control (known-good input) → `controls.md`
   - **Step 4:** Negative control (known-bad input) → `controls.md`
   - **Step 5:** Define baseline (existing method или null model) → `baselines/<id>.json`
   - **Step 6:** Run minimal test → `metrics/run.json`
2. Pilot rules:
   - На REAL data (НЕ synthetic) — `[VERIFIED-REAL]` mandatory
   - Sample size минимум для statistical power detection effect ≥MCID
   - Pre-registered analysis plan (что считаем success ДО запуска)
3. Result classification (FL Step 8):
   - **PROMOTE** — success, full experiment justified
   - **REPEAT** — inconclusive, iterate с modifications
   - **REJECT** — pilot fail → kill gate
   - **ARCHIVE** — valid but deprioritized

**KILL signal:**
> Pilot не воспроизводит expected behavior на real data. ИЛИ negative control unexpectedly succeeds.
>
> **Verdict:** PILOT REJECTED → STOP. Это model boundary / data issue. Report что обнаружено, save в null_results/.

**SCOPE-REDUCE signal:**
> Pilot succeeds только на subset (specific population/condition).
>
> **Action:** narrow гипотезу до tested scope, добавить boundary conditions в caveats.md.

**Output:** `pilot_result.md` + `metrics/run.json` + `controls.md` + `baselines/<id>.json`

---

### Step 7 — Documentation & Audit Trail

**Вопрос:** есть ли воспроизводимый аудит всей цепочки?

**Actions:**
1. Создать experiment directory: `experiments/<YYYYMMDD-slug>/`
2. Зафиксировать:
   - **Original AI prompt** (с timestamp)
   - **AI model + version** (название модели и версия)
   - **Generation date**
   - Все 6 предыдущих outputs (`source_register.md`, `novelty_check.md`, `claim.md`, `skeptic_review.md`, `estimand.md`, `pilot_result.md`)
   - Final decision (`decision.md`)
3. Final decision template:
   ```markdown
   # Decision — <hypothesis slug>

   **Date:** YYYY-MM-DD
   **Question type:** descriptive / predictive / causal
   **AI source:** <model + version + prompt>

   ## Gate Results
   | Step | Verdict | Artifact |
   |---|---|---|
   | 1. Source trace | PASS / FAIL | source_register.md |
   | 2. Novelty | PASS / FAIL | novelty_check.md |
   | 3. Falsifiability | PASS / FAIL | claim.md |
   | 4. Skeptic | PASS / WEAKEN / FAIL | skeptic_review.md |
   | 5. Causal | PASS / DOWNGRADE / FAIL | estimand.md |
   | 6. Pilot | PROMOTE / REPEAT / REJECT | pilot_result.md |

   ## Final Decision
   PROMOTE TO RESEARCH DESIGN / REJECT / ARCHIVE

   ## Caveats
   <list any WEAKEN/DOWNGRADE/SCOPE-REDUCE signals from gate>

   ## What this does NOT mean
   <explicit boundaries>
   ```

**KILL signal:**
> Нет originating prompt OR нет AI model+version OR нет gate decisions.
>
> **Verdict:** UNAUDITABLE → STOP. Reproducibility broken at methodology level. Fix documentation before promoting.

**Output:** `experiments/<id>/decision.md` + all gate artifacts

---

## Flow Diagram

```
AI-generated hypothesis
    ↓
Step 1: Source trace ────[FAIL: HALLUCINATED]──> STOP
    ↓
Step 2: Novelty ────[FAIL: PSEUDONOVELTY]──> STOP
    ↓                  ────[REJECTED in null_results/]──> STOP
Step 3: Falsifiability ──[FAIL: NOT FALSIFIABLE]──> STOP
    ↓
Step 4: Skeptic ────[FAIL: FALSIFIED]──> STOP
    ↓        ────[WEAKEN: scope narrow]──> add caveats, continue
Step 5: Causal ────[FAIL: UNIDENTIFIABLE]──> STOP
    ↓        ────[DOWNGRADE: not causal]──> rewrite as associational, continue
Step 6: Pilot ────[FAIL: REJECTED]──> save null_results/, STOP
    ↓        ────[SCOPE-REDUCE: subset only]──> narrow, continue
Step 7: Documentation ──[FAIL: UNAUDITABLE]──> STOP
    ↓
PROMOTE TO RESEARCH DESIGN
```

## Final Report Format

```markdown
# /ai-hyp-gate Result — <hypothesis>

## Verdict: PROMOTE / REJECT / ARCHIVE

## Gate Trail
1. Source trace: PASS — verified N claims via lit search
2. Novelty: PASS — no prior work found in N queries
3. Falsifiability: PASS — kill criterion: <numeric threshold>
4. Skeptic: WEAKEN — added caveats X, Y
5. Causal: DOWNGRADE — rewritten as associational
6. Pilot: PROMOTE — pilot N=100 confirms effect at p<0.01
7. Documentation: PASS — audit trail in experiments/<id>/

## Artifacts
- experiments/<id>/source_register.md
- experiments/<id>/novelty_check.md
- experiments/<id>/claim.md
- experiments/<id>/skeptic_review.md
- experiments/<id>/estimand.md
- experiments/<id>/pilot_result.md
- experiments/<id>/decision.md

## Next Step
<one concrete action — design full experiment OR pivot OR archive>
```

## What NOT to produce

- ❌ Markdown отчёт без artifacts на disk
- ❌ "Probably falsifiable" — нужен concrete numeric kill criterion
- ❌ Skip skeptic step "потому что и так понятно" — Context Asymmetry mandatory
- ❌ Pilot на synthetic data, claim PROMOTE — `[VERIFIED-REAL]` required
- ❌ Skip Step 5 causal check для "не causal hypothesis" без явной classification

## Anti-loopholes

**EXPLOIT 1 — Skip source trace:** "AI is reliable, sources implied".
**Fix:** Mandatory verification. Если AI не указал sources, generate **specific** claims и search для каждого.

**EXPLOIT 2 — Fake novelty:** "I haven't seen it" = novel.
**Fix:** 3+ search queries обязательны. Pre-work check в null_results/ обязателен.

**EXPLOIT 3 — Soft kill criterion:** "если не работает".
**Fix:** Numeric threshold ОБЯЗАТЕЛЬНО. "Не работает" = not falsifiable.

**EXPLOIT 4 — Friendly skeptic:** дать skeptic полный контекст.
**Fix:** Context Asymmetry HARD RULE — skeptic видит только artifacts, не reasoning chain.

## Companion Skills (mapping на шаги)

| Step | Skill | Mode |
|---|---|---|
| 1 | поиск литературы | source verification |
| 1 | `Agent(verifier)` | claim verification |
| 2 | поиск литературы | semantic novelty search |
| 2 | аудит источников | если AI cited specific papers |
| 3 | `rules/falsification-ladder.md` | FL Step 0 spec |
| 4 | `Agent(skeptic)` | Context Asymmetry red team |
| 5 | `rules/estimand-ops.md` | L0 classification + DAG |
| 6 | `/scientific-research` | pilot + controls + baseline |
| 6 | `/sci-evidence` BUILD | pilot design |
| 7 | `rules/falsification-ladder.md` | FL Steps 8-11 documentation |

## Reference

- `rules/falsification-ladder.md` — FL protocol (Step 0 → Step 11)
- `rules/estimand-ops.md` — L0 gate + causal layer
- `rules/audit-verification-gate.md` — verification thresholds
- `agents/skeptic.md` — Context Asymmetry HARD RULE
- `experiments/_template/` — directory skeleton

## Final Notes

**Default mode:** read-only audit — выдаёт verdict + artifacts, НЕ запускает реальный эксперимент сам.

**Implementation:** если PROMOTE verdict → user явно запускает следующий шаг через `/scientific-research` или `Agent(builder)`. Gate сам **не** scales до full experiment.

**Time budget:** typical full gate = 30-90 минут (Steps 1-5 быстро, Step 6 pilot занимает основное время).
