# Литературный Поиск — Детальный Протокол

## Принцип поиска

Большинство исследователей ищут только современными терминами и пропускают 40-60% релевантной литературы. До 2010 года многие явления назывались иначе. Негативные результаты не публикуются — их нужно искать специально.

---

## Шаг 1 — Найти старые термины

**Зачем:** Термины меняются. "Machine learning" раньше называли "pattern recognition" и "connectionism". Если ищешь только современными словами — теряешь 10-20 лет литературы.

**Как найти старые термины:**

```
Запроси Claude:
"Как называлось [явление] до 2000 года в [домен]?"
"Какие синонимы использовались для [концепт] в [домен] до 2010?"
"Найди альтернативные термины для [явление] в смежных доменах"
```

**Примеры трансформаций терминов:**

| Современный термин | Старый термин (до 2000-2010) |
|-------------------|------------------------------|
| Machine learning | Pattern recognition, adaptive systems |
| Neural networks | Connectionism, parallel distributed processing |
| LLM hallucination | Model confabulation, false memory (AI) |
| Epigenetics | Gene expression regulation, chromatin remodeling |
| Network effects | Bandwagon effects, threshold models |
| Prompt engineering | Query formulation, information retrieval tuning |

---

## Шаг 2 — Систематический поиск по базам

### Биомедицина / Науки о жизни

**PubMed** (https://pubmed.ncbi.nlm.nih.gov):
```
Поисковые стратегии:
1. Точная фраза: "exact mechanism name"
2. MeSH термины: [MeSH Terms] для стандартизированного словаря
3. Фильтры: Publication type → "Randomized Controlled Trial", "Meta-Analysis"
4. Негативные результаты: добавь "negative results" OR "failed" OR "no effect"
5. Даты: [PDAT]: 1990:2010 — для старых терминов
```

**PubMed advanced query пример:**
```
("chromatin loop"[Title/Abstract] OR "CTCF binding"[Title/Abstract]) 
AND ("mutation"[Title/Abstract] OR "variant"[Title/Abstract])
AND ("2015"[PDAT]: "2024"[PDAT])
NOT ("review"[Publication Type])
```

### AI / ML / Компьютерные науки

**arXiv** (https://arxiv.org):
```
Секции: cs.LG, cs.AI, stat.ML, cs.CL
API: https://export.arxiv.org/api/query?search_query=...
Для старых работ: ищи q-bio, cs.NE (neural evolution)
```

**Semantic Scholar** (https://www.semanticscholar.org):
```
Преимущества:
- Citation graph: кто цитирует + что цитируется
- Semantic search (не только ключевые слова)
- Open API для batch поиска
- Influence score (влиятельность статьи)
```

**Google Scholar**:
```
Операторы:
- "exact phrase" — точное совпадение
- author:Lastname — конкретный автор
- site:arxiv.org — только arXiv
- Cited by N — популярность статьи
```

### Психология / Социальные науки

**PsycINFO** (через institutional access):
```
Ищи: behavioral effects, cognitive mechanisms, social influence
```

**SSRN** (https://ssrn.com) — препринты экономики и права

**OSF Preprints** (https://osf.io/preprints/) — открытые рабочие материалы

### Физика / Математика

**arXiv** (math, physics, quant-ph секции)
**INSPIRE-HEP** (https://inspirehep.net) — физика высоких энергий

---

## Шаг 3 — Citation Chaining (backward + forward)

**Backward chaining:** В нашедших статьях читай References — там часть старых терминов и основополагающих работ.

**Forward chaining:** Кто цитирует эту статью? Semantic Scholar / Google Scholar → "Cited by N" → найди работы, которые строятся на первой.

**Инструмент: Connected Papers** (https://connectedpapers.com)
- Визуальный граф связанных статей
- Находит кластеры похожих работ
- Показывает семинальные работы в центре графа

---

## Шаг 4 — Поиск Негативных Результатов

**Почему критично:** Publication bias — журналы предпочитают позитивные результаты. Негативные результаты публикуются в 3-5 раз реже. Без них твоя доказательная база систематически смещена.

**Где искать:**

| Источник | Что там |
|----------|---------|
| PubMed: добавь "negative results" | Статьи с явными null-результатами |
| PubMed: добавь "failed replication" | Неудачные репликации |
| Replication Wiki | https://replicationwiki.iast.net |
| PsychFileDrawer | http://psychfiledrawer.org — Psychology |
| OSF Registered Reports | Предрегистрированные исследования с любым исходом |
| PROSPERO | Систематические обзоры (включая незавершённые) |

**PubMed запрос для негативных результатов:**
```
("your hypothesis keywords") AND 
("no significant difference" OR "null result" OR "negative result" OR 
 "failed to replicate" OR "no effect" OR "not significant")
```

**Важно:** Отсутствие в индексах ≠ опровержение. Это может быть publication bias.

---

## Шаг 5 — Смежные Домены

Самые важные доказательства часто публикуются под другим именем в другой области.

**Матрица смежных доменов:**

| Твой домен | Смежные домены для проверки |
|------------|----------------------------|
| Биология | Физика (моделирование), Химия (механизм), Медицина (клинические данные) |
| ML/AI | Нейронауки (биологические аналоги), Статистика (методология) |
| Экономика | Психология (поведение), Социология (групповые эффекты) |
| Психология | Нейронауки, Антропология, Эволюционная биология |
| Физика | Математика (формализм), Инженерия (применение) |

**Запрос для Claude:**
```
"В каких доменах изучается аналог [твоего явления]? 
Как это называется там?"
```

---

## Шаг 6 — Проверить Качество Найденных Статей

### GRADE-like оценка (упрощённая)

| Критерий | Сильная статья | Слабая статья |
|----------|---------------|---------------|
| Дизайн | RCT, мета-анализ | Case report, expert opinion |
| Выборка | N>100, репрезентативная | N<10, convenience sample |
| Контроль | Рандомизация + ослепление | Нет контроля |
| Репликация | ≥2 независимые лаборатории | Одна лаборатория |
| Pre-registration | Предрегистрировано | Нет |
| Журнал | Impact Factor >5 | Серый журнал |

### Проверки перед включением в доказательную базу

1. **Ретракция:** https://retractionwatch.com — не отозвана ли статья?
2. **Конфликт интересов:** есть ли у авторов финансовый интерес?
3. **Независимость:** все авторы из одной лаборатории? Один и тот же датасет?
4. **P-hacking риск:** много гипотез тестировалось одновременно без коррекции?

---

## Быстрые AI-запросы для литературного поиска

```
1. Обзор поля:
   "Дай обзор литературы по [тема] за последние 5 лет. 
   Выдели 3-5 ключевых статей, основные дискуссии, нерешённые вопросы."

2. Поиск опровержений:
   "Найди аргументы и эмпирические данные ПРОТИВ [гипотеза].
   Самые сильные контраргументы в литературе."

3. Механистические объяснения:
   "Какие биохимические/молекулярные/вычислительные механизмы предложены 
   для объяснения [явление]? Ссылки на ключевые работы."

4. Репликации:
   "Были ли попытки репликации исследований по [тема]? 
   Успешные и неудачные. Перечисли основные."
```

---

## Поиск по типу гипотезы

### Descriptive гипотезы
- **Цель:** Найти репрезентативные данные о распространённости явления
- **Лучшие источники:** Systematic reviews, population surveys, registry data
- **Ключевые слова:** "prevalence", "incidence", "distribution", "survey"

### Predictive гипотезы
- **Цель:** Найти out-of-sample validation и benchmark сравнения
- **Лучшие источники:** Competition results (Kaggle), benchmarks (Papers With Code), reproducibility studies
- **Ресурс:** https://paperswithcode.com — SOTA по задачам

### Causal гипотезы
- **Цель:** Найти RCT, квази-эксперименты, IV-анализы
- **Ключевые слова:** "causal", "randomized", "instrumental variable", "difference-in-differences"
- **Ресурс:** AEA RCT Registry, ClinicalTrials.gov, EGAP (политические науки)

---

## Быстрый чеклист поиска (10 минут)

```
[ ] Запрос старых терминов (Claude)
[ ] PubMed/arXiv — прямые термины (3+ статьи)
[ ] PubMed/arXiv — старые термины (1+ статья)
[ ] Проверка негативных результатов (null results)
[ ] Один смежный домен (аналоги)
[ ] Retractionwatch — ключевые статьи не отозваны
[ ] null_results/INDEX.md в проекте — не повторять уже опровергнутое
```

---

## Полный поиск (2-4 часа)

```
[ ] Быстрый чеклист выполнен
[ ] Citation backward chaining (2-3 уровня)
[ ] Citation forward chaining (кто цитирует ключевые)
[ ] Connected Papers граф построен
[ ] 2+ смежных домена проверены
[ ] Систематический поиск негативных результатов
[ ] Quality check всех включённых статей (GRADE)
[ ] Конфликты интересов проверены
```
