# Руководство по Skills

## Что такое Skills

Skills — механизм Progressive Disclosure в Claude Code.
При старте загружается только `name` + `description` (~100 токенов на все skills).
Полный SKILL.md читается только когда trigger word срабатывает.

## Формат SKILL.md

```yaml
---
name: my-skill
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]
  Описание skill в 1-2 предложениях.
  Triggers: keyword1, keyword2, keyword3.
---

# Skill Title

## Когда загружать
(условия активации)

## Инструкции
(конкретные действия)

## Антипаттерны
(что НЕ делать)
```

## YAML Frontmatter

### Обязательные поля
- `name` — уникальное имя (max 64 символа)
- `description` — описание + триггеры (max 1024 символа)

### Lifecycle маркеры (в description)
- `STATUS`: draft → confirmed → review → deprecated
- `CONFIDENCE`: low → medium → high
- `VALIDATED`: дата последней проверки

## CSO — Claude Search Optimization

**Критически важно**: description должен начинаться с условий активации ("Use when..."),
а НЕ с описания workflow.

Плохо: "Пошаговый процесс code review с 2-stage проверкой..."
Хорошо: "[STATUS: confirmed] Code review для финансовых приложений. Triggers: аудит, ревью, security."

**Почему**: если description описывает workflow, Claude следует description и пропускает SKILL.md.

## Жизненный цикл

1. **draft** — новый skill, не тестировался
2. **confirmed** — протестирован, работает стабильно
3. **review** — не использовался 2+ месяца, требует проверки
4. **deprecated** — устарел, готовится к удалению

Рекомендация: раз в неделю проверяй skills, обнови VALIDATED у актуальных.

## Структура директории

```
skills/
└── my-skill/
    ├── SKILL.md           # Основные инструкции (обязательно)
    ├── references/        # Справочные материалы (опционально)
    │   └── api_docs.md
    └── scripts/           # Утилиты (опционально)
        └── helper.py
```

## Наши Skills

### archcode-genomics
Симуляция хроматиновой экструзии для анализа патогенности вариантов.
30318 ClinVar вариантов, 9 валидированных локусов.

### brainstorming
Socratic Design — 2-3 альтернативы с trade-offs.
Hard gate: "design approved" перед написанием кода.

### geoscan
GeoScan Gold: Sentinel-2 спектральные индексы, Isolation Forest, lineament detection.
AUC=0.85, Phase B complete.

### git-worktrees
Изолированные рабочие копии для экспериментов и параллельной работы.

### mentor-mode
Расширенный педагогический режим с аналогиями из security/финансов.

### notebooklm
Query Google NotebookLM notebooks. Browser automation, persistent auth.

### security-audit
Security audit для финансовых приложений KZ. ARRFR compliance, IIN дедупликация.

### suno-music
Suno AI prompt engineering для EDM, hardstyle, hyperpop, rap-drill.

## Как создать новый skill

1. Создай директорию: `~/.claude/skills/my-skill/`
2. Создай `SKILL.md` с YAML frontmatter
3. Установи STATUS: draft, CONFIDENCE: low
4. Протестируй: убедись что триггеры срабатывают
5. Обнови STATUS: confirmed после успешного тестирования
