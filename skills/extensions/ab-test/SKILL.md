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
  Validates experiment integrity (SRM at 3 levels, novelty effect, peeking), computes
  two-proportion z-test with CI (+ Fisher exact for low counts), checks MCID
  (practical significance ≠ statistical), multiple comparisons correction,
  and gives a Ship/Extend/Stop/Investigate verdict with evidence markers.
  Integrates with rules/estimand-ops.md — MCID required before analysis.
  Triggers: /ab-test, a/b test, проанализируй эксперимент, результаты теста,
  split test, experiment results, A/B анализ, significance, конверсия.
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-06-12]
effort: medium
tokens: ~600
---

# /ab-test — A/B Test Analysis

> **No integrity, no inference.**
> Если рандомизация или логирование сломаны — статистический вывод запрещён независимо от p-value.

## Когда использовать

- Есть результаты рандомизированного эксперимента (A/B, A/A, multivariate)
- Нужно решение: пускать в прод / продлить / остановить
- Требуется доказуемость с evidence markers ([VERIFIED-REAL])

**НЕ использовать:**
- Для дизайна теста до запуска → `/experiment-design`
- Для observational data без рандомизации → добавить causal layer (rules/estimand-ops.md)
- Для последовательного анализа без pre-registration → секция "peeking guard" ниже

---

## Step 0 — Estimand (до любых расчётов)

Из `rules/estimand-ops.md` — заполнить до просмотра данных:

```
Population:   [кто именно, inclusion/exclusion criteria]
Intervention: [variant — точное описание изменения]
Comparator:   [control]
Endpoint:     [primary metric — конкретная, с единицами]
MCID:         [минимальное практически значимое изменение, напр. +0.5% conversion]
ICE:          [intercurrent events — что делать с drop-outs, технические сбои]
Secondary metrics: [явно перечислить + пометить exploratory если не pre-specified]
```

**Жёсткое правило:** MCID должен быть задан ДО просмотра результатов.
Если MCID неизвестен → остановись, договорись с командой, только потом анализируй.

---

## Step 1 — Integrity Gate

> Пройти все три уровня SRM и оба поведенческих check. Если хоть одна проверка провалена — **STOP, вердикт = INVALID**.

### 1a. Sample Ratio Mismatch (SRM) — три уровня

SRM нужно проверять на каждом уровне отдельно: баг может быть не в рандомизации, а в логировании событий.

```python
from scipy.stats import chisquare

def check_srm(observed_c, observed_v, expected_split=0.5, label=""):
    total = observed_c + observed_v
    exp_c = total * expected_split
    exp_v = total * (1 - expected_split)
    chi2, p = chisquare([observed_c, observed_v], f_exp=[exp_c, exp_v])
    status = "⚠️ SRM DETECTED — STOP" if p < 0.01 else "OK"
    print(f"SRM [{label}]: χ²={chi2:.3f}, p={p:.4f} → {status}")
    return p

# Уровень 1: Assignment (рандомизация при попадании в тест)
p_srm_assign = check_srm(n_assigned_c, n_assigned_v, label="assignment")

# Уровень 2: Exposure (пользователи которые реально увидели вариант)
p_srm_exposure = check_srm(n_exposed_c, n_exposed_v, label="exposure")

# Уровень 3: Analysis population (после фильтров inclusion criteria)
p_srm_analysis = check_srm(n_analysis_c, n_analysis_v, label="analysis")
```

**Интерпретация:**
- SRM на уровне assignment → баг в рандомизации или assignment логике
- SRM на уровне exposure → баг в feature flag / rollout системе
- SRM только на уровне analysis → баг в event logging или post-hoc фильтрации

**Любой SRM p < 0.01 → STOP.** Найти уровень, найти причину, починить до анализа.

### 1b. Novelty Effect Check

- Тест шёл менее 2 полных business cycles (обычно 2 недели)?
- Первые 3 дня показывают аномальный spike в variant?

Если да → разбить данные по неделям. Если week1 >> week2 → novelty effect, нужно продлить.

### 1c. Peeking Guard

Смотрел ли кто-то на p-value до окончания теста и принял решение остановить?

```
Если ДА и тест остановлен при p < 0.05:
  Uncontrolled repeated peeking inflates Type I error well above 0.05 —
  potentially toward ~0.30 depending on monitoring frequency,
  stopping behavior, and total sample size.
  (Точная инфляция зависит от числа просмотров и stopping rule.)

Решение:
  (a) применить sequential correction (mSPRT / alpha-spending function)
  (b) зафиксировать как "exploratory only", не production decision
```

---

## Step 2 — Statistical Test

### 2a. Low-count check (сначала)

```python
# Если ожидаемых событий мало — z-test ненадёжен
# ВАЖНО: n_c, conv_c, n_v, conv_v — введи свои данные здесь
n_c = <n control>
conv_c = <conversions control>
n_v = <n variant>
conv_v = <conversions variant>

rate_c = conv_c / n_c
rate_v = conv_v / n_v
p_pool = (conv_c + conv_v) / (n_c + n_v)  # определяем здесь — нужен и в 2b и в 2d

expected_c_pos = n_c * p_pool
expected_c_neg = n_c * (1 - p_pool)
expected_v_pos = n_v * p_pool
expected_v_neg = n_v * (1 - p_pool)

if min(expected_c_pos, expected_c_neg, expected_v_pos, expected_v_neg) < 5:
    print("⚠️ Low expected counts (<5 per cell) — use Fisher exact or Bayesian")
    USE_FISHER = True
else:
    USE_FISHER = False
```

### 2b. Two-proportion z-test (если USE_FISHER = False)

```python
import numpy as np
from scipy import stats

# n_c, conv_c, n_v, conv_v, rate_c, rate_v, p_pool — определены в 2a
lift_rel = (rate_v - rate_c) / rate_c
lift_abs = rate_v - rate_c

# Two-proportion z-test (pooled SE для p-value)
se = np.sqrt(p_pool * (1 - p_pool) * (1/n_c + 1/n_v))
z = (rate_v - rate_c) / se
p_value = 2 * (1 - stats.norm.cdf(abs(z)))  # two-tailed

# 95% CI (unpooled SE для интервала)
se_ci = np.sqrt(rate_c*(1-rate_c)/n_c + rate_v*(1-rate_v)/n_v)
ci_low  = lift_abs - 1.96 * se_ci
ci_high = lift_abs + 1.96 * se_ci

print(f"Control:  {rate_c:.4f} ({conv_c}/{n_c})")
print(f"Variant:  {rate_v:.4f} ({conv_v}/{n_v})")
print(f"Lift:     {lift_rel:+.2%} rel ({lift_abs:+.4f} abs)")
print(f"p-value:  {p_value:.4f}")
print(f"95% CI:   [{ci_low:+.4f}, {ci_high:+.4f}]")
```

> **CI vs p-value (не баг — корректно):** p-value считается на *pooled* SE (под H₀: p₁=p₂),
> а 95% CI — на *unpooled* SE (оценка реальной разности). У границы значимости они могут
> слегка расходиться (CI включает 0 при p чуть < 0.05, или наоборот). Это ожидаемо:
> p-value — для решения о H₀, CI — для величины эффекта. Не «подгонять» один под другой.

### 2c. Fisher exact (если USE_FISHER = True)

```python
from scipy.stats import fisher_exact
from statsmodels.stats.proportion import proportion_confint

odds_ratio, p_fisher = fisher_exact([[conv_c, n_c - conv_c],
                                      [conv_v, n_v - conv_v]])
ci_c = proportion_confint(conv_c, n_c, method='wilson')
ci_v = proportion_confint(conv_v, n_v, method='wilson')
print(f"Fisher p: {p_fisher:.4f}")
print(f"Wilson CI control:  {ci_c}")
print(f"Wilson CI variant:  {ci_v}")
```

### 2d. Power Check (если p ≥ α)

```python
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

mcid = <твой MCID как абсолютная разница>
# Cohen's h — корректный effect size для двух пропорций
# (точнее приближения mcid/√(p(1−p)); h = 2·arcsin√p1 − 2·arcsin√p2)
effect_size = proportion_effectsize(rate_c + mcid, rate_c)
# ВАЖНО: параметр называется nobs1 (не n_obs) — иначе TypeError
power = NormalIndPower().power(effect_size, nobs1=min(n_c, n_v), alpha=0.05)
print(f"Power для MCID={mcid}: {power:.2f}")
# power < 0.80 → тест был underpowered, нельзя делать вывод о null
```

### 2e. Multiple Comparisons Correction

Если тестировались несколько метрик или несколько вариантов:

**Проблема:** при 10 метриках вероятность хотя бы одного ложно-позитивного
результата ≈ 1 − 0.95¹⁰ = 40% при α=0.05.

**Правило:**
- Primary metric: pre-specified, без коррекции.
- Secondary metrics (pre-specified): применить Holm-Bonferroni.
- Secondary metrics (post-hoc): пометить `[EXPLORATORY]`, не для production decisions.
- Multiple variants (k вариантов): скорректировать α = 0.05 / (k − 1).

```python
from statsmodels.stats.multitest import multipletests

# p_values — список p-value для pre-specified secondary метрик
p_values = [p_metric1, p_metric2, p_metric3]
reject, p_corrected, _, _ = multipletests(p_values, method='holm')
for i, (r, pc) in enumerate(zip(reject, p_corrected)):
    print(f"Metric {i+1}: p_corrected={pc:.4f} → {'REJECT H0' if r else 'FAIL TO REJECT'}")
```

---

## Step 3 — Guardrail Metrics

Для каждой guardrail metric (revenue, latency, retention, error rate):

| Metric | Control | Variant | Δ | Статус |
|---|---|---|---|---|
| Primary metric | X | Y | +Z% | ✅/❌ |
| Revenue per user | X | Y | Δ | ✅/⚠️/❌ |
| Page load time | X | Y | Δ | ✅/⚠️/❌ |
| Error rate | X | Y | Δ | ✅/⚠️/❌ |

**⚠️** = деградация ≥ MCID guardrail → флаг для Investigate

---

## Step 4 — Verdict

| Условие | Вердикт |
|---|---|
| p < α AND lift_abs ≥ MCID AND все guardrails OK | ✅ **SHIP** |
| p < α AND lift_abs < MCID (статистически значимо но не практически) | ⚠️ **STOP** — ниже MCID |
| p ≥ α AND power ≥ 0.80 | ⛔ **STOP** — null confirmed, эффекта нет |
| p ≥ α AND power < 0.80 | ⏳ **EXTEND** — underpowered, продолжить |
| p < α AND guardrail деградировал | 🔍 **INVESTIGATE** — трейдофф требует решения |
| SRM detected (любой уровень) | 🚫 **INVALID** — устранить до решения |
| Peeking без коррекции | 🚫 **INVALID** — пометить exploratory или применить mSPRT |

---

## Step 5 — Отчёт с Evidence Markers

```markdown
## A/B Test: [название]
Период: [дата старт — дата конец]
Данные: [источник — [VERIFIED-REAL] с URL/путём к данным]

### Integrity
- SRM assignment:  p=X → OK / ⚠️ DETECTED [VERIFIED-REAL]
- SRM exposure:    p=X → OK / ⚠️ DETECTED [VERIFIED-REAL]
- SRM analysis:    p=X → OK / ⚠️ DETECTED [VERIFIED-REAL]
- Novelty effect:  [проверен / не применимо]
- Peeking:         [не было / был → скорректирован mSPRT / помечен exploratory]
- Low counts:      [N/A / Fisher exact использован]

### Results
- Control: {rate_c:.4f} (n={n_c})
- Variant: {rate_v:.4f} (n={n_v})
- Lift: {lift_rel:+.2%} | 95% CI: [{ci_low:+.4f}, {ci_high:+.4f}]
- p-value: {p_value:.4f} (α=0.05) [VERIFIED-REAL]
- MCID: {mcid} → EXCEEDED / NOT REACHED
- Multiple comparisons: [N/A / Holm corrected / secondary marked exploratory]

### Guardrails
[таблица из Step 3]

### Verdict: [SHIP / EXTEND / STOP / INVESTIGATE / INVALID]
Reason: [одно предложение]

### What This Does NOT Mean
1. Не доказывает причинно-следственную связь если A/B не был полностью рандомизирован
2. Не гарантирует результат на 100% трафика (Simpson's paradox по сегментам)
3. Не применимо для пользователей вне inclusion criteria теста
4. Secondary / post-hoc метрики помечены [EXPLORATORY] — не для production decisions
```

---

## Интеграция с нашим стеком

- Estimand → `rules/estimand-ops.md` (MCID, ICE, population definition)
- Evidence markers → `rules/evidence-markers.md` ([VERIFIED-REAL] обязателен)
- Skeptic trigger: если lift = round number (50%, 100%) → auto-trigger rule 4
- Causal layer: если данные не из рандомизированного эксперимента → остановись,
  требуется DAG + identifiability check (`rules/estimand-ops.md` §Causal Layer)

**Принцип всего скилла:**
> *No integrity, no inference.*
