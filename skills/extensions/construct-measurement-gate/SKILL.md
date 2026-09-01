---
name: construct-measurement-gate
description: >
  Специализированный диагностический аудит связи между научным construct и
  системой его измерения: construct ambiguity, proxy gaps, measurement
  artefacts, common-method effects, measurement non-invariance, альтернативные
  измерительные объяснения, независимые способы проверки observed effect.
  С v0.2 НЕ выносит финальный научный вердикт сам — это diagnostic specialist,
  не evaluator, per real blind-benchmark evidence (см. CONFIDENCE). Финальную
  интерпретацию (влияет ли measurement uncertainty на итоговый вывод, ослабить/
  сохранить/отклонить claim) явно передаёт downstream adjudication layer
  (эксперту, `hypothesis-arbiter`, `boyko-scientific-consortium`, `skeptic`).
  Triggers: /construct-measurement-gate, измерительная тень, construct
  validity, что мы на самом деле измеряем, proxy gap, common-method effect,
  measurement invariance, H_REAL vs H_MEASURE, measurement risk profile.
  [STATUS: dogfooded для v0.1-as-evaluator роли (blind benchmark) и для
  v0.2-as-diagnostician архитектуры (3 реальных dogfood, разные домены);
  described для нового Step 2a (Reference Standard Audit) — построен
  evidence-based на n=3, но сам ЕЩЁ НЕ прогнан отдельно на реальном кейсе]
  [CONFIDENCE: реальный blind-benchmark, 2026-08-30
  — независимый curator (не видевший gate) собрал 10 реальных, задокументированных
  через WebSearch кейсов (3 confirmed-failure / 3 clean / 2 deceptive-control /
  2 ambiguous, 6 из 10 не учебниковые: Google Flu Trends, пульсоксиметрия,
  Google Books n-grams, doubly labeled water, RECOVERY dexamethasone, GPS в
  футболе, urban heat island, "3 млрд птиц", teacher value-added, IAT). Arm A
  (сильный baseline, свободная экспертная проза) vs Arm B (v0.1 как gate-с-
  финальным-Verdict) прогнаны независимо, слепая адъюдикация третьим агентом.
  Результат: sensitivity 3/3 и specificity 3/3 у ОБОИХ плеч; Treatment
  систематически сильнее в H_REAL/H_MEASURE построении, поиске независимых
  measurement channels и проектировании discriminating test (10/10 explicit
  тестов vs 4/10 у baseline); НО Treatment проиграл ОДИН, но самый весомый
  кейс (Urban Heat Island, deceptive control) — его же собственная дисциплина
  "не усиливай claim пока H_MEASURE не исключён ИМЕЮЩИМИСЯ данными" не дала
  ему сделать вывод там, где baseline, рассуждая свободно, дал верный ответ,
  независимо реконструировав реальный опубликованный механизм (Fall 2011,
  min/max canceling trends). Адъюдикатор дословно: "roughly comparable
  overall... a combined workflow — R2's channel-hunting and test design,
  gated by R1's verdict calibration — would outperform either alone."
  Формальные Pass Criteria (см. registry.yaml) НЕ выполнены целиком (verdict
  quality не показал явного превосходства) → EXPAND отклонён. Вместо этого —
  архитектурный пивот: v0.2 убирает автоматический Verdict (Step 5→Step 8/9,
  advisory-only recommendations, никогда REPLACE/REDEFINE напрямую) и явно
  передаёт финальное решение downstream. Сама v0.2-архитектура ЕЩЁ НЕ
  прогнана отдельным бенчмарком — это ответ на находку, не подтверждённое
  улучшение. Решение по этому этапу: MERGE/SPECIALIZE, не EXPAND. Новый blind
  holdout сознательно НЕ запущен сейчас — собирать evidence через реальное
  использование, не через синтетический бенчмарк на этом же вопросе ("не
  чинить prompt до победы", максимум одна ревизия за цикл, уже использована).
  Три реальных dogfood-прогона v0.2 (2026-08-31, все независимо
  фактчекнуты/спроектированы пользователем): (1) потребительские трекеры сна
  vs PSG — 9.1/10, нашёл и закрыл 4 калибровочные проблемы (categorical-
  overclaim в H_MEASURE, thermometer principle для Content Validity,
  device-performance-vs-invariance conflation, рискованные манипуляции вместо
  безопасных повторных измерений), плюс первая находка potential-нового
  epistemic объекта — reference standard (PSG) сам является измерительной
  системой, не REAL PHENOMENON; (2) ИИ-диагностика меланомы vs консенсус
  патологов (намеренно медицинский домен, острее: каппа 0.27-0.87, полное
  согласие 8 экспертов только в 53.5% случаев) — тот же паттерн, n=2, гейт
  сработал чисто, новых калибровок не потребовалось; (3) автоматическое
  оценивание эссе vs человек-рейтер (намеренно НЕ медицинский домен — тест на
  обобщаемость) — тот же паттерн третий раз (kappa 0.58-0.71), n=3 в трёх
  разных доменах, ПЛЮС гейт корректно НЕ слил его с отдельно найденной,
  структурно другой находкой (Perelman/BABEL construct-contamination gaming
  — уже покрыта существующим Step 3 механизмом, новой capability не
  потребовала). n=3 across 3 domains достиг заявленного в pearl_registry
  порога → построен Step 2a (Reference Standard Audit): явное разделение
  REAL/LATENT PHENOMENON на reference-ветвь и target-ветвь,
  H_TARGET_ERROR/H_REFERENCE_ERROR/H_CONSTRUCT_MISMATCH как три раздельные
  модели вместо автоматического "target неправ". Pearl-запись закрыта
  (`pearl_registry/INDEX.md`, status: resolved, built into v0.3).]
  НЕ для: вынесения финального научного вердикта самостоятельно (это
  downstream adjudication layer — эксперт, `hypothesis-arbiter`,
  `boyko-scientific-consortium`, `skeptic`), атаки самой гипотезы (→
  /sci-evidence), аудита причинной идентифицируемости (→
  rules/estimand-ops.md), аудита кода (→ /sci-code-audit).
effort: medium
tokens: ~1400
triggers: [/construct-measurement-gate, "измерительная тень", "construct validity", "что мы на самом деле измеряем", "proxy gap", "common-method effect", "measurement invariance", "H_REAL vs H_MEASURE", "measurement risk profile"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : construct-measurement-gate
TL;DR  : v0.3, diagnostic specialist (не evaluator) — construct/measurement аудит + Reference Standard Audit, финальный verdict отдаёт downstream adjudication layer
Вызов  : /construct-measurement-gate, измерительная тень, что мы на самом деле измеряем, proxy gap
НЕ для : Вынесения финального вердикта самому (→ downstream adjudicator), атаки гипотезы (→ /sci-evidence), причинной идентифицируемости (→ estimand-ops)
Выход  : Construct Contract → Measurement Chain → Reference Standard Audit (если применимо) → H_REAL/H_MEASURE → Construct Validity Checks → Measurement Invariance → Independent Measurement Challenge → Discriminating Test → Measurement Risk Profile → Advisory Recommendation → Adjudication Handoff
-->

# construct-measurement-gate — v0.3 (Diagnostic Specialist + Reference Standard Audit)

## Purpose

Проведи специализированный аудит связи между научным construct и системой
его измерения. **Этот модуль не выносит окончательный научный verdict сам —
per реальный blind-benchmark (см. CONFIDENCE во frontmatter), он
систематически сильнее в диагностике (H_REAL/H_MEASURE, независимые каналы,
discriminating test), чем в финальной калибровке вывода.** Его задача —
выявить:
- construct ambiguity;
- proxy gaps;
- measurement artefacts;
- common-method effects;
- measurement non-invariance;
- alternative measurement explanations;
- независимые способы проверки observed effect.

Финальная интерпретация должна учитывать результаты этого аудита вместе с:
- общей evidence base;
- causal structure;
- domain knowledge;
- competing explanations;
- качеством источников;
- независимым экспертным или adjudication layer (`hypothesis-arbiter`,
  `boyko-scientific-consortium`, `skeptic`, или человек).

```text
Expert reasoning
      ↓
Construct-Measurement Gate  (этот модуль — diagnostician)
      ↓
H_REAL / H_MEASURE
Proxy gaps
Measurement risks
Independent measurement tests
      ↓
Expert / Independent Adjudicator  (не этот модуль — judge)
      ↓
Final scientific verdict
```

## Input

### Scientific Claim
[УТВЕРЖДЕНИЕ]

### Target Construct
[ЧТО ИССЛЕДОВАНИЕ СЧИТАЕТ, ЧТО ИЗМЕРЯЕТ]

### Operationalization
[КАК CONSTRUCT ПРЕВРАЩЁН В ИЗМЕРЯЕМУЮ ВЕЛИЧИНУ]

### Instrument / Assay / Sensor / Questionnaire / Model
[ИНСТРУМЕНТ]

### Raw Signal / Data
[ЕСЛИ ИЗВЕСТНО]

### Processing Pipeline
[ЕСЛИ ИЗВЕСТНО]

### Final Metric
[ПОКАЗАТЕЛЬ]

### Population / Groups / Conditions
[КОНТЕКСТ]

### Evidence Package
[СТАТЬИ / ДАННЫЕ / ОПИСАНИЕ]

---

## Step 1 — Construct Contract

Определи target construct максимально точно. Укажи:

### Construct
...
### Что входит в construct
...
### Что не входит
...
### Соседние constructs, с которыми его можно спутать
...
### Какую научную роль ему приписывает исследование
...

Если construct определён неоднозначно, зарегистрируй `CONSTRUCT_AMBIGUITY`.
Не пытайся автоматически исправить определение.

---

## Step 2 — Measurement Chain

Построй полную цепочку:

```text
REAL PHENOMENON
→ CONSTRUCT
→ OPERATIONALIZATION
→ INSTRUMENT
→ RAW SIGNAL
→ PREPROCESSING
→ FEATURE / SCORE
→ THRESHOLD OR METRIC
→ SCIENTIFIC CLAIM
```

Для каждого перехода укажи: необходимое assumption; какая информация
теряется; какая добавляется; какие artefacts могут возникнуть; какие внешние
переменные могут влиять на результат.

| Transition | Assumption | Information Loss | Possible Artefact | Evidence |
|---|---|---|---|---|

Не заполняй неизвестные свойства инструмента предположениями. Если
информации недостаточно: `<unknown>Недостаточно данных.</unknown>`

---

## Step 2a — Reference Standard Audit

**Запускать ТОЛЬКО когда target measurement сравнивается с named
reference/gold standard** (не для любой claim — большинство измерительных
вопросов не имеют этой структуры). Добавлено 2026-08-31 после n=3 реальных
dogfood-прогонов в трёх разных доменах (сон/wearables vs PSG, дерматопатология
vs консенсус патологов, автоматическое оценивание эссе vs человек-рейтер) —
во всех трёх reference standard молчаливо занимал место `REAL PHENOMENON` в
Step 2, хотя сам является операционализированной измерительной системой.

Прежде чем интерпретировать расхождение target vs reference — перестрой
Step 2 в две параллельные ветви:

```text
LATENT / REAL PHENOMENON
       ├── Reference branch: raw signal → transformations → reference label
       │      (это ТОЖЕ измерительная система, не сам феномен)
       └── Target branch: raw signal → transformations → target label
```

Для reference branch определи отдельно:
- что reference непосредственно наблюдает;
- какую часть construct он operationalizes (частично, не весь construct);
- какие transformations превращают raw signal в reference label;
- известную inter-rater / intra-rater variability (конкретное число, не
  "предположительно надёжен");
- возможные reference-specific artefacts;
- тип reference: gold standard / criterion standard / accepted proxy /
  consensus label / imperfect reference — назвать явно, не считать
  умолчательно "gold standard" просто потому, что так принято в поле.

Не интерпретируй расхождение Target ≠ Reference автоматически как ошибку
Target. Рассмотри три модели:

**H_TARGET_ERROR:** target measurement ошибается.
**H_REFERENCE_ERROR:** reference standard ошибается или теряет информацию
(измеренная inter-rater variability reference — прямое свидетельство ЗА эту
модель, не против неё).
**H_CONSTRUCT_MISMATCH:** target и reference измеряют частично разные
аспекты underlying phenomenon (например surface-feature proxy vs genuine
comprehension — см. Step 3 "construct contamination").

Определи, какое дополнительное наблюдение способно различить эти три модели
(обычно — независимый downstream outcome, не зависящий ни от reference, ни
от target: см. Step 6).

---

## Step 3 — Competing Measurement Models

**Если применялся Step 2a** (есть named reference standard): H_TARGET_ERROR
из Step 2a — это H_MEASURE применительно конкретно к target-ветви;
H_REFERENCE_ERROR — это отдельная, симметричная возможность (расхождение
объясняется НЕ target, а самим reference) — не сворачивай её обратно в
H_MEASURE, она указывает на другую сторону сравнения; H_CONSTRUCT_MISMATCH —
частный случай "construct contamination" ниже, где обе ветви валидны, но
измеряют не совсем одно и то же.

Построй минимум две модели.

### H_REAL
Observed effect преимущественно отражает реальное изменение target
construct. Укажи: предполагаемый mechanism; ожидаемые независимые признаки;
какие результаты должны воспроизводиться через другие measurement channels.

### H_MEASURE
Observed effect может возникнуть полностью или частично из measurement
system. Проверь следующие классы механизмов, только если они релевантны:
proxy substitution · common-method variance · batch effect · instrument
drift · preprocessing artefact · threshold artefact · annotator effect ·
operator effect · differential missingness · calibration error ·
group-specific measurement behaviour · temporal instability · construct
contamination · circular definition · label leakage.

Для каждого кандидата: Mechanism / Почему он способен создать observed
result / Какие данные его поддерживают / Какие данные против него / Что
различит H_REAL и H_MEASURE.

Не считай наличие правдоподобного H_MEASURE доказательством того, что
основной эффект ложен.

**Калибровка формулировки механизма (найдено 2026-08-31, первый реальный
прогон v0.2 — sleep tracker case, независимо проверено пользователем через
реальную литературу): не формулируй перекрытие сигналов как категоричный
факт полной неразличимости ("X физически неразличим от Y"), если это гипотеза
о ГРУБОМ single-feature сигнале, а не показанный факт о реальном алгоритме.
Устройства обычно комбинируют несколько признаков (например PPG + движение,
не один HRV-показатель); комбинация может частично снимать перекрытие, даже
если каждый признак по отдельности неразличим. Точнее: "X и Y существенно
перекрываются по доступным периферийным признакам, создавая information
bottleneck относительно эталонного метода" — не абсолютное "неразличимы".

---

## Step 4 — Construct Validity Checks

Проверь, насколько позволяют данные:

- **Convergent Validity** — сходится ли measurement с независимыми
  способами измерения того же construct?
- **Discriminant Validity** — отличает ли measurement target construct от
  соседних constructs?
- **Criterion Validity** — связан ли показатель с независимым внешним
  criterion?
- **Content Validity** — покрывает ли operationalization существенную часть
  construct?
- **Predictive Validity** — сохраняется ли смысл measurement вне среды его
  разработки?

Для каждого пункта: SUPPORTED / PARTIALLY SUPPORTED / UNSUPPORTED / UNKNOWN.
Не выводи validity из популярности инструмента.

**Thermometer principle (найдено 2026-08-31, первый реальный прогон v0.2):**
отсутствие ПРЯМОГО доступа к определяющему физиологическому/физическому
сигналу construct — не то же самое, что UNSUPPORTED Content Validity.
Термометр не измеряет молекулярную кинетическую энергию напрямую, и это не
делает его невалидным измерителем температуры — валидность идёт через
эмпирическую criterion/convergent validity, не через прямой физический
доступ к механизму. Если прямого доступа нет, но криterion/convergent
validity эмпирически подтверждена (пусть частично) — пиши раздельно:
"direct physiological/physical coverage: LOW; criterion/convergent validity:
PARTIAL", а не одним махом "Content Validity: UNSUPPORTED". Иначе гейт будет
систематически штрафовать хорошие косвенные измерители (большинство
биомаркеров, все proxy-based инструменты) просто за то, что они непрямые.

---

## Step 5 — Measurement Invariance

Проверь, насколько один и тот же показатель имеет одинаковый смысл: между
группами · популяциями · лабораториями · культурами · устройствами ·
версиями инструмента · временными точками · experimental regimes.

Четыре уровня:
- **Structural Invariance** — измеряется ли одна и та же latent structure?
- **Scale Invariance** — одинаково ли construct отображается в числовой score?
- **Threshold Invariance** — одинаково ли интерпретируется decision boundary?
- **Error Invariance** — сопоставимы ли структура и величина measurement error?

Если evidence недостаточно, не предполагай invariance.

**Не путай device-specific performance с нарушением structural invariance
(найдено 2026-08-31, первый реальный прогон v0.2):** разница в чувствительности
между двумя устройствами/лабораториями/версиями сама по себе НЕ доказывает,
что latent-construct-to-score mapping отличается — это может быть просто
разная точность при ОДНОМ И ТОМ ЖЕ mapping. Настоящий structural invariance
claim требует сравнения именно mapping (например, факторной структуры), не
сравнения точности. Если у тебя есть только разница в sensitivity/accuracy
между устройствами, а не прямое сравнение mapping — пиши "cross-device
measurement equivalence: UNKNOWN / HIGH RISK", не "Structural Invariance:
NOT SUPPORTED" — второе является более сильным и специфичным утверждением,
чем данные позволяют.

---

## Step 6 — Independent Measurement Challenge

Найди measurement channel, максимально независимый от основного. Приоритет
отдавай смене: физического принципа · источника информации · modality ·
observer · timescale · processing pipeline. Не считай небольшую модификацию
того же инструмента независимым каналом.

Ответь: если target construct действительно создаёт observed effect, какой
независимый measurement system должен обнаружить совместимый сигнал?

---

## Step 7 — Discriminating Test

Спроектируй минимальный тест между H_REAL и H_MEASURE. Укажи:
Manipulation/Comparison · Primary Measurement · Independent Measurement ·
Positive Control · Negative Measurement Control · Expected Result under
H_REAL · Expected Result under H_MEASURE · Result that would materially
weaken H_REAL · Result that would materially weaken H_MEASURE · Main
Confounder · Cost/Feasibility.

Выбирай тест по принципу: `Discriminative Power × Independence ×
Information Gain × Feasibility ÷ Cost` (тот же дух, что Cheapest
Differentiating Test Protocol в `rules/falsification-ladder.md` — не
изобретать отдельную формулу).

**Предпочитай безопасные наблюдательные дизайны рискованным манипуляциям
(найдено 2026-08-31, первый реальный прогон v0.2):** первая версия этого шага
на реальном кейсе предложила фармакологическую манипуляцию (стимулятор/
плацебо) как "самый дешёвый тест" — но это добавляет НОВЫЙ causal mechanism
и требует отдельного медицинского/этического контроля, которого сам вопрос
измерения не требовал. Если вопрос — про измерительную систему, а не про
причинный эффект вещества, предпочитай: несколько повторных синхронных
измерений (target + independent channel) под естественной или безопасно
контролируемой вариацией, оценивая не только направление эффекта, но
within-person slope, bias, agreement, test-retest stability. Один-единственный
замер легко спутать с обычной случай-к-случаю вариативностью — Manipulation/
Comparison должен явно указывать, зачем нужна именно манипуляция, а не просто
повторное наблюдение.

---

## Step 8 — Diagnostic Output

**Не выноси автоматически финальный scientific verdict** (см. Purpose и
benchmark evidence во frontmatter — это единственный реальный сбой,
найденный на 10 реальных кейсах, и он воспроизводился именно на этом шаге).
Сформируй Measurement Risk Profile:

- Construct Ambiguity — LOW / MEDIUM / HIGH / UNKNOWN
- Proxy Gap — LOW / MEDIUM / HIGH / UNKNOWN
- Method Artefact Risk — LOW / MEDIUM / HIGH / UNKNOWN
- Measurement Invariance Risk — LOW / MEDIUM / HIGH / UNKNOWN
- Circularity Risk — LOW / MEDIUM / HIGH / UNKNOWN
- Independent Validation Strength — LOW / MEDIUM / HIGH / UNKNOWN

Плюс: Strongest H_REAL Case / Strongest H_MEASURE Case / Most Important
Missing Evidence / Most Diagnostic Independent Measurement / Cheapest
Differentiating Test.

---

## Step 9 — Advisory Recommendation

Допускаются только эти формулировки (никогда `REPLACE`/`REDEFINE`
напрямую — см. Quality Rule 12):

- **NO MAJOR MEASUREMENT CONCERN IDENTIFIED** — существенная
  measurement-проблема не обнаружена в доступной evidence base. Это НЕ
  означает, что scientific claim доказан.
- **CALIBRATION RECOMMENDED** — основной measurement plausibly usable, но
  требует calibration.
- **TRIANGULATION RECOMMENDED** — claim желательно проверить независимым
  measurement channel.
- **CONSTRUCT CLARIFICATION REQUIRED** — основная неопределённость в
  определении construct, не в измерителе.
- **MEASUREMENT SYSTEM REQUIRES REVIEW** — есть существенные основания
  подозревать, что measurement process способен изменить scientific
  interpretation.

---

## Step 10 — Final Adjudication Handoff

Передай downstream evaluator структуру:

```text
SCIENTIFIC CLAIM: ...
MEASUREMENT CLAIM: ...
STRONGEST H_REAL: ...
STRONGEST H_MEASURE: ...
SUPPORTED MEASUREMENT RISKS: ...
UNSUPPORTED / SPECULATIVE RISKS: ...
INDEPENDENT VALIDATION: ...
CRITICAL UNKNOWN: ...
BEST DISCRIMINATING TEST: ...
MEASUREMENT ADVISORY: ...
```

Downstream evaluator (эксперт / `hypothesis-arbiter` /
`boyko-scientific-consortium` / `skeptic`) самостоятельно решает: влияет ли
measurement uncertainty на основной scientific conclusion; насколько
существенно она меняет confidence; требуется ли доп. эксперимент; допустим
ли текущий claim; следует ли ослабить, сохранить или отклонить его.

---

## Quality Rules

1. Не путай reliability и validity.
2. Не считай predictive accuracy доказательством construct validity.
3. Не считай наличие H_MEASURE доказательством measurement artefact.
4. Не превращай неизвестность в автоматический `TRIANGULATE` (см. Step 9 —
   выбирай advisory-формулировку из реального взвешивания risk profile, не
   как default при отсутствии данных).
5. Не требуй дополнительное измерение только потому, что оно теоретически
   возможно.
6. Не считай один method независимым подтверждением самого себя.
7. Не интерпретируй одинаковый score как одинаковый construct без проверки
   invariance.
8. Не выдавай proxy за underlying construct.
9. Не создавай measurement problems без evidence.
10. Не используй model memory как скрытый источник доказательства (найдено
    2026-08-30: формулировка "если исследования названы, применяй широкое
    знание" была явно отклонена — она незаметно делает результат зависимым
    от того, что конкретно модель помнит и насколько это свежо; это
    ослабило бы evidence discipline ради прохождения одного benchmark-case,
    не решило бы реальную проблему).
11. Если внешний факт существенно меняет verdict, он должен быть проверен по
    источнику, не восстановлен по памяти.
12. Разделяй: documented measurement failure / plausible measurement risk /
    hypothetical measurement risk.
13. Scientific claim не должен быть сильнее measurement evidence.
14. Measurement audit не заменяет полный scientific evaluation.
15. **Финальный verdict принадлежит downstream adjudication layer, не этому
    модулю** — это архитектурное ядро v0.2, не совет. Модуль, вынесший
    `REPLACE`/`REDEFINE`/`PASS` от своего имени как финальное заключение,
    нарушает собственную спецификацию.

---

## Success Criterion

Модуль полезен, если он улучшает ответ на вопрос: какие альтернативные
объяснения observed signal возникают именно из того, как измеряется
scientific construct, и какой независимый тест лучше всего отличит реальный
феномен от поведения measurement system? **Он не обязан самостоятельно
отвечать: истинна ли вся научная гипотеза?**

---

## История версий (честно, не только успехи)

**v0.1 (2026-08-30)** — 5 шагов, включая собственный финальный Verdict
(PASS/CALIBRATE/TRIANGULATE/REDEFINE/REPLACE). Реальный blind-benchmark (10
кейсов, независимый curator, слепая адъюдикация) показал: сильнее baseline в
диагностике (H_REAL/H_MEASURE, независимые каналы, discriminating test),
но НЕ показал превосходства в финальном verdict — и конкретно проиграл
единственный deceptive-control кейс с наибольшей ставкой (Urban Heat
Island), где собственная дисциплина "не выходи за пределы данных пакета"
помешала сделать верный вывод, который baseline получил свободным
рассуждением. Formal Pass Criteria не выполнены целиком → EXPAND отклонён.

**v0.2 (2026-08-30)** — архитектурный пивот, не патч найденной проблемы.
Вместо попытки "починить" Verdict-шаг (отклонённый вариант: "используй
широкое знание модели, если исследования названы поимённо" — сам создал бы
новую проблему зависимости от model memory) — модуль полностью убирает
автоматический финальный verdict, оставляя только диагностику (Steps 1-8) +
advisory-рекомендации (Step 9, никогда REPLACE/REDEFINE) + явную передачу
downstream (Step 10). v0.2-архитектура САМА ЕЩЁ НЕ прогнана отдельным
бенчмарком — это ответ на находку v0.1, не подтверждённое улучшение. Решение
этого цикла: **MERGE/SPECIALIZE, не EXPAND.** Новый blind holdout сознательно
не запущен — следующий evidence source: реальное использование, случаи, где
diagnostics модуля меняют downstream-решение, не синтетический бенчмарк на
тот же вопрос ("максимум одна ревизия за цикл" уже использована).

**v0.2.1 (2026-08-31)** — первый реальный dogfood-прогон (потребительские
трекеры сна vs PSG), независимо фактчекнутый пользователем через реальную
литературу. Оценка 9.1/10: архитектурная гипотеза v0.2 подтвердилась —
модуль естественно разложил один тезис на две разные measurement claims
(абсолютная стадийность vs относительное отслеживание изменений) вместо
одного глобального verdict, ровно то, ради чего Verdict был убран. Но прогон
нашёл 4 калибровочные проблемы, все исправлены: (1) Step 3 — не формулировать
перекрытие сигналов как категоричный факт полной неразличимости; (2) Step 4 —
thermometer principle: отсутствие прямого физиологического доступа ≠
UNSUPPORTED Content Validity; (3) Step 5 — device-specific performance
разница ≠ доказательство нарушения structural invariance, отдельная
"cross-device measurement equivalence: UNKNOWN/HIGH RISK" категория; (4)
Step 7 — предпочитать безопасные повторные наблюдения фармакологическим/
рискованным манипуляциям, если вопрос не требует именно манипуляции. Также
найден potential НОВЫЙ epistemic объект, не патч: reference standard (в этом
кейсе — PSG) сам является измерительной системой, не самим "REAL PHENOMENON"
— это могло бы стать отдельным обязательным sub-gate "Reference Standard
Audit" (H_TARGET_ERROR / H_REFERENCE_ERROR / H_CONSTRUCT_MISMATCH), но НЕ
построен на n=1 — зарегистрирован как pearl-кандидат
(`pearl_registry/INDEX.md`, запись 2026-08-31, `next_check: 2026-09-30`),
ждёт повторения на 2-3 реальных кейсах прежде чем становиться частью гейта.

**v0.3 (2026-08-31)** — два дополнительных реальных dogfood-прогона в разных
доменах: ИИ-диагностика меланомы vs консенсус патологов (медицинский, острее:
каппа 0.27-0.87, полное согласие 8 экспертов в 53.5% случаев) и
автоматическое оценивание эссе vs человек-рейтер (намеренно НЕ медицинский —
тест на обобщаемость, kappa 0.58-0.71). Оба прогона воспроизвели ТОТ ЖЕ
паттерн из v0.2.1 (reference standard как измерительная система, не
REAL PHENOMENON) — n=3 в трёх разных доменах, порог pearl_registry достигнут.
Третий прогон дополнительно показал, что гейт уже корректно НЕ путает этот
паттерн с структурно другой находкой (Perelman/BABEL construct-contamination
gaming в том же кейсе — покрыта существующим Step 3 механизмом, не потребовала
новой capability). Построен **Step 2a — Reference Standard Audit**: явное
разделение измерительной цепочки на reference-ветвь и target-ветвь до того,
как строятся H_REAL/H_MEASURE, плюс H_TARGET_ERROR / H_REFERENCE_ERROR /
H_CONSTRUCT_MISMATCH как три раздельные модели расхождения вместо
автоматического "target неправ". Pearl-запись закрыта как resolved. Сам новый
Step 2a — described, ещё НЕ прогнан отдельным dogfood-раундом (следующий
реальный прогон гейта на кейсе с named reference standard станет первой
проверкой уже самого Step 2a, не только паттерна, который его мотивировал).

---

## Связанные скилы

- `hypothesis-arbiter`, `boyko-scientific-consortium`, `skeptic` — типовые
  downstream adjudication layer для Step 10 (этот модуль не заменяет их
  финальный вердикт, а снабжает их структурированной diagnostic-справкой).
- `rules/estimand-ops.md` — следующий шаг конвейера после диагностики; этот
  гейт не заменяет L0-классификацию, идёт перед ней.
- `rules/artifact-provenance-gates.md` Gate 3 — узкий частный случай
  калибровки (digitization кривых), можно упомянуть в Step 9 CALIBRATION
  RECOMMENDED, если применимо к типу данных.
- `hypothesis-red-team` T11/T12 — смежные, но более грубые метки
  (dry-lab/wet-lab confusion, fit vs prediction) — не заменяют аудит цепочки
  измерения целиком.
- `sci-code-audit` — доверие к КОДУ, не к психометрической валидности
  конструкта — разные объекты аудита.
