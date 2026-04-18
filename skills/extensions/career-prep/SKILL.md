<!-- BSV — Brief Skill View | поиск: BSV
Скил   : career-prep
TL;DR  : Подготовка к интервью в топ AI-компании прямо в ходе работы над проектами
Вызов  : /career, career:, "вопрос с интервью", "готовь к интервью"
НЕ для : Общие карьерные советы без привязки к текущему проекту
-->

---
name: career-prep
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-04-18]
  Система подготовки к интервью в топ AI-компании (Anthropic, OpenAI, Google,
  Cursor, Perplexity) встроенная в работу над проектами. Двойная польза:
  продукт + навык одновременно.
  Triggers: /career, career:, interview, интервью, leetcode, собеседование,
  вопрос с интервью, готовь к интервью, STAR, system design.
effort: minimal
tokens: ~600
---

# Career Prep — AI Engineer Interview System

## Целевая роль

**AI Engineer / LLM Engineer / Applied AI Engineer**

Топ-компании по приоритету:
1. **Tier S** — Anthropic, OpenAI, Google DeepMind (ценят builder-менталитет)
2. **Tier 1** — Cursor, Perplexity, Mistral, Cohere, Hugging Face
3. **Tier 2** — Google, Meta, Microsoft AI divisions

## Что проверяют на интервью

| Компонент | Вес | Текущий уровень |
|-----------|-----|----------------|
| Алгоритмы / DS | 25% | ⚠️ нужна практика |
| System Design (AI) | 30% | ✅ уже строишь |
| ML/AI теория | 25% | ⚠️ частично |
| Behavioral (STAR) | 20% | ✅ есть истории |

## Когда активировать

### `/career question` — вопрос с интервью по текущей теме
Claude генерирует вопрос уровня Anthropic/Google связанный
с тем что ты сейчас делаешь. Отвечаешь — получаешь фидбек.

### `/career star` — STAR-история из последней задачи
Фиксирует что только что сделал в формате интервью:
```
Situation: [контекст задачи]
Task: [что нужно было решить]
Action: [как решил, конкретно]
Result: [измеримый результат]
→ Тема: "Tell me about a technical decision..."
```

### `/career algo` — алгоритмическая задача
LeetCode-стиль задача связанная с текущим проектом:
- Работаешь с Neo4j → задача на графы
- Работаешь с хуками → задача на очереди/события
- Работаешь с wiki-индексом → задача на поиск/хэши

### `/career roadmap` — где ты сейчас и что дальше
Показывает прогресс по 6-месячному роадмапу.

## 6-месячный роадмап

```
Месяц 1-2: Foundation
  □ LeetCode: 1 задача/день (Easy → Medium)
  □ Фокус: Array, Hash Map, Graph, Tree
  □ Python: generators, decorators, async/await deep dive
  □ Проект: GeoMiro baseline (rules-only, без LLM)

Месяц 3-4: AI Core
  □ Transformers: читать Attention is All You Need с кодом
  □ RAG: реализовать в CogniRouter (embeddings + retrieval)
  □ Vector DB: Chroma или Qdrant (добавить в один проект)
  □ Evaluation: Brier score, BLEU, human eval
  □ Проект: CogniRouter — embedding-based routing

Месяц 5-6: Interview Mode
  □ System Design: 2 mock/неделю
  □ 20 STAR-историй из своих проектов
  □ Blind 75 LeetCode завершить
  □ Отправить заявки: Anthropic → Cursor → Perplexity
```

## Алгоритмы по проектам (маппинг)

| Проект | Алгоритм | LeetCode эквивалент |
|--------|----------|---------------------|
| GeoMiro (Neo4j) | BFS/DFS на графах | #200 Number of Islands |
| GeoMiro (события) | Interval merging | #56 Merge Intervals |
| CogniRouter | Trie для routing | #208 Implement Trie |
| Wiki-индекс | Hash map lookup | #1 Two Sum, #146 LRU Cache |
| Хуки (порядок событий) | Topological sort | #207 Course Schedule |
| Claude-cod-top-2026 (hooks pipeline) | Event queue | #239 Sliding Window Max |

## STAR-истории (заготовки из твоих проектов)

### Story 1: "Расскажи о сложном техническом решении"
```
S: Нужно было предотвратить накопление галлюцинаций Claude в памяти
T: wiki_reminder должен сохранять только подтверждённые решения
A: Реализовал _has_verified_evidence() — паттерн "No Execution No Memory"
   Ключевые слова + Evidence markers + 5-мин debounce
R: 0 неподтверждённых фактов в wiki, 2MB limit, CI green
```

### Story 2: "Расскажи о системе которую ты спроектировал"
```
S: Нужна была система защиты от prompt injection в AI-агенте
T: 8 типов атак, не ломая нормальный markdown и код
A: Многоуровневый input_guard.py — HIGH_PRIORITY (immediate block)
   vs LOW (log only). Backtick = shell context, не inline code
R: 0 false positives на markdown, 100% блокировка shell injection
```

### Story 3: "Как ты работаешь с качеством кода?"
```
S: 49 хуков, ни одного ручного теста на hooks pipeline
T: 862 теста + CI на Linux + ruff + mypy
A: TDD workflow — каждый хук имеет unit + integration тест
   Smoke tests: 130 skills + 82 hooks автоматически
R: 86% coverage local, 65% CI/Linux, 0 регрессий за 3 месяца
```

## Вопросы с интервью Anthropic (реальные)

1. "How would you design a system to evaluate LLM outputs at scale?"
2. "Describe a time you caught a bug that could have caused serious harm"
3. "How do you think about the tradeoff between model capability and safety?"
4. "Walk me through how you'd implement a RAG pipeline from scratch"
5. "What's wrong with this prompt? [даётся промпт с проблемами]"

## Gotchas

- Anthropic ценит safety-thinking — всегда упоминай как учитывал риски
- OpenAI ценит scaling — говори о production-ready решениях
- Cursor/Perplexity ценят скорость — показывай что можешь строить быстро
- Алгоритмы важны даже для AI ролей — не пропускай LeetCode
