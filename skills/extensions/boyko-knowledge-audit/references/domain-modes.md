# Domain Modes

Пользователь должен указать домен.
Если не указан — осторожно инферь домен и заяви об этом.
Если неясно — используй самый широкий применимый режим и помечай неопределённость.

---

## Mode: Physics / Cosmology / High-Energy Theory
Спецправила:
* математическая элегантность никогда не evidence для физической истины;
* в high-energy theory без экспериментального доступа многие предсказания остаются Level 5 или Level 6;
* космологические наблюдения касаются одной вселенной; различай наблюдение и универсальный закон;
* не повышай модель до теории просто потому, что она математически согласована;
* не трактуй согласованность с теорией как доказательство, если сама теория проверяется.

Триггеры понижения: "naturalness" как evidence; "красота" или "простота" как физическая поддержка; единственная реализация модели, поданная как неизбежная; эмпирическая недоступность, скрытая за теоретической уверенностью.

---

## Mode: Mathematics
Используй суб-иерархию:

| Математический статус | Основной уровень | Правило |
|---|---:|---|
| Аксиома / Определение | Level 7 | Фундаментальное допущение |
| Лемма / Предложение | Level 3-M | Только если есть доказательство или точная ссылка |
| Теорема | Level 3-M | Только внутри аксиоматической системы |
| Следствие | Level 3-M | Прямое следствие теоремы |
| Гипотеза/Конъектура | Level 6 | Точно сформулирована, но не доказана |
| Эвристика / Интуиция | Level 6 или Level 0 | Зависит от ясности |
| Пример / Контрпример | Level 1 | Конкретный математический инстанс |
| Отсутствует набросок доказательства | Level 0 | Если нет точной ссылки |

Спецправила: никогда не смешивай теорему с физическим законом; если доказательство отсутствует, а ссылка расплывчата — Level 0; если теорема условна на допущениях — перечисли их; если теорема используется для implied эмпирической истины — требуй empirical bridge.

---

## Mode: Biology / Medicine / Clinical Research

| Измерение | Варианты |
|---|---|
| Тип evidence | Meta-analysis / RCT / Cohort / Case-control / Case study / In vitro / In vivo animal / In silico / Expert opinion |
| Причинность | Established causal / Probable causal / Associational / Correlational only / Unknown |
| Внешняя валидность | Broad / Limited population / Single study / Unknown |
| Механизм | Validated molecular mechanism / Proposed mechanism / Unknown |

Спецправила: одиночный RCT — Level 1 для этого испытания, не универсальный Level 3-P; мета-анализ с низкой гетерогенностью может поддержать Level 2; claims механизма без молекулярной валидации — Level 6; animal-модель — Level 5 для human claims; in vitro находки — Level 5 для in vivo claims; клинические causal claims требуют design или identification strategy.

---

## Mode: Computer Science / Machine Learning

| Измерение | Варианты |
|---|---|
| Тип результата | Theorem / Benchmark / Ablation / Case study / Architecture proposal / System claim |
| Воспроизводимость | Independent / Single-team / Unreproduced / Unclear |
| Генерализация | Proven / Cross-dataset empirical / Single dataset / Unknown |
| Scope | Formal model / Benchmark-specific / Production-specific / Undefined |

Спецправила: результат бенчмарка — Level 1 только для этого бенчмарка; SOTA claim — Level 1 только для указанного comparison set; предложение архитектуры — Level 5 до валидации на разных задачах; ablation — Level 2 только для этой экспериментальной установки; теоретическая граница — Level 3-M внутри формальной модели; production claims требуют runtime/deployment evidence.

---

## Mode: Social Sciences / Economics / Psychology

| Измерение | Варианты |
|---|---|
| Методология | Experimental / Quasi-experimental / Observational / Survey / Theoretical model |
| Causal identification | RCT / Natural experiment / IV / RD / Difference-in-differences / Matching / OLS only / None |
| Репликация | Replicated / Failed replication / Unreplicated / Unknown |
| Scope | Universal / Context-dependent / Culture-specific / Sample-specific |

Спецправила: OLS на observational данных — Level 2 максимум, часто Level 1 только для корреляции; causal claims без identification strategy — Level 6; допущения рационального актора — Level 7; нереплицированные результаты — дефолт Level 0 или Level 6, если evidence не показан; scope-условия должны быть явными.
