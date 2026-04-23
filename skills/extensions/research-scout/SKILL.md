---
name: research-scout
description: "Поиск научных статей, экспериментов и неочевидных данных по теме проекта. 3 угла: фундаментальные (высокоцитируемые), свежие (< 2 лет), неочевидные (counterintuitive). ArXiv + bioRxiv MCP + Semantic Scholar + Papers With Code."
triggers: [research-scout, найди статьи, найди исследования, scientific papers, arxiv, поиск статей, научный поиск, эксперименты, найди данные]
tokens: ~450
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

---

## Алгоритм (5 шагов)

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

> ✅ ArXiv через WebFetch — протестировано, работает без rate limits.

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
| Год ≥ 2025 | +3 |
| Год 2023-2024 | +2 |
| Содержит "surprising" / "contrary" / "unexpected" в abstract | +3 |
| Есть код на GitHub / Papers With Code | +2 |
| Высокое цитирование (если известно) | +2 |
| Кросс-доменная (другая область, та же проблема) | +2 |

---

### Формат вывода

```markdown
## 🔬 Топ-5 фундаментальных (высокоцитируемые / классика)

1. **[Название статьи]** (год) — arXiv:XXXX / DOI
   - **Ключевой результат**: [1 предложение]
   - **Применить**: [как использовать в проекте]
   - **Код**: [ссылка или "нет"]

## 🆕 Топ-5 свежих (< 2 лет)

1. **[Название]** (2025/2026)
   - **Ключевой результат**: [1 предложение]
   - **Почему важно**: [что меняет в текущем подходе]
   - **Код**: [ссылка или "нет"]

## 🎯 Топ-5 неочевидных (counterintuitive / surprising)

1. **[Название]** (год)
   - **Общепринятое мнение**: [что все думали]
   - **Что обнаружили**: [неожиданный результат]
   - **Импликация для проекта**: [что менять]

## ⚡ Главный инсайт сессии
> [1-2 предложения: самое важное что изменит подход к проекту]

## 📚 Следующий шаг
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

- После research-scout → `запусти skeptic` — проверить применимость найденного
- После research-scout → `запусти codex-solver` — реализовать найденный алгоритм
- Ключевые статьи → `error-to-lesson` — сохранить инсайт в wiki
- `scientific-research` skill — для полного цикла исследования с kill criteria
