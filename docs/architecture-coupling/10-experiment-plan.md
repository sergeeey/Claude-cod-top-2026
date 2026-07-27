# 10 — Falsification Experiments

Формат: Claim → Alternatives → Test → Controls → Metric → Gates → Null-policy.
Question type (EstimandOps L0) указан для каждого. Ни один разрушающий эксперимент
в «production» (живой ~/.claude пользователя) не запускается.

## Experiment A — Graph-only decomposition (выполнен частично, descriptive)

- **Claim:** чисто графовое разбиение (Louvain) достаточно для целевых границ hooks/.
- **Alternative:** графовое разбиение оверфитится на инфраструктурные рёбра (utils).
- **Test:** сравнить Louvain-партицию с DDD-informed (08) по edge cut, semantic clarity
  (доля кластеров с именуемым доменом), cross-boundary calls.
- **Результат [VERIFIED]:** Louvain: edge cut минимален, но C0 (41 файл) семантически неименуем —
  5/9 кластеров осмысленны; Fiedler: cut=2, обе половины неименуемы. DDD-informed вариант
  проигрывает по cut, выигрывает по clarity 6/6.
- **Gate:** если graph-only выигрывает только по cut → гипотеза «математического разбиения
  достаточно» **опровергнута**. <fact>Опровергнута.</fact>
- Null-policy: зафиксировано здесь + в null-результатах отчёта (14, §19).

## Experiment B — Zero-coupling observability (toy, design-time)

- **Claim:** полная изоляция двух хуков (без общего utils/логгера) сохраняет диагностируемость сбоя.
- **Test:** toy-пара хуков A→B через файл-очередь во временном каталоге; сбой на шаге B;
  проверить: trace-корреляция (общий request-id?), error propagation, восстановление.
- **Positive control:** те же хуки с utils.log_hook_trigger (общий JSONL, единый writer).
- **Negative control:** сбой без какого-либо логгера (должен быть недиагностируем — иначе тест слаб).
- **Metric:** время/шаги локализации сбоя по логам; полнота audit trail.
- **Pass gate (для гипотезы изоляции):** локализация без общего лога ≤ 2× времени с логом.
  **Fail gate:** сбой невоспроизводимо теряется. Прогноз по H7: fail — «изоляция без контрактов
  делает coupling ненаблюдаемым» (02 §H7).
- Null-policy: результат любой полярности → в experiments/ репо по шаблону FL Standard.

## Experiment C — Fat interface split (utils.py) — данные ДО собраны

- **Claim:** utils.py разделим на 4 подбиблиотеки так, что клиенты станут узкоспециализированными.
- **До [VERIFIED-ast]:** 61 клиент; медиана 3 имени/клиента из 34; max 9; кластеры использования:
  runtime-protocol (43/26/16 использований), state+log (11/11/7), discovery (6/3), security (2/2/2).
- **Metric после:** sublibs-per-client; contract count; mock complexity в тестах utils.
- **Pass gate:** медиана sublibs/клиента = 1; ни один клиент >2; 0 циклов между sublibs.
- **Fail gate:** >20% клиентов требуют 3+ sublibs → разрезание выбрано неверно, пересобрать по
  фактическим co-usage парам.
- Null-policy: fail → HS-01 остаётся, но переходит в «split по-другому», не в «не трогать».

## Experiment D — Static vs change coupling (выполнен, descriptive)

- **Claim:** static-зависимости предсказывают совместные изменения.
- **Результат [VERIFIED-git]:** Jaccard(static, co-change≥3) = **0.121**; 43 co-change-пары без
  static-ребра (документы/манифесты/конфиги — скрытый process coupling); 204 static-пары без
  co-change (стабильные библиотечные импорты).
- **Вывод:** claim в сильной форме **опровергнут**; практический вывод — fitness-контроль только
  импортов слеп к главному каналу изменений этого репо (обоснование правил 3/4/14 из 11-fitness).

## Experiment E — Boundary failure injection (safe, sandbox)

- **Claim:** конкурентная запись в activeContext.md безопасна при текущей дисциплине file_lock.
- **Test (sandbox tmp-каталог, НЕ живой ~/.claude):** N параллельных процессов пишут через
  (a) utils.file_lock-путь, (b) сырой open('w') — как минимум один реальный хук пишет без lock.
- **Fault-набор:** interleaved write, kill -9 посреди записи, полный диск (симуляция через quota-dir).
- **Metric:** доля повреждённых/потерянных записей; обнаружимость повреждения читателями.
- **Pass:** (a) 0 повреждений; **Fail:** любое повреждение в (a). Для (b) ожидаем повреждения —
  это positive control опасности и обоснование memory-API (Option B §8).
- Null-policy: если (b) тоже 0 повреждений на Windows-семантике — риск HS-03 понижается до P2,
  фиксация в отчёте обязательна.

## Experiment F — Fitness-function backtest (частично выполнен)

- **Claim:** count-consistency gate ловит реальные исторические дефекты и не шумит.
- **Backtest [VERIFIED-git+read]:** известные инциденты: (1) «87 vs 88» — пойман бы: именно из него
  gate родился (docstring test_structure); (2) cf32d7f «88→89 sweep missed header» — фраза
  «## 89 Hooks» ловится паттерном gate (тест уже допускает 1 прилагательное между числом и «hooks»).
- **FP-оценка:** правки чисел, не являющихся счётчиками — потенциальный шум; выборочная проверка
  требуется на 20 последних doc-коммитах. <hypothesis>FP-rate < 10%</hypothesis> — верифицировать
  прогоном gate по истории (git worktree на N исторических коммитов).
- **Gate:** правило переводится в block только если backtest: ≥80% исторических инцидентов
  поймано, FP ≤ 10% нормальных коммитов.
