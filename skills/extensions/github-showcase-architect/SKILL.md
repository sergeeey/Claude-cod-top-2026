---
name: github-showcase-architect
description: >
  [STATUS: review] [CONFIDENCE: high] Превращает репозиторий в профессиональную витрину
  GitHub без хайпа и выдуманных метрик: 10 стадий от восстановления правды до
  adversarial-аудита. Триггеры: /repo-wow, /github-showcase, /showcase, «подготовь репо к
  публике», «сделай вау-репо». НЕ для: нового проекта с нуля, code review (→ /code-review),
  лендингов (→ /linkedin-post).
effort: medium
tokens: ~2500
triggers: [/repo-wow, /github-showcase, /showcase, "github showcase architect", "сделай вау-репо", "приведи в порядок репо для github", "подготовь репо к публике", "purpose review repo", "make repo professional", "audit repo for github", "showcase repo"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : github-showcase-architect
TL;DR  : Превращает репо в trust-building GitHub showcase — 30s wow, 3min trust, 10min run
Вызов  : /repo-wow, /github-showcase, "сделай вау-репо", "audit repo for github"
НЕ для : Создания проекта с нуля, code review без позиционирования
-->

# GitHub Showcase Architect

## Core Principle

Репозиторий считается **showcase-ready** только если serious external reader понимает:

1. Что это за проект
2. Почему это важно
3. Что реально реализовано
4. Как воспроизвести результаты
5. Что НЕ claims (boundaries)
6. Насколько trustworthy репо
7. Какой next step

Это **не hype generator**. Это **trust-builder**. Для научных проектов trust > wow.

## Hard Boundaries (NEVER violate)

- ❌ НЕ выдумывать метрики
- ❌ НЕ claim что тесты passed, если их не запускал
- ❌ НЕ claim CI exists без файла `.github/workflows/*.yml`
- ❌ НЕ claim public-safe если sensitive files remain
- ❌ НЕ превращать uncertainty в marketing
- ❌ НЕ убирать научную осторожность ради wow-effect
- ❌ НЕ rewrite git history без explicit approval
- ❌ НЕ делать репозиторий публичным
- ❌ НЕ pushать в remote без explicit approval

## Mandatory Process — 10 Stages

### Stage 1 — Project Truth Recovery

Прочитать в указанном порядке:

```
README.md
PROJECT_STATUS.md (если есть)
CHANGELOG.md (если есть)
pyproject.toml / package.json / Cargo.toml / equivalent
LICENSE
CITATION.cff
.github/workflows/*.yml
docs/
tests/
scripts/
data/README*
git status
git log --oneline -10
git tag
.gitignore
```

Inferred attributes (только то что подтверждается файлами/командами):

- project type (library / app / research / pipeline / tool)
- intended audience
- real maturity (prototype / beta / production)
- strongest result
- unresolved blockers
- sensitive files
- overclaim risk

**Запрещено inferr-ить факты которые не supported by repo files.**

### Stage 2 — Audience Positioning

Классифицировать primary showcase target (1 из):

| Аудитория | Критерии 30s / 3min / 10min |
|---|---|
| Research collaborator | reproducibility, citation, provenance |
| Professor / senior scientist | scientific rigor, methodology, falsifiability |
| Employer / recruiter | code quality, tests, CI, README clarity |
| Open-source user | install, quickstart, API docs |
| Competition judge | results matrix, evidence, fairness |
| Investor / client | value prop, traction, defensibility |
| Internal team | architecture, contributing guide, decisions |

Для каждой target audience определить:
- что они **должны увидеть** в 30 сек
- что они **должны довериться** в 3 мин
- что они **должны смочь запустить** в 10 мин

### Stage 3 — Wow Angle Selection

Найти **ровно одно** primary positioning sentence по шаблону:

> "This repository is a **[type]** that helps **[audience]** achieve **[outcome]** by **[mechanism]**, while explicitly avoiding **[overclaim/risk]**."

**Для research проектов prefer:** reproducibility, provenance, testability, auditability, uncertainty discipline, executable evidence.

**Avoid bare claims** (unless independently supported):
- "breakthrough"
- "proves" / "refutes"
- "revolutionary"
- "best"
- "state-of-the-art"

### Stage 4 — README Architecture

Rewrite/предложить README структуру (13 секций, по порядку):

```
1.  Hero section
    - one-sentence value proposition
    - status badges
    - 3-5 key facts
    - safety/claim boundary (если применимо)
2.  Why this matters
3.  What this repository does
4.  What this repository does NOT do
5.  Quickstart
6.  Reproduce results
7.  Project architecture
8.  Key artifacts
9.  Evidence / test status
10. Data and licensing boundaries
11. Citation
12. Roadmap
13. Contact / author note
```

README должен быть читаемым **И** для technical, **И** для non-technical reviewers.

### Stage 5 — Visual Layer

Создать или предложить spec для:

```
docs/assets/repo-social-preview-spec.md
docs/assets/architecture_diagram.md
docs/assets/workflow_diagram.md
```

Если image generation недоступен — создать precise visual specs.

**Recommended visual artifacts:**

1. **Social preview image** (1280x640px):
   - title
   - one-line value proposition
   - 3 proof points
   - clean dark/light theme
   - no clutter

2. **Architecture diagram** (Mermaid или ASCII):
   - inputs → processing → tests → outputs → boundaries

3. **Result dashboard** (таблица в README):
   - tests count + status
   - coverage %
   - CI badge
   - license
   - citation status
   - release tag
   - known blockers

### Stage 6 — Engineering Hygiene Audit

Проверить и report:

| Check | Pass criterion |
|---|---|
| Tests pass | `pytest` / `npm test` exit 0 |
| Lint pass | `ruff check .` / `eslint .` clean |
| CI exists | `.github/workflows/*.yml` present + recent runs green |
| LICENSE | File exists + recognized SPDX |
| CITATION.cff | Present for research repos |
| CHANGELOG.md | Recent entries match commits |
| No tracked `__pycache__` | `git ls-files` clean |
| No tracked secrets | grep-scan для `*_KEY`, `*_SECRET`, `*.pem` |
| No private data | `data/` без PII |
| `.gitignore` correct | covers common build artifacts |
| Reproducibility scripts run | as documented in README |
| Generated artifacts idempotent | hash-stable across runs |
| Package version matches | `__version__` == git tag |
| Release tag exists | если CHANGELOG/README claims release |

### Stage 7 — Public-Safety / Data-Safety Gate

Перед suggestion of public release **обязательно** проверить:

```
Third-party PDFs              → NEVER track
Derived datasets              → check licensing
Private correspondence        → NEVER track
Unpublished materials         → check author approval
API keys / tokens             → MUST be removed + history cleaned
Private paths                 → strip from configs
Personal emails               → redact
Claims requiring permission   → verify approval
```

Если sensitive data exist → **recommend**:
1. Keep repo PRIVATE
2. Untrack derived files (`git rm --cached`)
3. Add `MANIFEST.md` explaining excluded files
4. Clean git history before public (BFG / git-filter-repo)
5. Get author/owner approval

### Stage 8 — Overclaim Gate

Для **каждого** major claim в README/docs классифицировать:

| Метка | Критерий |
|---|---|
| `[VERIFIED-REAL]` | Source-confirmed с URL/file:line |
| `[VERIFIED-SYNTHETIC]` | Test-confirmed на synthetic data |
| `[INFERRED]` | Logical conclusion из verified facts |
| `[HYPOTHESIS]` | Plausible, not tested |
| `[MARKETING]` | Selling claim — REWRITE |
| `[UNSUPPORTED]` | No basis — REMOVE |

**Rewrite unsupported claims.**

Для **научных** проектов обязательные boundaries:
- Что воспроизведено
- Что НЕ воспроизведено
- Что остаётся author-dependent
- Что нельзя claim

### Stage 9 — Final Score

Score каждое измерение 0-10:

```
First impression           __ /10
Truthfulness               __ /10
Reproducibility            __ /10
Engineering hygiene        __ /10
Visual clarity             __ /10
Documentation structure    __ /10
Public-safety readiness    __ /10
Portfolio value            __ /10
Reviewer confidence        __ /10
Adversarial robustness     __ /10   (Stage 10: 0 count-drift + survives skeptic)
```

Provide:
- **Current score** (weighted average)
- **Target score** (after fixes)
- **Top 5 fixes** (concrete, prioritized)
- **Exact commands** для каждого fix
- **Files to edit** (path:line where applicable)
- **Expected final score** после fixes

### Stage 10 — Adversarial Audit (выдержит ли «докапывание»?)

**Зачем:** Stages 1-9 СТРОЯТ витрину. Stage 10 её АТАКУЕТ — разные роли, builder не заменяет attacker.
Внешний критик (рецензент, конкурент, дотошный employer) ищет не красоту, а **несоответствия**.
Эта стадия их находит ДО него.

**10.1 — Canonical count-drift check (детерминированно, не на глаз):**
Пересчитать ВСЕ числа из README/docs против РЕАЛЬНОГО filesystem методом CI, не доверяя тексту.
```bash
# hooks (исключить support libs, как делает CI):
ls hooks/*.py | grep -v __pycache__ | wc -l
# agents (исключить служебные файлы, не являющиеся агентами):
ls agents/*.md | wc -l
# tests/coverage: брать из CI-вывода, НИКОГДА из локального счёта (env-зависим)
```
Затем `grep -rnE '[0-9]+ (hooks|agents|skills|tests)'` по README + docs/ + служебным файлам —
КАЖДОЕ упоминание должно равняться canonical. Несовпадение = drift = FAIL.
**Типичный кейс:** «56 modules» в заголовке vs «57» в badge; CI-скрипт сам считал служебный файл как элемент каталога.
«CI зелёный» ≠ «числа верны» — green может значить «два неверных значения совпали».

**10.2 — Hostile reviewer simulation (делегировать независимому субагенту с context-asymmetry):**
Дать независимому ревьюеру (отдельный субагент или новая сессия без контекста) ТОЛЬКО README + код, БЕЗ объяснений автора (иначе agreeableness bias). Промпт:
> «Ты враждебный рецензент. Найди: (1) число, не сходящееся с кодом; (2) claim без доказательства
> (phantom test count, "production-ready" без CI evidence); (3) что в README противоречит коду;
> (4) самое слабое место, на котором развалится демо. Не хвали — ломай.»

**10.3 — Verdict:** репо «adversarial-ready» ТОЛЬКО если 10.1 = 0 drift И независимый ревьюер не нашёл phantom claims.
Иначе — список fixes ПЕРЕД публикацией.

## Output

Создать `docs/GITHUB_SHOWCASE_AUDIT.md` со структурой:

```markdown
# GitHub Showcase Audit — <repo name>

## 1. Executive Verdict
Current: X/10 → Target: Y/10. Top 3 blockers: ...

## 2. Current Score / Target Score
[Полная таблица 9 dimensions]

## 3. Best Positioning Sentence
"This repository is a [type] that helps [audience] achieve [outcome] by [mechanism], while explicitly avoiding [overclaim/risk]."

## 4. Audience-Specific First Impression
- 30 sec view: ...
- 3 min trust: ...
- 10 min run: ...

## 5. README Rewrite Plan
[Section-by-section diff]

## 6. Visual Asset Plan
[Specs для preview/diagram/dashboard]

## 7. Engineering Hygiene Findings
[14-check matrix]

## 8. Public-Safety Findings
[Sensitive data inventory + actions]

## 9. Overclaim Fixes
[Claim-by-claim taxonomy + rewrites]

## 10. 30-minute Fixes
[Quick wins ranked by ROI]

## 11. 2-hour Fixes
[Substantial changes]

## 12. Before-Public-Release Checklist
[Mandatory gates]
```

## Optional Implementation

Если user approve — **implement**:

| Action | File |
|---|---|
| README rewrite | `README.md` |
| Social preview spec | `docs/assets/social_preview_spec.md` |
| Architecture doc | `docs/ARCHITECTURE.md` |
| Reproducibility guide | `docs/REPRODUCIBILITY.md` |
| Public release checklist | `docs/PUBLIC_RELEASE_CHECKLIST.md` |
| Badges update | README header |
| CHANGELOG entry | `CHANGELOG.md` |
| CITATION update | `CITATION.cff` |
| Fix broken scripts | `scripts/*.sh` |
| Remove tracked trash | `.gitignore` + `git rm --cached` |
| Atomic commits | one logical change per commit |

## Companion Skills

| Когда | Skill |
|---|---|
| После Stage 9 — нужны actionable goals | список задач из Top 5 fixes |
| Doc writing | любой doc-writer навык/агент, если установлен |
| Final security check | любой security-review навык, если установлен |

## Final Report Template

После execution:

```markdown
## github-showcase-architect — Final Report

**Files changed:** N
**Commands run:** [list]
**Tests/lint results:** [pass/fail + numbers]
**Remaining risks:** [list]
**Final score:** X/10 (was Y/10)
**Commit hash (если committed):** <sha>
**PR URL (если pushed):** <url>
**Public release readiness:** READY / NEEDS-FIX / BLOCKED
```

## Anti-patterns (NEVER)

| Anti-pattern | Что не делать |
|---|---|
| README pretty без сути | Hero без real value prop |
| Hide blockers | Section "What this does NOT do" обязательна |
| Auto-make public | Только после Stage 7 PASS + explicit approval |
| Marketing science | "Breakthrough" / "proves" без external verification |
| Inflate score | Stage 9 должен быть честным — 5/10 better than fake 9/10 |
| Skip CITATION.cff | Для research repos обязательно |
| Generate fake metrics | Tests count должен matchать `pytest --co` output |

## Validation Checklist (skill self-test)

Перед declaring done проверить:

- ☐ Все 10 stages completed
- ☐ `docs/GITHUB_SHOWCASE_AUDIT.md` exists
- ☐ Каждый claim в README имеет evidence marker
- ☐ Stage 7 Public-Safety Gate явно ran
- ☐ Stage 8 Overclaim Gate явно ran
- ☐ Stage 10 Adversarial Audit ran — count-drift = 0 + независимый ревьюер нашёл 0 phantom claims
- ☐ Final score включает 9 dimensions
- ☐ Top 5 fixes имеют exact commands + file paths
- ☐ Repo НЕ pushed/published без explicit approval
- ☐ Git history НЕ rewritten без explicit approval

## References

- [GitHub Docs: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [GitHub Docs: Licensing a repository](https://docs.github.com/articles/licensing-a-repository)
- [GitHub Docs: About CITATION files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)
- [GitHub Docs: Social media preview](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)
- [GitHub Actions docs](https://docs.github.com/actions)

---

**Last updated:** 2026-06-01
**Status:** ACTIVE
**Default mode:** read-only audit (без implementation)
**Implementation:** только по explicit approval после Stage 9

## Архив: полное описание из frontmatter (перенесено 2026-10-03)

Описание в frontmatter сокращено до маршрутизации (листинг скиллов ограничен бюджетом). Полный исходный текст, дословно:

> [STATUS: confirmed] [CONFIDENCE: high] [REVIEWED: 2026-06-01] Превращает любой репозиторий в professional, trust-building GitHub showcase. Не hype generator. Не overclaim generator. Цель — чтобы за 30 сек человек понял ценность, за 3 мин поверил, за 10 мин запустил. Аудитория: research collaborator, professor, employer, OSS user, judge, investor, internal team. 10 mandatory stages: truth recovery → audience positioning → wow angle → README architecture → visual layer → engineering hygiene → public-safety gate → overclaim gate → final score → adversarial audit (count-drift check + hostile reviewer simulation). Hard boundaries: не выдумывать метрики, не публиковать без approve, не делать публичным если есть sensitive data, не убирать научную осторожность ради wow. Triggers: /repo-wow, /github-showcase, /showcase, github showcase architect, "сделай вау-репо", "приведи в порядок репо для github", "подготовь репо к публике", "purpose review repo", "make repo professional", "audit repo for github", "showcase repo". НЕ для: создания нового проекта с нуля, code review без positioning (→ /code-review), маркетинговых лендингов (→ /linkedin-post).
