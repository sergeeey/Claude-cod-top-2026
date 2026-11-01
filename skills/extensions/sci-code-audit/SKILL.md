---
name: sci-code-audit
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [REVIEWED: 2026-11-01]
  Аудит научного кода в 10 слоях: отвечает на вопрос, можно ли доверять коду, который породил
  эти результаты. Ищет тихие fallback'и, нарушенные инварианты, невалидные контроли, проблемы
  происхождения данных, статистической интерпретации, расхождения документации и кода,
  воспроизводимости. Смежен с аудитом методологии исследования и code-materiality (сортировка багов).
  Триггеры: /sci-code-audit, «code audit», «найди что ещё упустили», «audit code», «code hardening»,
  «trust the code», «аудит кода», «могли упустить», «что ещё проверить», «layers of risk»,
  «scientific code review», «audit pipeline code», «code maturity», «research-prototype to production»,
  «audit hardened».
effort: high
tokens: ~1200
triggers: [/sci-code-audit, "code audit", "найди что ещё упустили", "audit code", "code hardening", "trust the code", "аудит кода", "могли упустить", "что ещё проверить", "layers of risk", "scientific code review", "audit pipeline code"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : sci-code-audit
TL;DR  : 10-слойный аудит доверия к научному коду — что ещё мы могли упустить?
Вызов  : /sci-code-audit, "что ещё проверить", "audit code", "code hardening"
НЕ для : Общего code review без активного scientific pipeline / gate
-->

# Scientific Code Audit — 10 Layers of Trust (+ Layer 0)

## Суть

Внешний аудитор нашёл баги. Хорошо. Но это значит: **что ещё не проверено?**

Типичная ошибка: исправить найденные баги и считать, что всё ок. На самом деле
каждый найденный баг — сигнал о целом классе рисков, который мог не проверяться.

Этот скил проводит **10-слойный аудит доверия** к научному коду.

**Троица скилов:**
- `code-materiality` — "этот баг влияет на active pipeline?" (triage)
- `sci-code-audit` — "коду можно доверять?" (полный audit)

---

## Когда активировать

- Получили внешний code audit / review
- Перед blind test или submission
- После быстрого роста репозитория (prototype → research software)
- Когда хочешь сказать "результаты подтверждены" внешнему рецензенту
- Нужен ответ: "что ещё могли упустить?"

---

## Что нужно от пользователя

1. **Активный pipeline** — entry script + key functions
2. **Версия/этап** — какие результаты проверяем (напр., release v1.2 / experiment 3)
3. **Список уже найденных багов** — если есть
4. **Главный claim** — что именно утверждаем (напр., "метод A в 3× лучше baseline, p<0.001")

---

## 10 Слоёв Аудита

### Layer 0 — Stop the Spread
**Пока аудит не завершён:** не расширяем claims, не начинаем Gate N+1, не пишем "всё подтверждено".

---

### Layer 1 — Active Pipeline Materiality
Какие файлы **реально** участвуют в текущем gate/версии?

Создать call graph:
```
entry_script → operator_construction → eigensolver → metrics → aggregation → report
```

Используй `/code-materiality` для тriage конкретных найденных багов.

---

### Layer 2 — Silent Fallbacks
**Самый опасный слой.** Ищи все места где код молча делает не то:

```python
# Паттерны для поиска:
grep -rn "if.*small\|if.*empty\|if.*None\|except.*pass\|except.*continue"
grep -rn "return full_spectrum\|return default\|return \[\]"
grep -rn "np.nan_to_num\|fillna(0)\|replace.*nan"
```

Категории silent fallbacks:
- Empty data → full data (весь спектр вместо окна)
- NaN → 0 (маскирует провал)
- Exception → continue (пропуск кейса без записи)
- Missing field → default value (неверный параметр)
- Failed metric → skip (пропуск в агрегации)
- Small sample → full spectrum (игнорирование условия)

Для каждого найденного fallback: **проверить что активный pipeline не попадает в эту ветку молча**.

---

### Layer 3 — Metrics & Normalization Audit
Для каждой метрики в активном pipeline:

| Вопрос | Проверить |
|--------|-----------|
| Что именно считается? | Код vs README vs paper |
| На каких eigenvectors? | Весь спектр? Окно? Какое? |
| Как фильтруются NaN? | `skipna=True`? Молча? |
| Как агрегируются seeds/families/sizes? | mean vs median vs ratio |
| Threshold обоснован? | Почему 2×? Почему p<0.05? |

Ключевые различия которые меняют вывод:
- `mean(ratio)` vs `ratio(means)` — могут отличаться в 2-3×
- Plain IPR vs metric-weighted IPR
- Central window vs full spectrum
- Biased vs unbiased estimator

---

### Layer 4 — Core Computation Stability
> ⚠️ Слой специфичен для домена. Адаптируй вопросы под свой тип вычислений.

**Для матричной физики / спектрального анализа:**
```python
# Проверить в eigensolver:
# 1. dense vs sparse (eigsh vs eigh)
# 2. which="SM" vs sigma=0 — разные результаты!
# 3. Сортировка eigenvalues после вызова
# 4. Degeneracies — как обрабатываются?
# 5. Complex eigenvectors — берётся |ψ|²?
# 6. Нормировка eigenvectors
# 7. Повторяемость: один seed → один результат?
```

**Для ML / статистики:** numerical precision, gradient overflow, batch size effects.
**Для симуляций:** time step stability, boundary conditions, convergence criteria.
**Для обработки данных:** encoding consistency, datetime parsing, join key types.

---

### Layer 5 — Data/Operator Invariants
> ⚠️ Примеры ниже — для физических операторов. Замени на invariants своего домена.

Для каждого ключевого объекта — **автотесты инвариантов**:

```python
# Физика: Hermitian operator
assert np.allclose(H, H.conj().T)          # Hermitian
assert np.all(np.isreal(eigenvalues))       # real eigenvalues
assert not np.any(np.isnan(H))             # no NaN
assert H.shape == (N, N)                    # correct dimension

# ML: model output
assert 0 <= probabilities.all() <= 1       # valid probabilities
assert not np.any(np.isnan(output))        # no NaN in predictions

# Data pipeline: schema
assert set(df.columns) == EXPECTED_COLUMNS
assert df['id'].is_unique
```

Если эти тесты не запускаются автоматически → **слепая зона**.

---

### Layer 6 — Control / Baseline Validity
**Важно:** negative controls и baseline сами могут быть неправильно реализованы.

**Принцип:** каждый control должен проверять ровно то, что заявлено — не больше, не меньше.

**Общие вопросы для любого домена:**
- Control действительно отличается от experimental условия?
- Control имеет те же invariants (shape, dtype, range)?
- Control не ломает ничего лишнего?
- Результаты control и experimental логично отличаются?

**Пример для физики (адаптируй для своего домена):**
```python
# scrambled_geometry должна менять топологию, а не только relabel узлы:
scrambled = make_scrambled(H)
assert not np.allclose(scrambled, H)          # реально изменилась
assert np.allclose(scrambled, scrambled.conj().T)  # всё ещё Hermitian
# Проверь: P·H·Pᵀ — это НЕ scrambling, это просто relabeling
```

---

### Layer 7 — Data Provenance
Результаты в отчёте соответствуют актуальным данным?

Проверить:
```bash
# Даты файлов
ls -la results/<run_id>/
stat reports/final_report.md

# Нет ли старых файлов в новом отчёте
grep -n "run_directory\|results_path" report_generator.py

# Полнота: все cases присутствуют?
python -c "import json; d = json.load(open('results.json')); print(len(d), 'cases')"
```

Риски:
- Старый файл попал в новый отчёт (по дате)
- Частичный batch смешался с полным
- Duplicate/missing case IDs
- W=0 и W=20 метки перепутаны

---

### Layer 8 — Statistical Interpretation
Даже верный код может дать слабый вывод:

| Claim | Что проверить |
|-------|--------------|
| "3× лучше" | mean of ratios или ratio of means? weighted? |
| "p<0.001" | тест на правильных данных? multiple comparisons? |
| "consistent across sizes" | независимы ли size bins? |
| "family contrast" | N families достаточно? CI рассчитан? |
| "2× threshold" | откуда именно это число? |

---

### Layer 9 — Documentation/Code Mismatch
```bash
# Создать список claims из README/docs
# Для каждого claim найти код который его реализует
# Сравнить

grep -n "IPR\|r-stat\|scrambled\|negative control" README.md
# → проверить в коде
```

Типичные расхождения:
- README: "metric-corrected IPR" → code: plain IPR
- README: "scrambled geometry" → code: permutation only
- README: "N=100 seeds" → code: actual N varies by case

---

### Layer 10 — Reproducibility
```bash
# Проверить на чистой машине (или в chroot/docker):
git clone <repo>
pip install -r requirements.txt
python scripts/smoke_test.py  # один маленький тест
python scripts/run_single_case.py --size 50 --W 0 --seed 42
# Сравнить output с ожидаемым
```

---

## Вывод: Rerun Policy

После аудита — строгая политика:

| Если баг... | То... |
|-------------|-------|
| Не в active pipeline | patch + tests, rerun НЕ нужен |
| В вычислении вторичной метрики (не primary result) | recompute только этой метрики |
| В primary calculation (меняет числа) | rerun affected gate / experiment |
| В case selection / windowing / sampling | rerun или пометить provisional |
| В controls / baseline | rerun affected controls |
| В data provenance / aggregation | rerun + verify integrity |

---

## Выходной документ: `CODE_AUDIT_HARDENING.md`

```markdown
# CODE_AUDIT_HARDENING — <Project> / <Stage> / <Date>

## Audit Status: [IN PROGRESS / COMPLETE]

## Layers Checked (10/10)
| Layer | Status | Findings | Action |
|-------|--------|---------|--------|
| 0 — Stop spread | ✅ | Gate N+1 paused | — |
| 1 — Materiality | ✅ | See code-materiality report | ... |
| 2 — Silent fallbacks | ⚠️ | Found: empty-input fallback returns full data | PATCH |
| 3 — Metrics/norms | ✅ | mean vs median confirmed | — |
| 4 — Eigensolver | ✅ | No issues | — |
| 5 — Invariants | ❌ | No auto-tests yet | ADD TESTS |
| 6 — Controls | ⚠️ | scrambled = permutation only | INVESTIGATE |
| 7 — Provenance | ✅ | Files match run dates | — |
| 8 — Statistics | ✅ | CIs calculated | — |
| 9 — Docs/code | ⚠️ | README says metric-IPR, code is plain | CLARIFY |
| 10 — Reproducibility | ❌ | Not tested yet | TEST |

## Overall Verdict — векторный

Общее слово не ставится сразу. Каждый вектор получает свой статус:

| Вектор | Статус | Что проверяет |
|---|---|---|
| implementation_integrity | PASS / FAIL / UNVERIFIED | код делает то, что задумано |
| numerical_integrity | PASS / FAIL / UNVERIFIED | стабильность, инварианты, скрытые fallbacks |
| data_provenance | PASS / FAIL / UNVERIFIED | входы, версии, полнота кейсов |
| statistical_validity | PASS / FAIL / UNVERIFIED | интерпретация, контроли, baseline |
| claim_alignment | PASS / FAIL / UNVERIFIED | вычисляемая величина совпадает с заявленной в результате |
| reproducibility | PASS / FAIL / UNVERIFIED | повтор на чистом окружении даёт те же числа |

Производный итог: `HARDENED` только если все векторы PASS. `STOP` при FAIL в `claim_alignment` или `data_provenance`. Иначе `PROVISIONAL` или `NEEDS_WORK` по остальным векторам. `UNVERIFIED` никогда не считается PASS.

## Rerun Required?
[YES for: X, Y / NO / PROVISIONAL]

## Как измерять качество аудита

- **Known-Defect Recall** — доля заранее известных дефектов, которые найдены.
- **Novel Verified Findings** — новые находки, подтверждённые независимо (история репозитория, тесты, воспроизведение). До проверки они не считаются ни попаданием, ни промахом.

Результаты benchmark сообщать по обеим метрикам раздельно.

## "Антистыдный" чеклист (для внешнего рецензента)
- [ ] Получили внешний audit
- [ ] Не проигнорировали
- [ ] Materiality audit проведён
- [ ] Active pipeline issues отделены от legacy
- [ ] Bugs исправлены
- [ ] Regression tests добавлены
- [ ] Affected results rerun
- [ ] Всё задокументировано в этом отчёте
```

---

## Companion Skills
- `/code-materiality` — Layer 1: triage конкретных багов
- научный методологический аудит — параллельно
- `/tdd-workflow` — Layer 5: добавление invariant tests

## "Artifact Zoo" для кода

Набор тест-кейсов которые код **обязан** правильно обработать. Адаптируй под домен:

**Универсальные (любой проект):**
```python
ARTIFACT_ZOO_UNIVERSAL = [
    "empty_input",         # пустой массив/датасет → NaN или error, не 0
    "single_element",      # N=1, edge case агрегации
    "all_nan_input",       # все значения NaN → explicit error
    "duplicate_ids",       # дубликаты ключей → error, не silent overwrite
    "missing_ids",         # отсутствующие ключи → warn, не silent skip
    "max_size_input",      # очень большой input → no OOM crash
    "known_trivial",       # тривиальный кейс с аналитическим ответом
]
```

**Для матричной физики (пример):**
```python
ARTIFACT_ZOO_PHYSICS = [
    "identity_matrix",     # IPR = 1.0 (полная локализация)
    "uniform_vector",      # IPR = 1/N (полная делокализация)
    "non_hermitian",       # должен raise error
    "goe_matrix",          # known level statistics
    "permuted_matrix",     # invariants preserved under P·H·Pᵀ
]
```

**Для ML / классификации (пример):**
```python
ARTIFACT_ZOO_ML = [
    "all_same_class",      # degenerate dataset → warn
    "perfectly_separable", # F1=1.0 → check for data leakage
    "random_labels",       # F1 ≈ baseline → sanity check
    "adversarial_input",   # out-of-distribution → не crash
]
```
