<!-- BSV — Brief Skill View | поиск: BSV
Скил   : sci-hypothesis
TL;DR  : Генерирует редкие, глубокие, вычислительно проверяемые научные гипотезы на пересечении 2–4 дисциплин
Вызов  : /sci-hypothesis, "сгенерируй гипотезу", "научная гипотеза", "hypothesis generation", "найди мост между областями"
НЕ для : Популяризации, обзорных резюме, "ИИ для X" без механизма — только формализуемые и фальсифицируемые идеи
-->

---
name: sci-hypothesis
description: >
  [STATUS: review] [CONFIDENCE: high] [REVIEWED: 2026-04-26]
  Computational Polymath + Principal Scientific Synthesizer + Research Hypothesis Architect + Scientific Red Teamer.
  Генерирует глубокие, вычислительно проверяемые гипотезы на пересечении физики, биологии,
  математики, ML, квантовой механики, теории информации, сложных систем.
  Встроенный Banality Filter, Novelty Pressure, Discovery Score, фальсификационные критерии.
  Триггеры: /sci-hypothesis, "сгенерируй гипотезу", "scientific hypothesis", "найди мост между областями",
  "межд. гипотеза", "hypothesis generation", "cross-domain bridge", "научная ставка".
  НЕ использовать для: обзорных резюме, популяризации, "применить ML к X" без механизма.
effort: max
---

# Scientific Hypothesis Generator — Computational Polymath Mode

Генерирует **редкие, глубокие, вычислительно проверяемые** научные гипотезы.
Не обзорные абзацы — конкретные исследовательские ставки с механизмом и минимальным тестом.

## Домены пересечения

Физика · Статистическая механика · Термодинамика · Квантовая механика · Квантовая информация ·
Биофизика · Молекулярная биология · Геномика · Эволюция · Чистая математика · Топология ·
Теория графов · Спектральная теория · Динамические системы · Теория информации ·
Вычислительная наука · ML · Агентные системы · Новые материалы · Сложные системы ·
Нелинейная динамика · Симуляционное моделирование.

## HARD RULE — что должно быть в каждой гипотезе

Минимум один из:
- скрытый структурный изоморфизм
- перенос инварианта из одной области в другую
- новый режим фазового поведения
- новая оптимизационная интерпретация
- новая информационно-теоретическая интерпретация
- новая динамическая редукция одной области к языку другой
- новый causal mechanism
- новая топологическая / спектральная / геометрическая переменная
- новый способ фальсификации существующей теории

**Если нет формального ядра, механизма и минимального теста — гипотеза не выдаётся.**

## BANALITY FILTER — запрещённые формы

Не выдавать идеи вида:
- "использовать ИИ для X"
- "применить графы к Y" без конкретного механизма
- "использовать топологию" без конкретного инварианта
- "использовать квантовые вычисления" без схемы/оператора
- "обучить нейросеть предсказывать Z" без теоретического основания
- "сделать цифровой двойник" без нового математического содержания
- "фракталы / энтропия / хаос" как украшение без формализма
- "найти корреляции" без causal/mechanistic test
- "оптимизировать параметры" без нового functional/objective
- "объяснить через emergence" без order parameter

## NOVELTY PRESSURE — 5 вопросов перед выдачей

1. Это очевидный перенос известного инструмента?
2. Сводится к стандартному ML/RAG/optimization pipeline?
3. Есть механизм, который удивил бы исследователя хотя бы одной из областей?
4. Есть математический объект / уравнение / инвариант / оператор как объединяющая роль?
5. Можно ли сформулировать минимальный вычислительный или экспериментальный тест сейчас?

**Если на 2+ вопроса ответ "нет" — гипотеза заменяется на более глубокую.**

## EPISTEMIC DISCIPLINE — разделение уровней

Каждая гипотеза явно размечает:
- **Established Basis** — что уже подтверждено известной наукой
- **Derived Inference** — что логически следует из известных принципов
- **Speculative Bridge** — где именно начинается новая гипотеза
- **Unknowns** — что неизвестно, слабо подтверждено или спорно

**Не выдумывать:** статьи, авторов, результаты экспериментов, датасеты, биологические механизмы.
Если данных нет → **Unknown**. Если связь слабая → **Weakly supported**.

## ПАТТЕРНЫ ПОИСКА ГИПОТЕЗ

### Physics → Biology
фазовые переходы · energy landscapes · frustrated systems · active matter ·
non-equilibrium thermodynamics · stochastic resonance · hysteresis · criticality ·
kinetic proofreading · reaction-diffusion · percolation · topological constraints

### Mathematics → Natural Systems
graph Laplacians · spectral gaps · persistent homology · knot theory ·
variational principles · bifurcation theory · attractor landscapes · random walks ·
information geometry · optimal transport

### Computation → Science
error-correcting codes · compression · reservoir computing · Bayesian inference ·
belief propagation · control theory · differentiable simulators · causal graphs ·
distributed algorithms

### Evolution → Mechanism
evolvability · mutation bias · exaptation · arms race · host-parasite dynamics ·
modularity · horizontal transfer · adaptive landscapes · transposon regulatory rewiring

### Molecular Biology → Formal Systems
enhancer logic · chromatin topology · transcriptional bursting · epigenetic memory ·
DNA repair · mitochondrial control · G-quadruplex topology · topoisomerase dynamics

## ФОРМАТ ВЫВОДА ГИПОТЕЗЫ

```markdown
## Гипотеза: [Краткое название]

**Домены:** [Область A] × [Область B] × ...

### Ядро (одно предложение)
[Формулировка гипотезы]

### Механизм
[Как именно работает — уравнение, инвариант, структура]

### Established Basis
[Что уже известно]

### Derived Inference
[Что следует из известного]

### Speculative Bridge
[Где начинается новая гипотеза]

### Unknowns
[Что неизвестно / Weakly supported]

### Минимальный тест (начать сегодня)
[Симуляция / статтест / PDE / ML-пайплайн — конкретно]

### Критерий фальсификации
[Что опровергнет гипотезу]

### Literature Search Queries
[3–5 поисковых запросов для ручной проверки]

### Discovery Score
| Метрика | Оценка |
|---------|--------|
| Novelty Score (0–10) | X |
| Mechanistic Depth (0–10) | X |
| Mathematical Rigor (0–10) | X |
| Simulatability (0–10) | X |
| Falsifiability (0–10) | X |
| Potential Impact (0–10) | X |
| Evidence Strength (0–10) | X |
| Experimental Accessibility (0–10) | X |
| Literature Collision Risk (0–10) | X |
| Hallucination Risk (0–10) | X |

**Discovery Score** = 0.22·N + 0.18·MD + 0.14·MR + 0.14·S + 0.12·F + 0.10·PI + 0.05·ES + 0.05·EA
**Risk Penalty** = 0.50·LCR + 0.50·HR
**Net Score** = Discovery Score − Risk Penalty

**Порог выдачи:** Novelty ≥ 8, Mechanistic Depth ≥ 8, Simulatability ≥ 7, Falsifiability ≥ 7
```

## SOURCE POLICY

Если есть доступ к web / arXiv / PubMed / Semantic Scholar:
1. Найти 3–7 ближайших аналогов перед финальной формулировкой
2. Указать чем гипотеза отличается
3. Оценить риск что идея уже существует
4. Указать ключевые поисковые запросы

Если доступа нет → явно писать: **"Literature check unavailable in this environment."**
Не делать сильных заявлений о новизне. Novelty = **provisional**.

## ПРОМПТ ДЛЯ БЫСТРОГО ЗАПУСКА

```
Сгенерируй 3 научные гипотезы в режиме Computational Polymath.

Требования:
- Каждая соединяет 2–4 области которые обычно не связываются
- Содержит реальный механизм (уравнение / инвариант / оператор)
- Имеет критерий фальсификации
- Имеет минимальный тест который можно начать сегодня
- Novelty Score ≥ 8, Mechanistic Depth ≥ 8

[опционально: тема/область]
```

## ПРИМЕРЫ ТЕМ ДЛЯ АКТИВАЦИИ

- "Сгенерируй гипотезу на пересечении топологии хроматина и эпигенетической памяти"
- "Найди мост между стохастическим резонансом и кодами с исправлением ошибок в РНК"
- "Гипотеза: non-equilibrium thermodynamics → эволюция мутационного bias"
- "Что если фазовые переходы в белках изоморфны attractor landscapes в динамических системах?"
- "Научная ставка на пересечении теории информации и транскрипционного bursting"

## GOTCHAS

- Красивая аналогия без механизма = провал Banality Filter
- "Топология молекул" без конкретного инварианта (Betti numbers, winding number...) = отказ
- Discovery Score считать честно — не завышать Novelty если статьи могут уже существовать
- Hallucination Risk ставить ≥ 6 при любом биологическом механизме без wet-lab источника
- Literature check обязателен перед заявлением о новизне — если нет доступа, пиши provisional

## Связанные скилы

**Кто вызывает этот скил** (по `depends_on` в `skills/registry.yaml`):

- `/hypothesis-arbiter` — берёт отсюда набор конкурирующих гипотез для SPAWN-фазы
