# Live-only lines from global hypothesis-arbiter (not in repo), saved 2026-11-01 before deploy
# Review and merge into skills/extensions/boyko-hypothesis-arbiter, then delete this file.
name: hypothesis-arbiter
  Когда не знаешь почему что-то происходит — выдвигает 4-6 конкурирующих объяснений
               # experiments/20260728-hypothesis-arbiter-taxonomy-pilot/decision.md (filed in
triggers: [/hyparb, /strong-inference, "конкурирующие гипотезы", kill-test, "почему это происходит"]
Скил   : hypothesis-arbiter
Вызов  : /hypothesis-arbiter, /hyparb, /strong-inference, "выдвини гипотезы", "множественные гипотезы", "конкурирующие объяснения"
| Проект | Когда применять hypothesis-arbiter |
- Минимум **4 гипотезы**, максимум **6** (меньше — underfit, больше — неуправляемо)
**Статусы по итогу:**
- ✅ **ВЫЖИЛА** — Confidence ≥ 0.55, нет прямого опровержения
- ⚠️ **ПОД ВОПРОСОМ** — Confidence 0.40–0.54 или источник одиночный
- ❌ **УБИТА** — Confidence < 0.40 или найдено прямое опровержение (grade A/B)
**Добавка специфичная для hypothesis-arbiter (не покрыта каноническим гейтом):**
   - 0 → все ложны → нужна новая генерация (вызов /sci-hypothesis)
### `/hypothesis-arbiter` или `/hyparb` — полный цикл (все 5 этапов)
sci-hypothesis ──→ [hypothesis-arbiter] ──→ scientific-research
- `/negative-space-miner` — вызывает, если Этап 4 (Repair Hypotheses) даёт >1 survivor-гипотезу, для ACH/kill-test дискриминации между ними
Когда в такой таблице заполнено ≥3 гипотезы: `python scripts/ach_quotient.py classes <файл>` (из репозитория
Claude-cod-top-2026) покажет гипотезы, которые ни один заполненный тест не разделяет, и тесты, не разделяющие
ничего; `N/A` там никогда не равно согласию. Справка, не гейт (`docs/derived-view-tools.md`).
