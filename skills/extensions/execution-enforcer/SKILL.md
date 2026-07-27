---
name: execution-enforcer
version: 1.0.0
status: confirmed
confidence: high
validated: 2026-05-30
author: Sergey Boyko
description: |
  Превращает audit outputs (markdown отчёты, /goal conditions, action backlogs) в реальные
  commits, tests, artifacts. Защита от audit theatre — главного антипаттерна из user vault
  (intention-action gap). Берёт на вход /atomize output ИЛИ /source-distiller output ИЛИ
  любой план — выдаёт git commits, новые test cases, измеримые artifacts. Если после
  execution-enforcer нет ни одного commit/test/file — он считает что задача провалена
  и говорит явно.
  Triggers: /execution-enforcer, /enforce, "превратить в действия", "сделай commit",
  "execute this plan", "no more reports", action enforcer.
  НЕ для: planning (use /atomize), brainstorming (use /brainstorming), pitch creation.
triggers: [/execution-enforcer, /enforce, "превратить в действия", "сделай commit", "execute this plan", "no more reports", "action enforcer"]
---

# Execution Enforcer — Audit-to-Artifact Pipeline

## BSV (Behavior-Signal-Value)

**Behavior:** Запускается когда есть план, аудит, action backlog или список задач — но нет
реальных изменений в кодовой базе. Не обсуждает, не переформатирует, не улучшает отчёт.
Берёт первый приоритетный action → превращает в /goal → выполняет → подтверждает артефактом.

**Signal:** Любой из triggers выше. Или: пользователь принёс markdown с action items и хочет
движения, а не ещё один отчёт. Или: /office-hours дал Assignment, /source-distiller дал
action_backlog.md — следующий шаг это /execution-enforcer.

**Value:** Закрывает intention-action gap. Одна сессия enforcer = ≥1 реальный commit/test/artifact.
Без enforcer: 80% аудитов умирают в markdown, не доходя до кода.

---

## HARD RULES

- Не закрывать задачу без минимум ОДНОГО из: git commit | test added | external artifact (file != markdown report) | URL submitted
- Markdown отчёты НЕ считаются результатом
- LLM-сессия НЕ считается результатом
- /goal без verify command = недостаточно — добавить verify обязательно
- Если за N turns не появилось external artifact — STOP, признать failure, не маскировать
- "Mostly done" без SHA = не done
- Переименовать planning.md в plan.md = не прогресс

---

## Pipeline (6 шагов, строго последовательно)

### Шаг 1 — Read input
Принять на вход один из:
- `/atomize` output (список bottlenecks с приоритетами)
- `/source-distiller` output (action_backlog.md из .distill/ папки)
- `/office-hours` Assignment section
- Любой markdown с numbered action items

Если input не структурирован — спросить: "Какой один action ты хочешь исполнить прямо сейчас?"

### Шаг 2 — Identify top-1 action
Критерии выбора (в порядке важности):
1. Наибольший impact на ближайший milestone
2. Наименьшие зависимости (можно сделать прямо сейчас)
3. Есть чёткий verify command (можно проверить автоматически)
4. Маленький scope (≤2 файла в идеале)

Если несколько кандидатов — назвать top-3, спросить пользователя, не выбирать за него при неоднозначности.

### Шаг 3 — Convert to /goal template

Обязательный формат:
```
/goal <END STATE>. Run <CMD> and show full output. Output must contain: <STRING>. Do NOT <CONSTRAINT>. or stop after <N> turns.
```

Заполнить все поля:
- `<END STATE>` — конкретное изменение в файлах или системе (не "исправить", а "hook X returns Y on input Z")
- `<CMD>` — реальная команда (pytest, git log, cat файл) — не "проверь вручную"
- `<STRING>` — литеральная строка в output (SHA, PASSED, строка в файле)
- `<CONSTRAINT>` — что нельзя (не менять тесты, не добавлять noqa без обоснования)
- `<N>` — turn budget (lint=10, TDD=25, coverage=30, CI=70)

### Шаг 4 — Execute

Варианты:
- Выполнить /goal напрямую если задача достаточно чёткая
- Передать /goal как spec builder-агенту если задача требует множества файлов
- Для одиночных команд — запустить Bash напрямую

Во время execution — не отвлекаться на улучшение смежного кода. Scope = только top-1 action.

### Шаг 5 — Verify artifact

Проверить, что появился хотя бы один из:
- `git commit` — есть SHA в `git log --oneline -1`
- `test added` — новый test file или новая test function в существующем файле (grep подтверждает)
- `non-markdown artifact` — .py, .yaml, .json, .sh, .ts — не .md
- `URL submitted` — реальный external endpoint, не localhost

### Шаг 6 — Report или Failure declaration

Если verify прошёл → Output format (см. ниже).

Если verify не прошёл → объявить явно (см. Hard-fail rules ниже).

Не маскировать failure через "почти готово" или "следующий шаг — ...".

---

## Hard-fail rules (mandatory)

- If verify fails → output MUST start with `## EXECUTION FAILED` (exact string, required for grep detection)
- NEVER report "mostly done", "partially complete", "almost there"
- NEVER auto-create a markdown file as a fallback artifact (markdown is NOT an artifact)
- If `git commit` was attempted but pre-commit hook blocked → that is FAILED, not "blocked but ok"
- If test was added but test file is mock-only (asserts True / assert True) → that is FAILED, not "test added"
- Empty `git diff` after enforce attempt → FAILED

**Allowed artifact types (whitelist — anything else is NOT an artifact):**
- Real git commit (has SHA, non-zero diff)
- Test file in `tests/` directory with at least 1 non-trivial assertion
- Non-markdown file in source dirs (`.py`, `.ts`, `.js`, `.sh`, `.yaml`, `.json`, `.toml`, etc.)
- Email/document sent externally (with proof)
- Executed command with non-trivial captured output saved to file

**Failure mode output template (use verbatim):**
```
## EXECUTION FAILED
Stage that failed: <verify | execute | identify>
What WAS produced: <list>
What was NOT produced (required): <list>
Anti-pattern detected: <name>
Recommendation: <retry / split / kill / hand-off>
```

---

## Output Format

```markdown
## Execution Result

Status: COMMITTED | TESTED | ARTIFACT_CREATED | FAILED

Evidence:
  - commit_sha: <7-char SHA или "none">
  - test_file: <path или "none">
  - artifact_path: <path или "none">

Verify command: <команда которую пользователь может запустить сам>

Next /goal (if any):
  /goal <next action if pipeline continues>. Run <CMD>. Output must contain: <STRING>. or stop after <N> turns.
```

Если статус FAILED — дополнительно:
```markdown
Failure analysis:
  - Blocker: <что конкретно помешало>
  - Root cause: <почему blocker существует>
  - Next step: <retry scope | kill | escalate>
```

---

## Anti-Patterns Blocked

| Anti-pattern | Почему блокируется | Что делать вместо |
|---|---|---|
| Beautiful audit matrix без commit | Отчёт != результат. Матрица не деплоится. | Взять row #1 → /goal → commit |
| /goal без verify command | Нельзя подтвердить что done | Добавить `Run X, output must contain Y` |
| "Mostly done" без артефакта | Почти = не сделано | Declare FAILED, split task |
| Mocked test который всегда passing | Circular validation ([VERIFIED-SYNTHETIC]) | Real input или объявить [VERIFIED-SYNTHETIC] явно |
| Переименовать planning.md в plan.md | Косметика != прогресс | Нужен код или тест |
| "Следующая сессия доделаем" без SHA | Context потеряется | Commit NOW или declare FAILED |

---

## Integration Map

| Входящий скил | Что передать enforcer'у | Ожидаемый output |
|---|---|---|
| `/atomize` | Top bottleneck с priority score | git commit fixing bottleneck |
| `/source-distiller` | `.distill/action_backlog.md` row #1 | New file or test implementing action |
| `/office-hours` | "Assignment:" section | Email/commit/file matching assignment |
| `/gate-check` | STOP items из gate | Commit fixing stop condition |
| `/sci-code-audit` | HIGH finding | Fix commit + regression test |
| `/gsd-audit-fix` | Открытый bug | Fix + test + commit |

---

## Quick Reference

```
Есть план без артефактов?  → /execution-enforcer
После /atomize?            → /execution-enforcer берёт top bottleneck → ships commit
После /source-distiller?   → /execution-enforcer берёт action_backlog.md row #1 → artifact
После /office-hours?       → /execution-enforcer берёт Assignment → commits or emails
Нет артефакта после N turns? → FAILED, declare explicitly, never mask
```

## Companion Skills

| Скил | Когда использовать |
|---|---|
| `/atomize` | Обычно запускается ПЕРЕД execution-enforcer — находит bottleneck, который тот превращает в артефакт |
| `/refine-project` | Оркестратор, который вызывает execution-enforcer как финальную стадию цепочки /orient → /atomize → /execution-enforcer |

---

## STATUS: confirmed | VALIDATED: 2026-05-30 | tokens: ~600
