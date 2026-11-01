# Live-only lines from global hypothesis-revival (not in repo), saved 2026-11-01 before deploy
# Review and merge into skills/extensions/boyko-hypothesis-revival, then delete this file.
name: hypothesis-revival
description: "Система поиска 'похороненных' гипотез: берёт проблему или контекст → ищет в старой литературе (pre-2015), патентах, монографиях гипотезы, которые были правдоподобными но непроверяемыми тогда → проверяет стали ли они проверяемы сейчас (AlphaFold, LLM, embeddings, OpenAlex, CRISPR, AutoML, новые датасеты) → возвращает ranked таблицу Revival Leads с ABC-мостами, testability score и конкретными следующими шагами. Метод: Swanson LBD + sleeping beauty detection + temporal testability gap. Triggers: '/hypothesis-revival', 'найди старые гипотезы', 'что про это знали раньше', 'hypothesis revival', 'забытые решения', 'ищи в старой литературе', 'sleeping beauty hypothesis', 'LBD search', 'что было до нас', 'старые идеи для проблемы', 'поищи в прошлом', 'есть ли готовое решение в старых работах'. НЕ для: поиска свежих статей (→ /deep-research или /literature-review), генерации новых гипотез с нуля (→ /sci-hypothesis), cross-domain аналогий без литературного поиска (→ /cross-domain)."
triggers: [/hypothesis-revival, "найди старые гипотезы", "что про это знали раньше", "hypothesis revival", "забытые решения", "ищи в старой литературе", "sleeping beauty hypothesis", "LBD search", "что было до нас", "старые идеи для проблемы", "поищи в прошлом", "есть ли готовое решение в старых работах"]
| **Quick** | `/hypothesis-revival quick: <проблема>` | ~5 мин | 5 revival leads, web search only |
| **Standard** | `/hypothesis-revival <проблема>` | ~15 мин | 10 leads, OpenAlex + web + ABC bridges |
| **Deep** | `/hypothesis-revival deep: <проблема>` | ~40 мин | Full pipeline, patents, all sources, kill-tests |
| **Domain** | `/hypothesis-revival domain:<область> <проблема>` | ~20 мин | Domain-restricted search (biomedicine / materials / physics / CS) |
#### 2a. OpenAlex API (старая литература, мало цитирований)
curl -s "https://api.openalex.org/works?search=ATERM&filter=publication_year:%3C2015&sort=cited_by_count:asc&per-page=5&select=id,title,publication_year,cited_by_count,concepts" \
`curl -s "https://api.openalex.org/works/WORK_ID" | python -c "import json,sys; w=json.load(sys.stdin); print(w.get('abstract',''))"`
| Нашёл несколько конкурирующих объяснений | → `/hypothesis-arbiter` |
