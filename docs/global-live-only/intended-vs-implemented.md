# Live-only lines from global intended-vs-implemented (not in repo), saved 2026-11-01 before deploy
# Review and merge into skills/extensions/intended-vs-implemented, then delete this file.
  USE when you need to find gaps between what documentation claims the system
  does vs what the code actually does. Catches high-value bugs that linters miss:
  permissions documented but unenforced, endpoints marked internal that accept
  external calls, data classified as private that leaks.
  ALWAYS cite both documentation claim AND code evidence — no speculation.
  Triggers: /intended-vs-implemented, docs vs code, intent vs reality,
  [STATUS: confirmed] [CONFIDENCE: high] [REVIEWED: 2026-08-11]
triggers: [/intended-vs-implemented, "docs vs code", "intent vs reality", "задокументировано vs реализовано", "docs не совпадают с кодом", "что обещано vs что делает", "audit intent", "verify documented behavior"]
Читать: `README.md`, `docs/`, `CLAUDE.md`, docstrings, inline comments с `# WHY:`.
