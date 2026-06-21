---
name: research-scout
description: "Поиск научных статей, экспериментов и неочевидных данных по теме проекта. 3 угла: фундаментальные (высокоцитируемые), свежие (< 2 лет), неочевидные (counterintuitive). ArXiv + bioRxiv MCP + Semantic Scholar + Papers With Code. Режим --anti-context: FVA-RAG, kill queries first."
triggers: [research-scout, найди статьи, найди исследования, scientific papers, arxiv, поиск статей, научный поиск, эксперименты, найди данные, anti-context, kill queries, refuting evidence]
tokens: ~500
type: directory
---

# Research Scout — Научная разведка

## Когда использовать
- Нужно обосновать архитектурное решение научными данными
- Ищешь state-of-the-art по технологии/алгоритму
- Хочешь найти что-то неожиданное — данные которые меняют подход
- Перед построением ML-модели — найти benchmark и baseline
- Проверить: "а вдруг это уже исследовали и не работает?"

## Как запустить

**"запусти research-scout"** — по контексту проекта  
**"запусти research-scout на [тема]"** — по конкретной теме  
**"запусти research-scout: найди counterintuitive данные про [X]"** — режим неочевидного  
**"запусти research-scout --anti-context [тема]"** — FVA-RAG: kill queries first  

---

## Режим: --anti-context (FVA-RAG)

**Что это:** инвертированный RAG. Сначала ищем опровергающие доказательства, потом подтверждающие.
Предотвращает confirmation bias: система не соберёт красивый стек поддерживающих статей и не пропустит ключевое опровержение.

**Когда использовать:**
- Перед финальной формулировкой гипотезы (FL Full-Ladder Step -3: Novelty Check)
- Когда уверенность в идее высокая (skeptic-trigger: 90%+ confidence)
- Аудит существующего claim перед публикацией / релизом

**Запустить:**
```
research-scout --anti-context "[тема / гипотеза]"
```

### Anti-context Шаг 1 — Kill Queries (всегда первый)

Сформируй 5 kill queries — запросы, нацеленные на уничтожение гипотезы:

```
WebSearch: "[тема] does not work OR fails 2023 2024 2025 2026"
WebSearch: "[тема] null result OR negative result 2023 2024 2025 2026"
WebSearch: "[тема] replication failure OR failed to replicate OR does not replicate"
WebSearch: "[тема] contradicts OR refutes OR disproves 2024 2025"
WebSearch: "[тема] criticism OR fundamental limitation OR why [X] is wrong"
```

Для каждого результата:
- Записать: title, year, key negative finding
- Пометить: `[KILL]` если опровергает гипотезу напрямую, `[WEAKEN]` если ограничивает scope

### Anti-context Шаг 2 — Null Results Registry

Проверить локальный реестр перед поиском в интернете:
```
grep -i "[ключевое слово]" null_results/INDEX.md
grep -i "[ключевое слово]" parked/INDEX.md
```

Если найдено: прочитать `decision.md` из того эксперимента. Новая попытка ОБЯЗАНА объяснить чем отличается от предыдущей провалившейся.

### Anti-context Шаг 3 — Confirmation Round (только после Kill Queries)

Стандартные запросы (Шаги 1-5 из основного алгоритма ниже) — но теперь каждый результат сопоставляется с kill findings. Найденные противоречия документируются явно.

### Anti-context Формат вывода

```markdown
## Kill Findings (что может уничтожить гипотезу)

1. **[Название статьи]** (год) — [URL]
   - **Тип:** [KILL] / [WEAKEN]
   - **Что опровергает:** [1 предложение]
   - **Scope ограничение:** [при каких условиях опровержение применимо]

## Null Results (внутренние)
- [found / not found in null_results/INDEX.md]

## Confirmation Evidence (после kill check)
[стандартный формат Топ-5 фундаментальных / свежих / неочевидных]

## Anti-context Verdict
- Kill findings: N
- Weakening findings: N
- Surviving claim scope: [что осталось после всех опровержений]
- Recommendation: PROCEED / REVISE_CLAIM / STOP_HYPOTHESIS
```

---

## Стандартный алгоритм (5 шагов)

### Шаг 1 — Контекст и ключевые слова

Прочитай `.claude/memory/activeContext.md`. Извлеки:
- **Домен**: что делает проект (AI agents, genomics, NLP, etc.)
- **Ключевые технологии**: 3-5 терминов на EN
- **Открытые вопросы**: что ещё не решено / PENDING

Если тема задана явно → используй её. Сформируй **3 поисковых запроса**:
- Запрос A: `[технология] [проблема]` — прямой
- Запрос B: `[технология] surprising OR unexpected OR counterintuitive` — неочевидный
- Запрос C: `[смежный домен] [та же проблема]` — кросс-доменный

---

### Шаг 2 — ArXiv (свежие preprints)

Для каждого запроса выполни WebFetch:

```
URL: https://export.arxiv.org/api/query?search_query=all:[QUERY]&sortBy=submittedDate&max_results=8&start=0
Prompt: "Extract: arxiv ID, title, abstract first 2 sentences, submission date. Return as list."
```

Примеры рабочих URL:
```
https://export.arxiv.org/api/query?search_query=all:attention+memory+decay&sortBy=submittedDate&max_results=8
https://export.arxiv.org/api/query?search_query=all:llm+agent+hooks+memory&sortBy=relevance&max_results=8
https://export.arxiv.org/api/query?search_query=all:knowledge+graph+retrieval+counterintuitive&sortBy=submittedDate&max_results=5
```

> ArXiv через WebFetch — протестировано, работает без rate limits.

---

### Шаг 3 — bioRxiv (биология, медицина, нейронауки)

Если проект касается биологии, геномики, нейронаук, медицины:

```
mcp__obsidian-vault или bioRxiv MCP:
search_preprints(query="[тема]", limit=5)
```

Если домен не биологический → пропусти, перейди к Шагу 4.

---

### Шаг 4 — WebSearch (неочевидные + Papers With Code)

**Для неочевидных данных:**
```
WebSearch: "[тема] negative results OR null results site:arxiv.org"
WebSearch: "[тема] surprising finding 2024 OR 2025 OR 2026"
WebSearch: "[тема] contradicts conventional wisdom research"
WebSearch: "[тема] replication failure OR does not replicate"
```

**Для имплементаций:**
```
WebSearch: "[тема] site:paperswithcode.com"
WebSearch: "[тема] benchmark state of the art 2025 2026"
```

**Для кросс-доменного:**
```
WebSearch: "[смежная область] [та же проблема] unexpected results"
```

---

### Шаг 5 — Скоринг и вывод

Для каждой статьи вычисли Score:

| Критерий | Баллы |
|----------|-------|
| Год >= 2025 | +3 |
| Год 2023-2024 | +2 |
| Содержит "surprising" / "contrary" / "unexpected" в abstract | +3 |
| Есть код на GitHub / Papers With Code | +2 |
| Высокое цитирование (если известно) | +2 |
| Кросс-доменная (другая область, та же проблема) | +2 |

---

### Формат вывода (стандартный режим)

```markdown
## Топ-5 фундаментальных (высокоцитируемые / классика)

1. **[Название статьи]** (год) — arXiv:XXXX / DOI
   - **Ключевой результат**: [1 предложение]
   - **Применить**: [как использовать в проекте]
   - **Код**: [ссылка или "нет"]

## Топ-5 свежих (< 2 лет)

1. **[Название]** (2025/2026)
   - **Ключевой результат**: [1 предложение]
   - **Почему важно**: [что меняет в текущем подходе]
   - **Код**: [ссылка или "нет"]

## Топ-5 неочевидных (counterintuitive / surprising)

1. **[Название]** (год)
   - **Общепринятое мнение**: [что все думали]
   - **Что обнаружили**: [неожиданный результат]
   - **Импликация для проекта**: [что менять]

## Главный инсайт сессии
> [1-2 предложения: самое важное что изменит подход к проекту]

## Следующий шаг
- [ ] Прочитать полностью: [название #1 из неочевидных]
- [ ] Реализовать: [конкретная идея из статьи]
- [ ] Проверить baseline: [что нужно измерить]
```

---

## Источники по домену

| Домен | Лучший источник |
|-------|----------------|
| ML / AI / NLP | ArXiv cs.LG, cs.AI, cs.CL |
| Биология / Геномика | bioRxiv MCP + PubMed |
| Нейронауки / Память | bioRxiv + ArXiv q-bio |
| Системы / Distributed | ArXiv cs.DC, cs.SY |
| Финансы / Экономика | SSRN (WebSearch) + ArXiv q-fin |
| Физика / Математика | ArXiv math, physics |
| Кросс-доменный | WebSearch + Semantic Scholar |

---

## Примеры запросов для неочевидного поиска

```
# Паттерн 1: Что НЕ работает (negative results)
"[технология] does not work when OR fails when site:arxiv.org"

# Паттерн 2: Противоречие консенсусу
"[технология] contrary to popular belief research 2024 2025"

# Паттерн 3: Репликация провалилась
"[метод] replication crisis OR failed to replicate"

# Паттерн 4: Кросс-домен инсайт
"[проблема в другой области] solution applied to [наш домен]"

# Паттерн 5: Эффект маленького датасета
"[ML метод] small dataset surprising performance 2025"
```

---

## Связка с другими скилами

- `--anti-context` → после kill queries → `запусти skeptic` с найденными [KILL] findings
- После research-scout → `запусти skeptic` — проверить применимость найденного
- После research-scout → `запусти codex-solver` — реализовать найденный алгоритм
- Ключевые статьи → `error-to-lesson` — сохранить инсайт в wiki
- `scientific-research` skill — для полного цикла исследования с kill criteria
- FL Step -3 (Novelty Check) — запускать `--anti-context` как часть ai-hyp-gate

---

## Gotchas

- [2026-04] Не пропускать Шаг 5 (скоринг) — синтез на слабом корпусе = уверенно выглядящий мусор
- [2026-04] ArXiv-поиск (Шаг 2) обязательно до скоринга (Шаг 5) — нельзя scoring без сырого материала
- [2026-06] `--anti-context`: kill queries ОБЯЗАТЕЛЬНО первыми — нельзя начинать с подтверждающего поиска
- [2026-06] `--anti-context`: если в null_results/INDEX.md есть совпадение — прочитать decision.md ПЕРЕД продолжением
