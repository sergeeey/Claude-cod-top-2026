<!-- BSV — Brief Skill View | поиск: BSV
Скил   : ab-test
TL;DR  : Статистически строгий анализ A/B теста с MCID, peeking guard и evidence markers
Вызов  : `/ab-test`, 'проанализируй эксперимент', 'результаты A/B теста'
НЕ для : Дизайна теста до запуска (→ /experiment-design), causality без рандомизации
-->

---
name: ab-test
description: >
  USE when you have A/B test results and need rigorous statistical analysis.
  Validates experiment integrity (SRM, novelty effect, peeking), computes
  two-proportion z-test with CI, checks MCID (practical significance ≠ statistical),
  and gives a Ship/Extend/Stop/Investigate verdict with evidence markers.
  Integrates with rules/estimand-ops.md — MCID required before analysis.
  Triggers: /ab-test, a/b test, проанализируй эксперимент, результаты теста,
  split test, experiment results, A/B анализ, significance, конверсия.
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-06-12]
effort: medium
tokens: ~500
---

# /ab-test — A/B Test Analysis

## Когда использовать

- Есть результаты рандомизированного эксперимента (A/B, A/A, multivariate)
- Нужно решение: пускать в прод / продлить / остановить
- Требуется доказуемость с evidence markers ([VERIFIED-REAL])

**НЕ использовать:**
- Для дизайна теста до запуска → `/experiment-design`
- Для observational data без рандомизации → добавить causal layer (rules/estimand-ops.md)
- Для последовательного анализа без pre-registration → секция "peeking guard" ниже

## Шаг 0 — Estimand (до любых расчётов)

Из `rules/estimand-ops.md` — заполнить до просмотра данных:

```
Population:   [кто именно, inclusion/exclusion criteria]
Intervention: [variant — точное описание изменения]
Comparator:   [control]
Endpoint:     [primary metric — конкретная, с единицами]
MCID:         [минимальное практически значимое изменение, напр. +0.5% conversion]
ICE:          [intercurrent events — что делать с drop-outs, технические сбои]
```

**Жёсткое правило:** MCID должен быть задан ДО просмотра результатов.
Если MCID неизвестен → остановись, договорись с командой, только потом анализируй.

---

## Шаг 1 — Валидация целостности эксперимента

### 1a. Sample Ratio Mismatch (SRM)

```python
from scipy.stats import chi2_contingency
import numpy as np

n_control, n_variant = <число пользователей в каждой группе>
expected_split = 0.5  # или ваш запланированный split

observed = [n_control, n_variant]
expected = [sum(observed) * expected_split, sum(observed) * (1 - expected_split)]
chi2, p_srm = chi2_contingency([[n_control, n_variant],
                                  [expected[0], expected[1]]])[0:2]

if p_srm < 0.01:
    print("⚠️ SRM DETECTED — эксперимент скомпрометирован, анализ ненадёжен")
    # STOP: найти причину (tracking bug, cache, bot traffic) перед продолжением
```

**SRM p < 0.01 → STOP.** Не интерпретировать результаты до устранения.

### 1b. Novelty Effect Check

- Тест шёл менее 2 полных business cycles (обычно 2 недели)?
- Первые 3 дня показывают аномальный spike в variant?

Если да → разбить данные по неделям. Если week1 >> week2 → novelty effect, нужно продлить.

### 1c. Peeking Guard

Смотрел ли кто-то на p-value до окончания теста и принял решение остановить?

```
Если ДА и тест остановлен при p < 0.05 → реальный α ≈ 0.30, не 0.05
Решение: либо применить sequential correction (mSPRT),
          либо зафиксировать как "exploratory only", не production decision
```

---

## Шаг 2 — Статистический анализ

```python
import numpy as np
from scipy import stats

# Данные
n_c = <n control>
conv_c = <conversions control>
n_v = <n variant>
conv_v = <conversions variant>

rate_c = conv_c / n_c
rate_v = conv_v / n_v
lift_rel = (rate_v - rate_c) / rate_c
lift_abs = rate_v - rate_c

# Two-proportion z-test (pooled)
p_pool = (conv_c + conv_v) / (n_c + n_v)
se = np.sqrt(p_pool * (1 - p_pool) * (1/n_c + 1/n_v))
z = (rate_v - rate_c) / se
p_value = 2 * (1 - stats.norm.cdf(abs(z)))  # two-tailed

# 95% Confidence Interval (unpooled для CI)
se_ci = np.sqrt(rate_c*(1-rate_c)/n_c + rate_v*(1-rate_v)/n_v)
ci_low = lift_abs - 1.96 * se_ci
ci_high = lift_abs + 1.96 * se_ci

print(f"Control:  {rate_c:.4f} ({conv_c}/{n_c})")
print(f"Variant:  {rate_v:.4f} ({conv_v}/{n_v})")
print(f"Lift:     {lift_rel:+.2%} abs ({lift_abs:+.4f})")
print(f"p-value:  {p_value:.4f}")
print(f"95% CI:   [{ci_low:+.4f}, {ci_high:+.4f}]")
```

### Power Check (если p ≥ α)

```python
# Достаточно ли было данных чтобы обнаружить MCID?
from statsmodels.stats.power import NormalIndPower

mcid = <твой MCID как абсолютная разница>
effect_size = mcid / np.sqrt(p_pool * (1 - p_pool))
power = NormalIndPower().power(effect_size, n_obs=min(n_c, n_v), alpha=0.05)
print(f"Power для MCID={mcid}: {power:.2f}")
# power < 0.80 → тест был underpowered, нельзя делать вывод о null
```

---

## Шаг 3 — Guardrail Metrics

Для каждой guardrail metric (revenue, latency, retention, error rate):

| Metric | Control | Variant | Δ | Статус |
|---|---|---|---|---|
| Primary metric | X | Y | +Z% | ✅/❌ |
| Revenue per user | X | Y | Δ | ✅/⚠️/❌ |
| Page load time | X | Y | Δ | ✅/⚠️/❌ |
| Error rate | X | Y | Δ | ✅/⚠️/❌ |

**⚠️** = деградация ≥ MCID guardrail → флаг для Investigate

---

## Шаг 4 — Вердикт

| Условие | Вердикт |
|---|---|
| p < α AND lift_abs ≥ MCID AND все guardrails OK | ✅ **SHIP** |
| p < α AND lift_abs < MCID (статистически значимо но не практически) | ⚠️ **STOP** — ниже MCID |
| p ≥ α AND power ≥ 0.80 | ⛔ **STOP** — null confirmed, эффекта нет |
| p ≥ α AND power < 0.80 | ⏳ **EXTEND** — underpowered, продолжить |
| p < α AND guardrail деградировал | 🔍 **INVESTIGATE** — трейдофф требует решения |
| SRM detected | 🚫 **INVALID** — устранить до решения |

---

## Шаг 5 — Отчёт с Evidence Markers

```markdown
## A/B Test: [название]
Период: [дата старт — дата конец]
Данные: [источник — [VERIFIED-REAL] с URL/путём к данным]

### Integrity
- SRM: p={p_srm:.3f} → {'OK' if p_srm >= 0.01 else '⚠️ DETECTED'} [VERIFIED-REAL]
- Novelty effect: [проверен / не применимо]
- Peeking: [не было / был → скорректирован mSPRT]

### Results
- Control: {rate_c:.4f} (n={n_c})
- Variant: {rate_v:.4f} (n={n_v})
- Lift: {lift_rel:+.2%} | 95% CI: [{ci_low:+.4f}, {ci_high:+.4f}]
- p-value: {p_value:.4f} (α=0.05) [VERIFIED-REAL]
- MCID: {mcid} → {'EXCEEDED' if lift_abs >= mcid else 'NOT REACHED'}

### Guardrails
[таблица из шага 3]

### Verdict: [SHIP / EXTEND / STOP / INVESTIGATE]
Reason: [одно предложение]

### What This Does NOT Mean
1. Не доказывает причинно-следственную связь если A/B не был полностью рандомизирован
2. Не гарантирует результат на 100% трафика (Simpson's paradox по сегментам)
3. Не применимо для пользователей вне inclusion criteria теста
```

## Интеграция с нашим стеком

- Estimand → `rules/estimand-ops.md` (MCID, ICE, population definition)
- Evidence markers → `rules/evidence-markers.md` ([VERIFIED-REAL] обязателен)
- Skeptic trigger: если lift = round number (50%, 100%) → auto-trigger rule 4
- Causal layer: если данные не из рандомизированного эксперимента → остановись,
  требуется DAG + identifiability check (`rules/estimand-ops.md` §Causal Layer)
