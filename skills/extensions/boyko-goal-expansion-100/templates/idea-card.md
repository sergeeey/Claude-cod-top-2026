# Idea card template

Один блок на каждый итоговый вариант (Шаг 9 SKILL.md). Одна идея — ровно
одна основная категория `Type`.

```markdown
## N. Название

Type: established_method | extension | cross_domain_transfer | hybrid |
      inverse_problem | no_go | computational_experiment | new_hypothesis
Evidence: fact | inference | hypothesis | unknown
Source domains:
Target gap:

Core mechanism:
[Конкретный механизм — не общая фраза]

Why it may work:
[Почему структура метода соответствует структуре задачи]

Required assumptions:
[Какие условия должны быть истинны]

Main obstacle:
[Главная причина, по которой подход может не сработать]

Cheapest test:
[Самый дешёвый тест на один день или одну неделю]

Falsifier:
[Какой результат должен заставить отказаться от идеи]

Expected output:
[Что появится при успехе: формула, алгоритм, теорема, прототип, датасет,
оператор, эксперимент...]

Scores:
  relevance: 0-10
  feasibility: 0-10
  novelty: 0-10
  expected_impact: 0-10
  evidence_strength: 0-10
  falsifiability: 0-10
  speculation_penalty: 0-4
  confidence: 0.00-1.00
  # optional, если указано — validate_output.py сверит с формулой:
  # priority_score: 0.00-10.00
  # adjusted_score: 0.00-10.00

Sources:
[Реальные ссылки или локальные файлы. Не требуется цитата для самой новой
гипотезы, но должны быть процитированы механизмы, на которых она основана.]
```
