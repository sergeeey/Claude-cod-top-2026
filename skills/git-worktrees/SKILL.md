---
name: git-worktrees
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]
  Изолированные рабочие копии для экспериментов и параллельной работы.
  Triggers: worktree, эксперимент, параллельная ветка, изолированная копия.
---

# Skill: Git Worktrees

## Когда загружать
- Эксперимент с неясным исходом (может потребоваться откат)
- Параллельная работа над 2+ задачами
- Крупный рефакторинг при необходимости держать рабочую версию

## Принцип
Worktree = изолированная рабочая копия. Дешевле чем stash/switch, безопаснее чем работа в одном дереве.

---

## Decision Matrix: branch vs worktree

| Ситуация | Branch | Worktree | Почему |
|----------|--------|----------|--------|
| Фикс бага в 1-2 файла | v | | Overhead worktree не оправдан |
| Эксперимент (может не пригодиться) | | v | Чистый откат = удалить папку |
| Параллельная работа (2 задачи) | | v | Не нужно stash/switch |
| Крупный рефакторинг 5+ файлов | | v | Основная ветка остаётся рабочей |
| Обычная фича 3-5 файлов | v | | Worktree = overkill |
| CI/CD проверка другой ветки | | v | Не прерывает текущую работу |

**Правило:** worktree = рекомендация, не мандат. Обычный branch покрывает 80% случаев.

---

## Workflow

### 1. Создание worktree
```bash
# EnterWorktree создаёт worktree автоматически (Claude Code built-in)
# Или вручную:
git worktree add ../project-experiment feature/experiment
cd ../project-experiment
```

### 2. Работа в worktree
- Worktree = полноценная рабочая копия с отдельным HEAD
- Можно параллельно работать в основном дереве и worktree
- Коммиты в worktree идут в свою ветку

### 3. Merge результата
```bash
# Из основного дерева:
git merge feature/experiment
# Или cherry-pick конкретных коммитов:
git cherry-pick <commit-hash>
```

### 4. Cleanup
```bash
git worktree remove ../project-experiment
# Или если ветка больше не нужна:
git worktree remove ../project-experiment
git branch -d feature/experiment
```

---

## Claude Code интеграция

Claude Code имеет встроенный `EnterWorktree` tool:
- Автоматически создаёт worktree в соседней директории
- Переключает контекст на новое дерево
- После завершения — merge и cleanup

**Когда использовать EnterWorktree:**
1. План содержит 5+ шагов с высоким риском каскадных ошибок
2. Сергей просит "попробуй, но чтобы можно было откатить"
3. Параллельная задача при незаконченной текущей

---

## Anti-patterns

| Не делай | Почему |
|----------|--------|
| Worktree для каждой мелкой правки | Overhead > benefit |
| Забывать cleanup после merge | Копятся мёртвые директории |
| Работать в worktree без ветки | Detached HEAD = потерянные коммиты |
| Несколько worktree на одну ветку | Git не позволит (и правильно) |
