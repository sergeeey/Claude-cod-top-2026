---
name: plugin-eval
sub_type: guide
version: "1.0"
source: "wshobson/agents (adapted)"
description: >
  3-слойная оценка качества скилов/плагинов: Static Analysis (<2 сек) →
  LLM Judge (30-90 сек) → Monte Carlo Simulation (5-20 мин, 50 реальных invocations).
  Выдаёт Platinum/Gold/Silver/Bronze badge. Используй для оценки качества новых скилов
  перед добавлением в экосистему, аудита существующих скилов, или когда скил ведёт себя
  не как ожидается.
  Триггеры: /plugin-eval, "оценить скил", "audit skill", "skill quality", "evaluate plugin",
  "skill score", "platinum badge", "quality certification".
tokens: ~300
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : plugin-eval
TL;DR  : 3-слойная сертификация скилов: Static + LLM Judge + Monte Carlo → Platinum/Gold/Silver/Bronze
Вызов  : /plugin-eval, оценить скил, skill quality, audit plugin
НЕ для : Code review (→ /reviewer); security audit (→ /sec-auditor)
-->

# Plugin-Eval — Quality Certification

## Зачем

Скил который запускается не когда надо или даёт непоследовательный output —
хуже отсутствия скила. Plugin-eval измеряет качество объективно: три слоя,
десять измерений, один итоговый score.

---

## Три Слоя Оценки

### Layer 1 — Static Analysis (<2 сек)

Анализирует SKILL.md без запуска:

| Измерение | Что проверяет |
|-----------|---------------|
| Frontmatter quality | name, description, tokens заполнены, description >80 chars |
| Trigger coverage | Есть "use when" language, ≥3 триггерных фразы |
| Structural completeness | Есть BSV блок, секция Related Skills |
| Token efficiency | <800 строк OR есть references/ поддиректория |
| Ecosystem coherence | Нет дублирования с другими скилами |

**Anti-pattern penalties** (каждый -5% от score):
- `OVER_CONSTRAINED` — >15 MUST/ALWAYS/NEVER директив
- `EMPTY_DESCRIPTION` — <20 chars в description
- `MISSING_TRIGGER` — нет "use when" language
- `BLOATED_SKILL` — >800 строк без references/
- `ORPHAN_REFERENCE` — битые ссылки на другие скилы

### Layer 2 — LLM Judge (30-90 сек)

Структурированная оценка по anchored rubrics:

| Измерение | Вес | Что оценивается |
|-----------|-----|-----------------|
| triggering_accuracy | 0.25 | Правильно ли активируется на целевые запросы? |
| orchestration_fitness | 0.20 | Чёткое разделение supervisor vs worker логики? |
| output_quality | 0.20 | Полезность и качество ответа |
| scope_calibration | 0.15 | Не делает слишком много / слишком мало? |
| structural_completeness | 0.10 | BSV, Related Skills, примеры есть? |
| token_efficiency | 0.10 | Не раздут без оснований? |

**Mental test prompt (для triggering_accuracy):**
```
Представь пользователь пишет: "[trigger phrase]"
Должен ли активироваться этот скил? Да/Нет + уверенность.
```

### Layer 3 — Monte Carlo (5-20 мин)

50 реальных invocations, статистические confidence intervals:

| Метрика | Что измеряет |
|---------|-------------|
| activation_rate | % запросов где скил правильно активировался |
| output_consistency | Стандартное отклонение качества ответов |
| failure_rate | % полных провалов (no useful output) |
| token_efficiency | Среднее tokens/invocation vs полезность |

---

## Composite Score Formula

```
score = Σ(dimension_weight × layer_contribution)
```

**Layer contributions по измерению:**
- `triggering_accuracy`: 70% Monte Carlo + 30% LLM Judge
- `structural_completeness`: 80% Static + 20% LLM Judge
- `output_quality`: 100% LLM Judge
- `token_efficiency`: 50% Static + 50% Monte Carlo

**Anti-pattern penalty:**
```
final = score × max(0.5, 1.0 - 0.05 × anti_pattern_count)
```

---

## Quality Badges

| Badge | Score | Значение |
|-------|-------|----------|
| 🏆 Platinum | ≥90 | Reference quality — используй как образец для новых скилов |
| 🥇 Gold | ≥80 | Production ready — можно добавлять в экосистему |
| 🥈 Silver | ≥70 | Functional — работает, но нужны улучшения |
| 🥉 Bronze | ≥60 | Minimum viable — есть серьёзные проблемы |
| ❌ Below | <60 | Не добавлять в экосистему до переработки |

---

## Как Запустить Оценку

### Быстрая (Layer 1 только, <2 сек)

```
Проверь SKILL.md скила [имя] по критериям Layer 1 plugin-eval:
- Frontmatter: name, description (>80 chars?), tokens заполнены?
- Triggers: ≥3 фразы, есть "use when" language?
- BSV блок есть?
- Related Skills есть?
- Anti-patterns: >15 MUST/ALWAYS/NEVER? >800 строк без references/?
Выдай score /100 и список issues.
```

### Полная (все 3 слоя)

Скажи: `/plugin-eval [skill-name]` — выполнит все три слоя последовательно.

---

## Приоритеты Улучшения

| Хочешь улучшить | Что делать |
|-----------------|-----------|
| triggering_accuracy | Перепиши description — конкретнее "use when" |
| orchestration_fitness | Явно раздели: что делает этот скил сам vs делегирует |
| output_quality | Добавь примеры хорошего output |
| token_efficiency | Перенеси детали в references/details.md |

---

## Связанные скилы

- `reviewer` — code review (не скил review)
- `skill-suggester` — предлагает улучшения в знаниях
- `claim-decomposer` — декомпозиция перед оценкой complex скилов
