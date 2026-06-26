<!-- BSV — Brief Skill View | поиск: BSV
Скил   : paper-assembly
TL;DR  : Сквозной пайплайн сборки статьи от результатов до PDF + Submission Gate
Вызов  : /paper-assembly, сборка статьи, assemble paper, full paper pipeline
НЕ для : Одного раздела статьи (→ /paper-revision), поиска литературы (→ /lit-search)
-->

---
name: paper-assembly
description: >
  Сквозной пайплайн сборки научной статьи. Фазы: Literature → Plan → Code → Experiments →
  Figures → Tables → Writing → Citations → Formatting → Compilation → Review → Submission Gate.
  Каждая фаза питается выходом предыдущей. Checkpointing между фазами. Submission Gate обязателен
  перед любой внешней публикацией (4 проверки).
  Triggers: /paper-assembly, сборка статьи, assemble paper, full paper pipeline, end-to-end writing,
  собрать статью, пайплайн статьи.
  [STATUS: active] [CONFIDENCE: high] [VERSION: 1.1.0]
allowed-tools: Read, Grep, Glob, Bash, Agent, WebSearch
version: "1.1.0"
---

# /paper-assembly — Сквозной пайплайн статьи

> **Принцип:** все числа в тексте должны трассироваться до лога эксперимента.
> Нельзя пропускать фазы — каждая зависит от выходов предыдущей.

```
Результаты (данные)
  ↓
[Feasibility Gate]
  ↓
Phase 1:  Literature      → knowledge base, BibTeX
  ↓ knowledge питает →
Phase 2:  Planning        → структура + task list
  ↓ план питает →
Phase 3:  Code            → training/eval pipeline
  ↓ код питает →
Phase 4:  Experiments     → results JSON/CSV
  ↓ результаты питают →
Phase 5:  Figures         → PNG фигуры
  ↓ фигуры питают →
Phase 6:  Tables          → LaTeX таблицы
  ↓ фигуры + таблицы питают →
Phase 7:  Writing         → main.tex sections
  ↓ текст питает →
Phase 8:  Citations       → references.bib выверен
  ↓ текст + bib питают →
Phase 9:  Formatting      → LaTeX отформатирован
  ↓ всё питает →
Phase 10: Compilation     → PDF
  ↓ PDF питает →
Phase 11: Review          → оценки качества
  ↓ оценки питают →
[Submission Gate]         ← 4 обязательных проверки
  ↓
Submission
```

---

## Feasibility Gate

Перед стартом:

```
1. Есть реальные результаты экспериментов?
   → НЕТ: запусти /research-pipeline сначала, paper-assembly — последний шаг

2. Есть paper directory с минимальной структурой?
   → НЕТ: создай paper/ с подпапками experiments/, figures/, tables/, sections/

3. Все числа в тексте смогут трассироваться до experiment log?
   → НЕТ: не начинай writing пока нет полных результатов
```

**Проверить текущий статус:**
```bash
# [OPTIONAL] python ~/.claude/skills/paper-assembly/scripts/assembly_checker.py --dir paper/ --verbose
# Если скрипт недоступен — вручную: ls paper/ и отметь какие фазы завершены
```

---

## Checkpoint формат

Сохранять после каждой фазы в `paper/checkpoint.json`:

```json
{
  "project": "paper-name",
  "phases_completed": ["literature", "planning"],
  "current_phase": "code",
  "artifacts": {
    "literature": "knowledge_base.json",
    "plan": "research_plan.json",
    "code": null,
    "results": null,
    "figures": null,
    "tables": null,
    "draft": null,
    "bib": null,
    "pdf": null
  },
  "last_updated": "YYYY-MM-DDTHH:MM:SSZ"
}
```

При возобновлении: прочти `checkpoint.json` → начинай с `current_phase`.

---

## Phase 1 — Literature

**→ Делегируй `/literature-review`**

Выход: `knowledge_base.json` + `references.bib` (предварительный)

Quality gate перед переходом к Phase 2:
- [ ] ≥10 релевантных работ проанализированы
- [ ] Пробелы в литературе явно названы
- [ ] BibTeX ключи уникальны и корректны

**Выход Phase 1 → питает Phase 2:** список пробелов + ключевые работы для Related Work.

---

## Phase 2 — Planning

Структура статьи + task list на основе knowledge base.

```markdown
## Paper Structure
- Title: [рабочий заголовок]
- Contribution: [1-3 конкретных вклада, не "мы предлагаем"]
- Sections: Introduction / Related Work / Method / Experiments / Results / Discussion / Conclusion
- Target venue: [конференция / журнал + дедлайн]
- Page limit: [N страниц]
```

**Выход Phase 2 → питает Phase 3:** детальный план каждой секции + список экспериментов.

---

## Phase 3 — Code

**→ Делегируй `/experiment-code`**

Выход: воспроизводимый pipeline в `experiments/`

Quality gate:
- [ ] Код запускается с нуля (`python run.py --config config.yaml`)
- [ ] Random seed зафиксирован
- [ ] Все зависимости в `requirements.txt`

**Выход Phase 3 → питает Phase 4:** готовый pipeline для запуска экспериментов.

---

## Phase 4 — Experiments

Запуск и сбор результатов.

```bash
# Зафиксировать все результаты в JSON
python run.py --config config.yaml --output results/run_YYYYMMDD.json

# Baseline обязателен для сравнения
python run.py --baseline --output results/baseline_YYYYMMDD.json
```

Quality gate:
- [ ] Позитивный control прошёл
- [ ] Негативный control прошёл
- [ ] Результаты воспроизводятся при повторном запуске (seed зафиксирован)
- [ ] Все числа сохранены в `results/*.json` — НЕ в голове и не в блокноте

**Выход Phase 4 → питает Phase 5 и 6:** `results/*.json` — единственный источник истины.

---

## Phase 5 — Figures

**→ Делегируй `/figure-generation`**

Все фигуры генерировать из `results/*.json` — не вручную:

```python
# Правило: каждая фигура = один script
# figures/plot_main_result.py → figures/main_result.pdf
import json
results = json.load(open("results/run_YYYYMMDD.json"))
# ... plotting code
```

Quality gate:
- [ ] Каждая фигура генерируется скриптом из results/
- [ ] Фигуры читаемы в grayscale (для печати)
- [ ] Подписи осей + units везде

**Выход Phase 5 → питает Phase 7:** `figures/*.pdf` готовы к `\includegraphics`.

---

## Phase 6 — Tables

**→ Делегируй `/table-generation`**

```python
# Каждая таблица = один script из results/
# tables/generate_main_table.py → tables/main_table.tex
```

Quality gate:
- [ ] Все числа трассируются до `results/*.json`
- [ ] LaTeX компилируется без ошибок
- [ ] Стандартное отклонение / confidence interval указаны

**Выход Phase 6 → питает Phase 7:** `tables/*.tex` готовы к `\input`.

---

## Phase 7 — Writing

**→ Делегируй `/paper-writing-section`** по секции

**Порядок написания (не интуитивный, но правильный):**
1. Experiments + Results (сначала — от реальных данных)
2. Method (что именно делали)
3. Related Work (в контексте уже написанного)
4. Introduction (последним — когда знаешь contribution)
5. Abstract (самым последним — выжимка из готового)

Quality gate:
- [ ] Каждое числовое утверждение ссылается на фигуру или таблицу
- [ ] Нет "наш метод лучше" без цифр
- [ ] Все `\cite{}` ключи существуют в .bib

**Выход Phase 7 → питает Phase 8:** черновик `main.tex`.

---

## Phase 8 — Citations

**→ Делегируй `/citation-management`**

```bash
# Проверить все \cite{} ключи
grep -oP '\\cite\{[^}]+\}' main.tex | sort -u > cited_keys.txt
grep -oP '^@\w+\{[^,]+' references.bib | sed 's/@\w*{//' | sort -u > bib_keys.txt
comm -23 cited_keys.txt bib_keys.txt  # Должно быть пусто
```

Quality gate:
- [ ] Все `\cite{}` ключи есть в `.bib`
- [ ] Нет неиспользуемых записей в `.bib`
- [ ] DOI у всех записей где возможно

---

## Phase 9 — Formatting

**→ Делегируй `/latex-formatting`**

Quality gate:
- [ ] Компилируется без ошибок и warnings
- [ ] Соответствует template venue (margins, font size, page limit)
- [ ] Все `\includegraphics` файлы существуют

---

## Phase 10 — Compilation

```bash
# Полная компиляция
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex

# Проверить PDF
pdfinfo main.pdf  # Должен показать корректные метаданные
```

Quality gate:
- [ ] PDF открывается
- [ ] Все ссылки кликабельны
- [ ] Page count в лимите venue

---

## Phase 11 — Review

**→ Делегируй `/self-review`**

```markdown
Checklist:
- [ ] Abstract точно описывает contribution
- [ ] Introduction имеет чёткий gap → our solution → contribution
- [ ] Все цифры в тексте = цифры на фигурах/таблицах (Text↔Figures check)
- [ ] Limitations секция честная, не "будущая работа"
- [ ] Conclusion не содержит новых claim-ов
```

**Text↔Figures consistency check (обязателен):**
```bash
# Извлечь все числа из текста
grep -oP '\d+\.?\d*%|\d+\.?\d*x' main.tex | sort > text_numbers.txt
# Сравнить с числами из results/
# ANY mismatch = STOP и разобраться
```

---

## Submission Gate (ОБЯЗАТЕЛЕН перед любой внешней публикацией)

Из `rules/integrity.md` — все 4 проверки, нельзя пропустить ни одну:

```
1. ✅ Skeptic Agent Run
   → Agent(skeptic, "Pre-submission red team: найди слабейшее место в claims")
   → Должен вернуть PASS

2. ✅ Pre-Submission Checklist
   → ~/.claude/memory/templates/Pre-Submission Checklist Template.md
   → Минимум 9 проверок, каждая [VERIFIED] с file:line

3. ✅ Text↔Figures Consistency Check
   → Все числа в тексте = числа в фигурах/таблицах
   → ANY mismatch = STOP

4. ✅ 24-hour Cooling Off
   → Между "готово" и submit ≥ 24 часа
   → Re-run skeptic после охлаждения
```

**Если хоть одна проверка FAILED → НЕ ПОДАВАТЬ. No exceptions.**

---

## Связанные скиллы

| Phase | Скилл |
|---|---|
| 1 | `/literature-review`, `/lit-search` |
| 3 | `/experiment-code` |
| 4 | `/experiment-design`, `/ab-test` |
| 5 | `/figure-generation` |
| 6 | `/table-generation` |
| 7 | `/paper-writing-section` |
| 8 | `/citation-management` |
| 9 | `/latex-formatting` |
| 10 | `/paper-compilation` |
| 11 | `/self-review` |
| Gate | `skeptic`, `integrity.md` (rules) |
| Upstream | `/research-pipeline` (поставляет результаты) |
