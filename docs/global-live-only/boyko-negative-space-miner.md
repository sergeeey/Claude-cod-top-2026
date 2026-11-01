# Live-only lines from global negative-space-miner (not in repo), saved 2026-11-01 before deploy
# Review and merge into skills/extensions/boyko-negative-space-miner, then delete this file.
name: negative-space-miner
  Triggers: /negative-space-miner, /negative-space, зона молчания, null results,
Скил   : negative-space-miner
Вызов  : /negative-space-miner, зона молчания, null results, failed replications
НЕ для : Атаки готовой гипотезы (→ /sci-evidence falsify), своих null_results (→ narrow-discovery-engines Engine 4), выбора между готовыми H (→ /hypothesis-arbiter)
# negative-space-miner — гипотезы из опубликованных провалов
   `hypothesis-arbiter`): repair-гипотеза объясняет конъюнкцию `наблюдение ∧
ПЕРВИЧЕН для Этапа 2/3, конфликты из основных запросов выше интерпретируются
через его призму, не параллельно с ним.
Классификация конфликта (ровно одна метка на строку, не смешивать):
`methodological` | `measurement` | `population-specific` | `temporal` |
показавшийся правдоподобным". То же самое HARD RULE 3 из `hypothesis-arbiter`
`hypothesis-arbiter`), или (б) понизить H_N до статуса "одна из нескольких
`hypothesis-arbiter` для той же ситуации, не изобретать второй.
- `hypothesis-arbiter` — если Этап 4 дал >1 survivor-гипотезу, ACH/kill-test

## История валидации

> Перенесено из frontmatter `description:` 2026-09-10. Описание грузится в
> системный промпт КАЖДЫЙ ход; эта история нужна только когда скилл реально
> запускается. Текст ниже — дословно тот, что стоял в описании.

[STATUS: described] [CONFIDENCE: n=1, 2026-08-30 — реальный прогон на ego
depletion / strength model of self-control (Baumeister 1998), с реальным
WebSearch (не по памяти): нашёл RRR 2016 null result, bias-corrected
meta-анализ, критику глюкозного механизма (Kurzban 2013) и хрупкий
moderator (Job/Dweck/Walton 2010 + его собственная 2023 реплика). Все 9
этапов отработали, ACH-матрица (Этап 7) реально нашла дешёвый
дискриминирующий тест. Прогон нашёл 2 доработки, обе применены: (1) "макс 5
гипотез" не означает "минимум 5" — явно разрешено меньше; (2) Novelty Check
без делегирования `/novelty-assessment` не может подниматься выше `closely
related`. Второй прогон (2026-08-30, microbiome/obesity causal claim, тоже
реальный WebSearch) дал репаир-гипотезу, которую НЕЗАВИСИМЫЙ skeptic-агент
(context-asymmetric, только claim+evidence) оценил как WEAKENED, на грани
FALSIFIED-AS-STATED: пересказ существующего caveat, а не синтез, и
unfalsifiable-by-confounder-appeal. Это НЕ провал скилла — это найденный им
же самим (через собственный процесс) реальный сбой исполнения на Этапах 3-4
и 6, приведший к 2 новым gate'ам: Ruling Theory Trap gate (Этап 3, не
останавливаться на первом правдоподобном кандидате без явного отклонения
остальных) и Rescue-unfalsifiability check (Этап 4, Duhem-Quine оговорка не
должна покрывать ЛЮБОЙ мыслимый негативный результат). Честный итог: метод
реально работает на объектах с несколькими конкурирующими объяснениями
(ego depletion), но давал слабый результат на объекте с одним консенсусным
объяснением в поле — само по себе полезная граница применимости, найденная
адверсариальной проверкой, а не самооценкой. Тот же microbiome-объект
прогнан ПОВТОРНО с обоими новыми гейтами (третий реальный прогон,
2026-08-30) — второй независимый skeptic-аудит нашёл РЕАЛЬНОЕ улучшение
(3 из 5 гипотез — NEEDS-REAL-DATA с конкретными, в основном tight
falsifiers, вместо WEAKENED/FALSIFIED у всех), но и НОВУЮ находку на уровень
выше: Ruling Theory Trap воспроизвёлся в списке КАНДИДАТОВ (generic
чек-лист Этапа 3 сам не domain-complete — пропустил publication bias в
ПОЛОЖИТЕЛЬНОЙ мышиной литературе, провалившиеся человеческие FMT-испытания,
host-genotype взаимодействие), и рекомендованный "самый дешёвый тест"
оказался НЕ дискриминирующим (одинаковый ожидаемый результат под 2 разными
гипотезами — нарушение собственного правила ach_matrix.md, прочитанного, но
не применённого построчно). Добавлены Exhaustion Completeness check (Этап 3,
делегирует narrow-discovery-engines Engine 4) и Full-row diagnosticity check
(Этап 7). Третий, независимый объект — minimum wage/employment (Card-Krueger
1994 vs Neumark-Wascher 1996) — дал ТРЕТИЙ skeptic-вердикт хуже двух первых:
"worse than a competent economist reading a review for 20 minutes". Причина
— новый, ещё более тонкий класс сбоя: generic-чек-лист Этапа 1/3 находит
КОНФЛИКТУЮЩИЕ РЕЗУЛЬТАТЫ, но не находит то, что само поле называет причиной
разногласия (выбор дизайна идентификации — border-pairs vs synthetic
control — не "источник данных", как я предположил без явного поиска именно
методологического спора); плюс H2 использовала необнаруженный
unfalsifiable threshold-механизм ("эффект есть до определённого порога", без
числа), и Full-row check не поймал confound самой переменной стратификации
(концентрация рынка коррелирует со скрытым фактором ДРУГОЙ гипотезы).
Добавлены ещё 3 gate'а: обязательный поиск "методологический спор поля"
как отдельная категория в Этапе 1 (не покрывается поиском null result),
numeric-threshold requirement для механизмов "до порога" (Этап 4), и
Stratifier-confound check (Этап 7, отдельно от Full-row check — та же
проблема класса "выглядело диагностичным, не было", но на уровне причины
предсказания, не самого предсказания). ЭТО ТРЕТИЙ ЦИКЛ "прогон → skeptic →
фикс" подряд без чистого LGTM — по Evaluator-Optimizer Guard из CLAUDE.md
здесь остановлена автономная итерация, эскалировано пользователю вместо
тихого 4-го цикла на новом объекте. Паттерн по трём объектам: метод
надёжен на объектах со СТАНДАРТНЫМИ типами конфликта (измерение,
confounding, reverse causation — ego depletion, частично microbiome), но
систематически слаб там, где ключевой спор поля — это выбор МЕТОДА/дизайна
идентификации, а не биологический/поведенческий механизм (современная
причинная эконометрика). Это картированная, не гипотетическая граница.
Собран 2026-08-30 по итогам сравнения внешнего промпта "ЗОНА
МОЛЧАНИЯ" с каталогом: закрывает единственный из трёх выявленных пробелов,
для которого не нашлось существующего скилла (в отличие от Outcome
Interpretation → hypothesis-arbiter и Assumption Taxonomy →
narrow-discovery-engines, обе добавлены как патчи, не новые скиллы).]
НЕ для: атаки гипотезы, которой уже доверяешь (→ /sci-evidence falsify),
работы с остатками СВОЕЙ модели или СВОИМИ null_results (→
narrow-discovery-engines Engine 1/4, /research-audit), выбора между уже
сформулированными конкурирующими гипотезами (→ /hypothesis-arbiter),
генерации гипотез с нуля без опоры на провалы (→ /cross-domain,
narrow-discovery-engines Engine 2).
effort: high
tokens: ~1600
triggers: [/negative-space-miner, /negative-space, "зона молчания", "null results", "failed replications", "почему это не сработало", "провалившиеся эксперименты", "противоречащие исследования", "boundary conditions", "negative-space hypothesis"]
