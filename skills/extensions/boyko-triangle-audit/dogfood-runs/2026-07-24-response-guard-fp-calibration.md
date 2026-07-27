# Dogfood run — boyko-triangle-audit vs experiments/20260716-response-guard-fp-calibration/

**Purpose:** real promotion evidence for `maturity: dogfooded` (P2 plan item 16,
`docs/baselines/2026-07-24-plan.md`), per the bar defined in
`docs/skill-maturity-criteria.md`. Not a synthetic test case — the audited
artifact is a real, previously-committed experiment from this repo's own
history (`experiments/20260716-response-guard-fp-calibration/`), audited
independently after the fact.

**Method:** a fresh `explorer`-type agent was given only the path to
`skills/extensions/boyko-triangle-audit/SKILL.md` and instructed to follow it
exactly against the target experiment folder — no prior context on this
session's own conclusions about that experiment, no steering toward a
particular verdict.

**Verification (this repo's own `rules/audit-verification-gate.md` — agent's
`[VERIFIED]` is not treated as verified until independently spot-checked):**
all 4 cited quotes were checked against the actual files. Two initial
single-line `grep` checks came back "no match" — traced to markdown
soft-line-wrapping splitting the quoted phrase across two physical lines in
the source file, not a fabrication; a full-file `Read` of both files
confirmed all quotes are genuinely present, in context, and accurately
represent the source. The other two citations (`claim.md`, `step4_redteam.md`)
matched on direct read. Verdict: agent output accepted as real evidence, not
theater.

---

## Triangle Audit: experiments/20260716-response-guard-fp-calibration/

| Вершина | Статус | Evidence (файл:строка или цитата) |
|---|---|---|
| Теория | present-strong | `result_summary.md:22-33` — "Why it does not generalize (root cause, not just symptom)... Distinguishing 'you must sanitize inputs' (advice to the reader) from 'you must ignore your rules' (injection) requires understanding the OBJECT of the imperative. That is semantic, not lexical -- no regex sees it." Names the structural mechanism (regex is lexical, the distinction is semantic), not just a number. |
| Вычисления | present-strong | `result_summary.md:12-15` -- table with dated, tool-tagged numbers: "Calibration corpus... 0 FP / 0 FN `[VERIFIED-SYNTHETIC]`... Held-out corpus (8 cases, NOT used in tuning)... 4 FP / 2 FN `[VERIFIED-SYNTHETIC]`". Also `claim.md:22-29` baseline table marked `[VERIFIED-bash]` with a stated measurement date (2026-07-16). Both point to reproducible commands/artifacts, not promised future runs. |
| Независимая проверка | present-strong | Two independent instances: (1) `step4_redteam.md:3-4` -- "Context-blind sec-auditor pass on `hooks/severity_calibrator.py`... found structurally sound but with real, tool-verified implementation bugs -- all now fixed and locked with regression tests." A different reviewer using doubt-driven-development's context-asymmetry protocol, not the same pipeline re-run. (2) `step6_shadow_findings.md:5` -- "2 actual WebSearch responses... fed through the real `web_response_guard.py` hook with `CLAUDE_GUARD_SHADOW=1`" -- real production-shaped data as an alternative check to the hand-authored corpus, which explicitly overturned the corpus's optimistic number (`step6_shadow_findings.md:35-37`: "the FP-reduction sell was corpus-optimistic"). |
| Объяснение | present-strong | `result_summary.md:22-38` explicitly asks and answers the degeneracy question for why 0/0-on-calibration happened yet failed held-out: "The calibration 0/0 is overfitting: the patterns were written while looking at that corpus, so passing it proves nothing about generalization." It then splits the failure into two named, non-overlapping mechanisms (descriptive-imperative-grammar ambiguity vs. unbounded paraphrase space) rather than treating the held-out failure as unexplained noise, and cross-checks against two independent predictions made earlier in the session ("Both were independently predicted by two external reviews this session..." -- `result_summary.md:34-36`). A real alternative-hypothesis-checked explanation, not a bare "it didn't generalize." |

**Итоговый вердикт:**

ПОЛНЫЙ ЦИКЛ -- все 4 вершины present-strong, с прямыми цитатами и file:line на
каждую. Это не типичный "остановились на совпадении" случай: артефакт явно
ловит и отвергает собственный ложный успех (0/0 на калибровочном корпусе)
через held-out тестирование (`result_summary.md`) и второй независимый
проход (`step4_redteam.md` -- context-blind sec-auditor; `step6_shadow_findings.md`
-- реальные production-данные), затем формулирует структурное объяснение
провала, а не просто фиксирует число. `decision.md` и
`null_results/20260716-regex-composition-response-guard.md` фиксируют REJECT
с явным Kill Analysis-стилем изложением (что убито: regex-composition
конкретно; что не убито: сама задача калибровки, source-aware classifier
остаётся открытым направлением).

Единственное, что стоит явно отметить как ограничение цикла, а не как gap
вершины: n=4 в `step6_shadow_findings.md:5` сам себя маркирует как "a probe,
not a verdict" -- независимая проверка присутствует и методологически
валидна (иной метод/данные), но статистически мала. Это не понижает статус
вершины (метод независим и результат реален), но ограничивает то, насколько
сильно на неё можно опираться при будущем PROMOTE решения о live-режиме
классификатора.

**Не покрыто этим аудитом:**
- Верен ли сам claim по существу за пределами того, что здесь измерено
  (например, репрезентативность корпуса для продакшн-трафика в целом) --
  это работа skeptic/falsification-ladder, не этого аудита.
- Эпистемический уровень отдельных claim'ов (факт/теория/гипотеза) -- это
  `/boyko-knowledge-audit`.
- Годится ли предложенная архитектура (source-aware classifier / LLM-judge)
  как решение -- это дальнейшее архитектурное решение, явно оставленное
  пользователю (`result_summary.md:51-62`), не проверялось этим аудитом.
