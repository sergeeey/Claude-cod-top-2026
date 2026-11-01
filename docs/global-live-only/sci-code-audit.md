# Live-only lines from global sci-code-audit (not in repo), saved 2026-11-01 before deploy
# Review and merge into skills/extensions/sci-code-audit, then delete this file.
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED (retired) 2026-05-24]
  10-layer audit of scientific/research code — answers "can we trust the code that
  produced these results?" Companion to gate-check (methodology) and code-materiality
  (bug triage). Covers: silent fallbacks, invariant tests, control validity, data
  provenance, statistical interpretation, documentation drift, reproducibility.
  Triggers: /sci-code-audit, "code audit", "найди что ещё упустили", "audit code",
  "code hardening", "trust the code", "аудит кода", "могли упустить", "что ещё проверить",
  "layers of risk", "scientific code review", "audit pipeline code", "code maturity",
  "research-prototype to production", "audit hardened".
  Invoke proactively when: external auditor found bugs and you want to check what else
  might be wrong; before claiming results are final; before submission or blind test.
- `gate-check` — "методология звучит?" (научная валидность)
2. **Gate/версия** — какие результаты проверяем (напр., Gate 4B / v0.1.22)
4. **Главный claim** — что именно утверждаем (напр., "7.15× IPR contrast, p<0.001")
ls -la results/gate_4b/
| "7.15×" | mean of ratios или ratio of means? weighted? |
# CODE_AUDIT_HARDENING — <Project> / <Gate> / <Date>
| 2 — Silent fallbacks | ⚠️ | Found: central_window fallback | PATCH |
## Overall Verdict
[HARDENED / PROVISIONAL / NEEDS_WORK / STOP]
- `/gate-check` — параллельно: научная методология
