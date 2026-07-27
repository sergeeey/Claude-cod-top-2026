# Dogfood run — boyko-why-ladder vs 2 blind constructed chains

**Purpose:** real promotion evidence for `maturity: dogfooded` (P2 plan item 16,
`docs/baselines/2026-07-24-plan.md`), per `docs/skill-maturity-criteria.md`.

**Why synthetic here is legitimate (per the criteria doc's own rule):** this
skill's job is to catch a specific failure mode (circular/ongoing-regress
explanation chains) in ANY domain, not to make a claim about the real world.
Two chains were deliberately constructed with a KNOWN correct answer before
the run -- this is unit-testing a checker, the same category as
`boyko-triangle-audit`'s own v1.0.1 changelog entry, just done here as a
fresh, independently-citable run instead of relying on that changelog's
un-cited prose (which is the skill's own file citing itself -- exactly the
evidence-laundering pattern this criteria doc's checklist disallows).

**Method:** a fresh `explorer`-type agent was given only the path to
`skills/extensions/boyko-why-ladder/SKILL.md` and the two chains below, and
instructed to follow the skill's methodology exactly. It was blind to which
chain was designed to pass and which to fail -- no answer key was given.

**Ground truth (designed before the run, not fitted after):**
- Chain A (prime numbers < 10): designed as a legitimate FOUNDATIONAL_STOP --
  closed by definition + exhaustive finite enumeration, no alternative
  possible.
- Chain B (feature-importance "explanation"): designed as textbook circular
  reasoning -- "X is important because its weight is high" / "its weight is
  high because X is important," with zero independent evidence (no ablation,
  no domain theory, no permutation-importance check) introduced at any step.

**Result:** the agent's verdicts matched the designed ground truth exactly on
both chains, and for Chain B it correctly localized the circularity to the
specific step (Ступень 2) rather than only reporting the final label -- this
matters because the skill's own spec requires naming the weakest link, not
just the terminal verdict, and a checker that only gets the final label right
without correctly locating the break would be much weaker evidence. Full
verbatim output below.

---

## Chain A

## Why-Ladder Audit: Множество простых чисел < 10

| # | Нашли | Почему? | Статус | Evidence |
|---|---|---|---|---|
| 1 | Набор {2, 3, 5, 7} | -- (это то, что объясняем) | -- | -- |
| 2 | Определение простого числа + прямая проверка 2..9 | объясняет набор {2,3,5,7} | DERIVED | Ступень 1 текста: "натуральное число >1, делящееся только на 1 и на себя" + перечисление 4=2*2, 6=2*3, 8=2*4, 9=3*3 |

**Обязательная проверка DERIVED:** "Если убрать ступень выше — сколько ДРУГИХ наборов дают тот же результат?" Ответ: ноль — определение простого числа фиксировано конвенцией математики, а перечисление 2..9 конечно и исчерпывающе; при этом определении и этом диапазоне результат единственный, альтернативных наборов, дающих то же самое, не существует.

**Самое слабое звено:** Нет слабого звена — цепочка состоит из одной ступени, которая проверяема прямым вычислением, а не подгонкой.

**Финальный вердикт (дилемма Агриппы):** FOUNDATIONAL_STOP
**Обоснование вердикта:** Закрывающий факт — определение простого числа (конвенция) плюс конечная, полностью проверяемая факторизация каждого из чисел 2–9 (4=2×2, 6=2×3, 8=2×4, 9=3×3). Это не выбор среди альтернатив и не апелляция к авторитету — это замкнутое, конечное перечисление, дающее единственный возможный результат.

**Depth Guard:** 0 нерешённых ступеней — не сработал (цепочка коротка и полностью DERIVED).

**Делегировано hypothesis-arbiter:** нет ступеней с UNKNOWN, делегирование не требуется.

**Уже встречалось в null_results/parked:** не применимо — нет папки эксперимента.

---

## Chain B

## Why-Ladder Audit: Важность признака X в модели

| # | Нашли | Почему? | Статус | Evidence |
|---|---|---|---|---|
| 1 | Признак X получил самый высокий вес важности | -- (это то, что объясняем) | -- | -- |
| 2 | Вес X оказался выше, чем у остальных признаков | объясняет "X самый важный" | FITTED | Ступень 2 текста — это переформулировка Ступени 1 другими словами ("самый важный" ⇔ "вес выше остальных"), не новая причина |
| 3 | X — наиболее важный признак для предсказания в этой предметной области | объясняет "почему вес X выше" | FITTED | Ступень 3 текста — вывод о важности X в домене обоснован ТОЛЬКО тем, что модель присвоила ему высокий вес (Ступень 1/2), после чего это же наблюдение цитируется как причина самого себя |

**Самое слабое звено:** Ступень 2 — уже здесь цепочка становится нечестной: "вес X выше, чем у остальных" не объясняет, ПОЧЕМУ он выше (не указана независимая причина), а просто повторяет наблюдение Ступени 1 другими словами. Ступень 3 усугубляет это, но круг замыкается уже на Ступени 2.

**Финальный вердикт (дилемма Агриппы):** CIRCULAR
**Обоснование вердикта:** Верхняя ступень (3: "X важен в предметной области") тайно объясняется через нижнюю (1: "X получил высокий вес в модели") — а Ступень 1 и есть то самое наблюдение, которое требовало объяснения. Явная циркулярность: вес высокий → потому что X важен → откуда известно, что X важен? → потому что вес высокий. Ни одна ступень не привносит независимое доказательство.

**Depth Guard:** 2 нерешённых (FITTED) ступени без FOUNDATIONAL_STOP — не достиг порога ≥3, но обе ступени уже дисквалифицированы циркулярностью, так что порог Depth Guard здесь избыточен.

**Делегировано hypothesis-arbiter:** нет — обе ступени однозначно классифицированы как FITTED/циркулярные.

**Уже встречалось в null_results/parked:** не применимо — нет папки эксперимента.
