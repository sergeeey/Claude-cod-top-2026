---
name: hypothesis-revival
description: "Система поиска 'похороненных' гипотез: берёт проблему или контекст → ищет в старой литературе (pre-2015), патентах, монографиях гипотезы, которые были правдоподобными но непроверяемыми тогда → проверяет стали ли они проверяемы сейчас (AlphaFold, LLM, embeddings, OpenAlex, CRISPR, AutoML, новые датасеты) → возвращает ranked таблицу Revival Leads с ABC-мостами, testability score и конкретными следующими шагами. Метод: Swanson LBD + sleeping beauty detection + temporal testability gap. Triggers: '/hypothesis-revival', 'найди старые гипотезы', 'что про это знали раньше', 'hypothesis revival', 'забытые решения', 'ищи в старой литературе', 'sleeping beauty hypothesis', 'LBD search', 'что было до нас', 'старые идеи для проблемы', 'поищи в прошлом', 'есть ли готовое решение в старых работах'. НЕ для: поиска свежих статей (→ /deep-research или /lit-search), генерации новых гипотез с нуля (→ /sci-hypothesis), cross-domain аналогий без литературного поиска (→ /cross-domain)."
allowed-tools: Read, Grep, Glob, WebSearch, Bash, Agent
version: "1.1.0"
license: "Swanson LBD (1986) + sleeping beauty detection + temporal testability gap analysis"
---

# Hypothesis Revival Engine

**Центральная идея:** Многие гипотезы в истории науки не были опровергнуты — они были *оставлены без проверки* из-за отсутствия инструментов, данных или вычислительных ресурсов. Сейчас LLM, AlphaFold, OpenAlex, CRISPR-скрининг, символьная регрессия и открытые датасеты закрыли большинство этих gap-ов. Этот скилл систематически находит такие гипотезы для твоей конкретной проблемы.

**Чего нет у конкурентов (verified 2026-05-01):**
- Google Co-Scientist: генерирует *новые* гипотезы, не находит *старые забытые*. Закрыт (gated access).
- Elicit / Consensus: поиск по литературе, не LBD-мосты и не temporal testability check.
- AI Scientist: end-to-end pipeline от гипотезы до статьи, не revival engine.

---

## Режимы запуска

| Режим | Команда | Время | Что даёт |
|-------|---------|-------|----------|
| **Quick** | `/hypothesis-revival quick: <проблема>` | ~5 мин | 5 revival leads, web search only |
| **Standard** | `/hypothesis-revival <проблема>` | ~15 мин | 10 leads, OpenAlex + web + ABC bridges |
| **Deep** | `/hypothesis-revival deep: <проблема>` | ~40 мин | Full pipeline, patents, all sources, kill-tests |
| **Domain** | `/hypothesis-revival domain:<область> <проблема>` | ~20 мин | Domain-restricted search (biomedicine / materials / physics / CS) |

---

## Feasibility Gate (запустить первым)

Оцени входную задачу:

- **Хорошо подходит:** проблема застряла, известные методы не работают, есть ощущение "это не может быть совсем новым"
- **Плохо подходит:** нужно просто найти свежие статьи (→ `/lit-search`), нет конкретной проблемы (слишком широко)
- **Красный флаг:** если проблема сформулирована только как "расскажи о теме X" — попроси сформулировать конкретный вопрос или bottleneck

---

## Полный поток (7 шагов)

### Шаг 0 — Парсинг входа (скрытый, не показывать пользователю)

Определи из контекста пользователя:

```
PROBLEM: <одна ключевая проблема / bottleneck / вопрос>
DOMAIN: <основная научная область, если известна>
EPOCH: <когда могли возникнуть релевантные гипотезы? по умолчанию: 1950–2010>
ENABLERS_TO_CHECK: <какие modern enablers наиболее релевантны:
  - AlphaFold/protein structures
  - LLM/embeddings/semantic similarity
  - OpenAlex/large literature corpus
  - AutoML/neural architecture search
  - CRISPR/genomics screening
  - single-cell RNA-seq
  - diffusion models/generative AI
  - graph neural networks
  - symbolic regression (PySR)
  - web-scale datasets / big data
  - real-time sensors / IoT
  - wearables / biometrics
  - new computational power (GPU cluster)
  - none obvious — search broadly>
```

Если пользователь не уточнил — **не спрашивай**, выведи из контекста. Если совсем непонятно — задай **один** вопрос: "Это ближе к биологии/химии, физике, или CS/data science?"

---

### Шаг 1 — Извлечь ABC anchor термины

По методу Swanson (1986) каждая "скрытая связь" строится как:
- **A** = твоя проблема / целевое явление
- **B** = промежуточные концепты (bridge terms) — найдём в старой литературе
- **C** = механизм решения из другого поля

Извлеки из формулировки проблемы:
- 3–5 **A-терминов** (что именно мы пытаемся решить/понять)
- 3–5 **C-терминов** (современные enabler-технологии, релевантные домену)

```
Пример:
Problem: "Как детектировать аномальные финансовые паттерны без разметки?"
A-terms: [anomaly detection, financial fraud, unsupervised pattern, unlabeled data]
C-terms: [contrastive learning, self-supervised, graph neural network, isolation forest]
B-terms (найдём в поиске): [concept drift, behavioral fingerprinting, ...]
```

---

### Шаг 2 — Поиск sleeping beauties в старой литературе

**Sleeping beauty** = статья, процитированная <5 раз за первые 10 лет после публикации, но концептуально релевантная проблеме. Это кандидаты на revival.

**Выполни эти поиски** (параллельно):

#### 2a. OpenAlex API (старая литература, мало цитирований)
```bash
# ATERM = URL-encoded search term (пробелы → +)
# per_page (underscore) — официальный параметр OpenAlex
# abstract_inverted_index — НЕ plain text, это positional index; в select не включаем
curl -s "https://api.openalex.org/works?search=ATERM&filter=publication_year:%3C2015&sort=cited_by_count:asc&per_page=5&select=id,title,publication_year,cited_by_count,concepts" \
  | python -c "
import json,sys
data=json.load(sys.stdin)
for w in data.get('results',[]):
    print(w['publication_year'], w['cited_by_count'], w['title'][:80])
"
```

Запусти для **каждого** A-терма. Пробелы в термине заменяй на `+` в URL.
Собери результаты. Если нужен abstract — делай отдельный запрос по work ID:
`curl -s "https://api.openalex.org/works/WORK_ID" | python -c "import json,sys; w=json.load(sys.stdin); print(w.get('abstract',''))"`

#### 2b. Semantic Scholar (semantic proximity, старые работы)
```bash
# Limit=5; без API-ключа rate limit ~100 req/5 min — не запускай в цикле без паузы
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=ATERM&fields=title,year,citationCount,abstract&limit=5" \
  | python -c "
import json,sys
data=json.load(sys.stdin)
for p in data.get('data',[]):
    if p.get('year') and p['year'] < 2015:
        print(p['year'], p.get('citationCount',0), p['title'][:80])
" 2>/dev/null
```

#### 2c. WebSearch (патенты + забытые техрепорты)
Запусти **отдельные** WebSearch запросы (не объединяй site: через OR):
- `"ATERM" hypothesis untested site:patents.google.com before:2015`
- `"ATERM" hypothesis untested site:arxiv.org before:2015`
- `"ATERM" "future work" OR "not yet tested" before:2015`
- `"ATERM" dormant OR neglected OR forgotten hypothesis`

---

### Шаг 3 — Temporal Testability Check

**⚠️ HARD RULE: Revival is forbidden unless the old blocker is explicitly removed by a concrete modern enabler.**
Семантическое сходство ≠ revival. ABC мост должен давать testable mechanism, не метафору.

Для каждого Revival Candidate заполни полностью:

```
CANDIDATE: <название/идея>
ORIGINAL_YEAR: <когда была предложена>

DEATH_REASON: <почему идея была оставлена — выбери основную>
  — no_tools          : инструменты не существовали
  — no_data           : не было нужного датасета
  — insufficient_compute : не хватало вычислений
  — no_method         : метод не был изобретён
  — disproven         : ⛔ STOP — идея опровергнута, revival запрещён
  — wrong_assumptions : исходные предположения оказались неверны → требует осторожности
  — too_expensive     : экономически нецелесообразно тогда
  — unfashionable     : вышло из моды без опровержения
  — mathematically_incomplete : формализм был неполным
  — [other]

# Если DEATH_REASON = disproven → SKIP этот кандидат целиком

KNOWN_REFUTATION_CHECK: <Поищи: была ли идея убита ПОСЛЕ 2015?>
  WebSearch: "CANDIDATE_NAME" refuted OR disproven OR failed site:arxiv.org after:2015
  WebSearch: "CANDIDATE_NAME" null result OR negative result after:2015
  VERDICT: clean / refuted_post_2015 / unclear
  # Если refuted_post_2015 → SKIP
  # Если unclear → продолжить, но: в Step 4 добавить ⚠️ CAUTION: refutation status unclear
  #   и cap TESTABILITY_SCORE ≤ 7 (не давать 8-10 при unclear)
  # Note: `after:2015` и `site:` — Google Search syntax. Если WebSearch на другом бэкенде,
  #   фильтруй год вручную из результатов. Надёжная альтернатива: OpenAlex
  #   filter=publication_year:%3E2015 (url-encoded %3E = >)

ORIGINAL_BLOCKER: <конкретная техническая причина, не смогли проверить>
  — insufficient compute
  — no protein structure data
  — no large corpus
  — no labeled dataset
  — no single-cell resolution
  — no real-time sensing
  — methodology not invented yet
  — [other]

ENABLER_NOW: <что именно изменилось — конкретный инструмент, не buzzword>
  — AlphaFold3 (2024): protein structures for 200M proteins
  — OpenAlex (2022): 250M papers, free API
  — GPT-4/Claude embeddings: semantic similarity at scale
  — CRISPR screening datasets (post-2018)
  — single-cell RNA-seq (post-2015)
  — symbolic regression PySR (2020)
  — web-scale labeled datasets (ImageNet era onwards)
  — GPU compute cost -1000x vs 2010

ENABLER_STRENGTH: 0-10
  0-2: buzzword only — "ChatGPT can help" без конкретики → WEAK, не revival
  3-5: plausible modern tool, требует нетривиальной адаптации
  6-8: tool directly addresses blocker, требует engineering
  9-10: tool directly removes blocker, применяется почти напрямую
  # Пример сильного: blocker=protein structure unknown, enabler=AlphaFold → 9/10
  # Пример слабого: blocker=hard quantum gravity calc, enabler=ChatGPT → 1/10

TESTABILITY_SCORE: 0-10
  0-3: blocker still exists
  4-6: partially testable, significant effort
  7-8: testable now, medium effort (~weeks)
  9-10: testable now, low effort (~days with modern tools)

TOY_TEST_1DAY: <минимальный проверяемый тест, выполнимый за 1 рабочий день>
  # Формат ОБЯЗАТЕЛЬНО: "запустить X на данных Y, ожидать Z" — все три части конкретны
  # Если сформулировать невозможно → cap TESTABILITY_SCORE = 5 (кандидат автоматически
  #   не проходит гейт ≥6 и отсеивается без ручного решения)
```

**Порог для продолжения:**
- DEATH_REASON ≠ `disproven`
- KNOWN_REFUTATION_CHECK = `clean` или `unclear`
- ENABLER_STRENGTH ≥ 5
- TESTABILITY_SCORE ≥ 6
- TOY_TEST_1DAY заполнен

**Только candidates, прошедшие все 5 условий, идут дальше.**

---

### Шаг 4 — ABC Bridge Construction

Для каждого прошедшего кандидата построй явный ABC мост:

```
🔗 REVIVAL LEAD #N

[A] Твоя проблема: <PROBLEM>
      ↓ through...
[B] Старая гипотеза/концепт: <CANDIDATE_NAME> (<YEAR>)
    Оригинальный источник: <автор, название, год>
    Death reason: <DEATH_REASON>
    Known refutation post-2015: <clean / unclear — если refuted_post_2015 этот блок не должен существовать>
    # ⚠️ Если unclear → добавь строку:
    # CAUTION: refutation status unclear. Search queries: [укажи что именно искал]. TESTABILITY_SCORE capped ≤ 7.
    Почему была отложена: <ORIGINAL_BLOCKER>
      ↓ enabled by...
[C] Современный enabler: <ENABLER_NOW>
    Enabler strength: N/10 — <конкретное объяснение как enabler снимает blocker>

BRIDGE: Если применить [B] к [A] используя [C],
то <конкретное измеримое следствие>,
потому что <механизм>.
# Требование: механизм, не метафора. "похоже на" не считается.

TESTABILITY: N/10 — <почему>
EFFORT: low/medium/high
TOY_TEST_1DAY: <конкретный тест: запустить X на данных Y, ожидать Z>
KILL CRITERION: <что опровергнет идею>
PRIOR ART: <другие попытки применить это? — поищи>
```

---

### Шаг 5 — Confidence Scoring

Для финального ранкинга каждому Revival Lead:

| Критерий | 0-10 | Вес |
|----------|------|-----|
| **Testability Now** | насколько хорошо enabler закрывает blocker | 0.35 |
| **Structural Fit** | ABC мост формально обоснован, не метафора | 0.25 |
| **Prior Evidence** | есть хоть 1 пример переноса этой идеи | 0.20 |
| **Novelty** | не повторяет известное решение | 0.10 |
| **Effort** | обратная оценка трудозатрат | 0.10 |

**Порог для вывода пользователю: ≥ 6.0 weighted score**

---

### Шаг 6 — Дополнительный поиск по B-терминам

Если шаги 2-5 дали < 3 leads с score ≥ 6:

```
# Расширение через "bridge terms" — термины, которые связывают A и другие поля
WebSearch: "ATERM" AND ("bridge" OR "connection" OR "similar to") BEFORE:2012
WebSearch: ATERM_synonyms — найди альтернативные названия явления в других дисциплинах
```

Затем повтори шаги 2-5 для найденных B-терминов.

---

### Шаг 7 — Выдача результата

#### Итоговый формат вывода:

```markdown
## 🔮 Hypothesis Revival Report

**Проблема:** <PROBLEM>  
**Эпоха поиска:** <EPOCH>  
**Источники:** OpenAlex, Semantic Scholar, WebSearch, Patents  
**Дата:** <TODAY>

---

### Топ Revival Leads (ranked by composite score)

| # | Гипотеза (год) | Death Reason | Enabler (strength) | Score | Effort | 1-day toy test |
|---|----------------|--------------|--------------------|-------|--------|----------------|
| 1 | NAME (YEAR) | no_tools | AlphaFold (9/10) | 8.2 | low | run X on Y, expect Z |
| 2 | ... | no_data | ... (6/10) | 7.5 | medium | ... |

> **Note:** Death Reason и Enabler Strength — информационные колонки, они НЕ входят в составной Score из Step 5.
> Score отражает только Step 5 criteria (Testability, Structural Fit, Prior Evidence, Novelty, Effort).
> Кандидаты с `wrong_assumptions` должны быть явно отмечены в ABC bridge секции.
> Кандидаты с `unclear` refutation: Score capped ≤ 7 и требуют CAUTION строки.

---

### Детальные ABC-мосты

#### 🔗 Lead #1: [NAME]
[полный ABC bridge block из Шага 4]

#### 🔗 Lead #2: ...

---

### Что НЕ нашлось (важно)
- Домены, где поиск был затруднён: [...]
- Что потребует Deep режима: [...]

---

### Следующий лучший шаг
> [конкретное действие на ближайшие 30 минут]
```

---

## Evidence markers (расширение стандартных из integrity.md)

Этот скилл использует стандартные маркеры проекта + один дополнительный уровень для источников:

| Маркер | Значение |
|--------|----------|
| `[VERIFIED-REAL]` | Найден реальный источник с URL/DOI — можно привести ссылку |
| `[VERIFIED]` | Подтверждено инструментом (curl вернул данные, grep нашёл) |
| `[INFERRED]` | Логический вывод из проверенных фактов — укажи цепочку |
| `[WEAK]` — аналог `[PARTIALLY-VERIFIED]` | Один косвенный источник или вывод по abstract без полного текста |
| `[UNKNOWN]` | Не проверено — требует дополнительного поиска |

**Запрещены:** `[INFERRED-HIGH]`, `[INFERRED-MEDIUM]` — они не определены в `~/.claude/rules/integrity.md` и создают несовместимость.

---

## Антипаттерны (запрещено)

| Антипаттерн | Что делать вместо |
|-------------|-------------------|
| Выдать "sleeping beauty" без проверки testability | Всегда заполнять ORIGINAL_BLOCKER + ENABLER_NOW |
| ABC мост как метафора ("это похоже на...") | ABC мост как формальная структурная связь |
| Score без обоснования | Каждый score — с объяснением на какой источник опирается |
| Цитировать статью которую не нашёл | Только [VERIFIED-REAL] если нашёл источник, [WEAK] если только abstract, [INFERRED] если вывод |
| Выдать > 10 leads без фильтра | Жёстко отфильтровать по порогу 6.0, лучше 3 сильных чем 15 слабых |
| Игнорировать патенты | Патенты часто содержат непроверенные идеи, особенно pre-2010 |
| Treating `unclear` refutation as equivalent to `clean` | `unclear` = cap TESTABILITY_SCORE ≤ 7 + обязательная CAUTION строка в ABC bridge |
| Не упоминать `wrong_assumptions` в ABC bridge | Если DEATH_REASON = `wrong_assumptions` → добавить явное предупреждение в BRIDGE блок |
| Вагное TOY_TEST_1DAY ("запустить модель, ожидать результат") | Формат обязателен: "запустить X на данных Y, ожидать Z" — без конкретики = cap score |

---

## Когда запускать вместе с другими скиллами

| Ситуация | Chain |
|----------|-------|
| Нашёл lead, хочу проверить структурный изоморфизм | → `/cross-domain` |
| Нашёл lead, хочу атаковать его критически | → `/skeptic` |
| Нашёл lead, хочу построить эксперимент | → `/experiment-design` + FL Standard ladder |
| Хочу найти свежие статьи по теме | → `/lit-search` или `/deep-research` |
| Нашёл несколько конкурирующих объяснений | → `/hypothesis-arbiter` |
| Хочу проверить статистически | → `/stat-validate` |

---

## Реальные примеры revival (из research 2026-05-01)

### Пример 1: Drug Repurposing + AlphaFold
[VERIFIED-REAL] Google Co-Scientist использовал AF-predicted structures для AML drug repurposing — нашёл кандидатов с клинической активностью. Механизм: гипотезы о CDK20 как мишени были в патентах 2003–2010, но структура CDK20 не была известна. AlphaFold (2022) закрыл этот gap.

### Пример 2: Materials synthesis routes + generative AI
[VERIFIED-REAL] MIT (Feb 2026): generative AI model нашёл забытые routes синтеза цеолитов из literature 1960–1980. Эти routes были known но impractical. Modern diffusion models + simulator сделали их testable/reproducible.

### Пример 3: Sleeping beauties в статистике
[VERIFIED-REAL] Бэкпропагейшн был предложен в 1974 (Werbos), проигнорирован. Через 12 лет "возрождён" как backpropagation (1986, Rumelhart). Classic revival через compute enabler.

---

## Sources & Evidence

- [Make LBD Great Again (arXiv:2502.16450)](https://arxiv.org/abs/2502.16450) — production-ready LBD pipeline
- [Google Co-Scientist validated in Nature (May 2026)](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/)
- [OpenAlex API](https://openalex.org) — 250M papers, free
- [Semantic Scholar API](https://www.semanticscholar.org/product/api/tutorial)
- [WISDOM weak signals (arXiv:2409.15340)](https://arxiv.org/abs/2409.15340)
- [Sleeping beauties in science (UChicago)](https://news.uchicago.edu/story/new-model-reveals-forgotten-influencers-and-sleeping-beauties-science)
- [MIT zeolite synthesis revival (Feb 2026)](https://news.mit.edu/2026/how-generative-ai-can-help-scientists-synthesize-complex-materials-0202)

---

**Last updated:** 2026-06-23  
**Version:** 1.1.0 (added Death Reason, Enabler Strength, Known Refutation Check, mandatory 1-day toy test)  
**Status:** ACTIVE  
**Method:** Swanson LBD (1986) + sleeping beauty detection + temporal testability gap analysis  
**Hard rule:** Revival forbidden unless old blocker explicitly removed by concrete modern enabler  
**Gap this fills:** No existing tool combines sleeping-beauty-detection + testability-now-check + ABC bridge construction + refutation guard
