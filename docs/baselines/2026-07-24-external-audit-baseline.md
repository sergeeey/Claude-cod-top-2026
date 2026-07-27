# Baseline снимок — 2026-07-24 (внешний аудит + перепроверка)

> **Назначение.** Зафиксированная отправная точка. При каждом следующем ревью
> сравниваем текущее состояние с этим файлом: какие пункты закрыты, какие
> появились, куда сдвинулись метрики. Это не отчёт о работе, а **эталон для
> сравнения**.

## Точка отсчёта

| Поле | Значение |
|---|---|
| Commit | `6f51b8a22209e49053c77f1c746503662c05b163` |
| Ветка | `main` |
| Дата | 2026-07-24 |
| CI на этом SHA | ✅ зелёный (test 3.11, test 3.12, windows-install) |

## Ground-truth метрики (перепроверено инструментами, не с чужих слов)

| Метрика | Значение | Как получено |
|---|---|---|
| Hooks (py, без 3 shared-lib) | **95** | `ls hooks/*.py \| grep -v utils/hook_state/severity_calibrator \| wc -l` |
| Agents (md, без CLAUDE.md) | **13** | `ls agents/*.md \| grep -v CLAUDE.md \| wc -l` |
| Skills (SKILL.md) | **128** | `find skills -name SKILL.md \| wc -l` |
| Registry entries | **132** | `skills/registry.yaml` (128 SKILL + 4 orchestrator/pack) |
| Rules | **15** | `ls rules/*.md \| wc -l` |
| Test files | **97** | `ls tests/test_*.py \| wc -l` |
| Tests passing (CI) | **2450** | GitHub Actions на 6f51b8a |
| Coverage (измеряемый scope) | **79%** | `coverage report`; порог CI 75% |
| Event keys в settings.json | **24** | подсчёт top-level ключей `hooks/settings.json` |

## Две внешние оценки (side-by-side)

| Аудит | Итог | Оптика | Логика балла |
|---|---|---|---|
| Аудит A (product/idea) | **6.6/10** | продукт + идея + упаковка | взвешенное среднее по 27 осям |
| Аудит B (adversarial security) | **5.0/10** | security-first, blocker-gated | 2 HIGH в default-path потолочат балл независимо от остального |

Разница 6.6 vs 5.0 — **не противоречие**, а разная методология: B применяет
правило «открытый HIGH в дефолтном пути = потолок оценки», A усредняет. Обе
сходятся в главном: **сильная концепция и ядро, слабая независимая валидация,
критические проблемы упаковки, поверхность больше глубины доказательств.**

## Перепроверка ключевых claim'ов (мой [VERIFIED] ≠ их [VERIFIED])

Легенда: ✅ CONFIRMED (перепроверил инструментом) · ⚠️ PARTIAL · ❌ DISMISSED ·
🔲 NOT-RE-VERIFIED (правдоподобно, но сам не гонял).

### Упаковка / plugin (P0 обоих аудитов)
- ✅ **plugin.json не содержит `hooks` и `skills`** — только name/version/description/author. `[VERIFIED-read] .claude-plugin/plugin.json`.
- ✅ **`hooks/hooks.json` отсутствует** — `[VERIFIED-bash] ls`. → при `/plugin install` 95 хуков, вероятно, не подключаются.
- ✅ **Имена рассинхронизированы**: plugin.json = `claude-cod-top-2026`, marketplace.json = `claude-code-config`, README зовёт `claude-cod-top-2026`. `[VERIFIED-grep]`.
- 🔲 **skills вложены в core/extensions, plugin.json не задаёт пути skills** — структуру подтвердил, реальное поведение discovery в Claude Code не гонял.

### Безопасность (2 HIGH аудита B)
- ✅ **SEC-01: `Read(*)` в allow-листе, отдельного PreToolUse-guard на Read нет** — `[VERIFIED-read] settings.json:13`; PreToolUse matchers = Bash, Edit|Write, mcp__* (Read не покрыт). Инференс аудита (утечка домашних секретов в контекст) — правдоподобен, но runtime-PoC не выполнялся → сам эффект `[HYPOTHESIS]`, конфиг-предпосылка `[VERIFIED]`.
- ✅ **SEC-02: `mypy` и `ruff` в `SAFE_BASH_PREFIXES`** — `[VERIFIED-read] permission_policy.py:63-64`. mypy умеет грузить repo-controlled plugin из config — задокументированное поведение mypy. Реальный эффект `[HYPOTHESIS]` (PoC не гонял), но предпосылка `[VERIFIED]`.
- ✅ **`Bash(*)`, `Write(*)`, `Edit(*)` в allow-листе** — `[VERIFIED-read] settings.json:12-22`.
- ⚠️ **ВАЖНЫЙ КОНТЕКСТ:** живой `~/.claude` — это осознанный **MAX_AUTONOMY** вариант пользователя (см. память `max-autonomy-permission-policy`). Для личной машины `Bash(*)` — намеренный выбор. НО репозиторий шлёт этот же settings.json как **дефолт для чужих** — вот здесь находка реальна. Фикс обязан разделить «личный MAX_AUTONOMY» и «что мы ставим незнакомцу».

### Документация / дрейф метаданных
- ✅ **CITATION.cff устарел**: `89 hooks / 25 events / 125 skills / 2237 tests / 80%` против реальных `95 / 24 / 128 / 2450 / 79%`. `[VERIFIED-read]`.
- ✅ **AGENTS.md устарел**: строки 119-122 — `49 hooks / 14 agents / 32 skills / 37 test files / 1093 tests (2026-04-26)`. Ниже GitNexus-шапки. CI этот файл не контролирует. `[VERIFIED-grep]`. *(Первичный скепсис снят при более глубоком чтении — аудит был прав.)*
- ✅ **Тройной рассинхрон счётчика событий**: README «25 Events», AGENTS.md «27 events», реально **24**. `[VERIFIED]`.
- ✅ **Внутренние рабочие файлы в публичном репо**: `docs/CODEX_AUDIT_RESULTS.md`, `docs/SESSION_REPORT_2026-06.md`, `docs/_truth/`, `.claude/memory/`, `null_results/`. `[VERIFIED-ls]`.

### Skills: ширина vs глубина
- ✅ **Maturity почти не используется как инструмент честности**: `127 wired / 1 dogfooded / 0 benchmarked / 4 described`. Только 1 запись (`hypothesis-arbiter`) имеет реальный `maturity_evidence` на бенчмарк. `[VERIFIED-grep]`.

### Installer / прочее (ниже по приоритету, часть не перепроверял)
- 🔲 install.sh ставит `skills/extensions/README.md` как skill `README` — не нашёл паттерн быстрым grep, помечаю NOT-RE-VERIFIED.
- 🔲 install.sh счётчик файлов (264 vs 517), version drift баннеров (v2.1/v11.1), Python 3.8+ vs 3.11+ — NOT-RE-VERIFIED.
- 🔲 Updater `git pull origin main` (mutable, без provenance) — правдоподобно, не гонял.
- 🔲 Perf-числа аудита B (≈556ms на Edit) — синтетика в чужом контейнере, NOT-RE-VERIFIED.

## Единственная поправка к аудитам

Аудит A в блоке DOC-01 описал содержимое AGENTS.md как «49 hooks/1093 tests». На
первый взгляд файл — GitNexus-индекс (символы/связи), и я усомнился. **При
глубоком чтении — аудит прав**: устаревшие числа реально есть на строках 119-122,
под GitNexus-шапкой. Claim подтверждён, не отклонён. Остальные проверенные
claim'ы аудитов совпали с реальностью — качество аудитов высокое.

## Что НЕ трогаем этим baseline

Это снимок + план. Изменения кода (особенно security: `Read(*)`, mypy) —
T3/Red-tier, требуют явного решения пользователя (убрать `Read(*)` может сломать
собственный workflow). В план — да; в автономное исполнение сейчас — нет.
