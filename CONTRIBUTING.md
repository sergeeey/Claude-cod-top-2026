# Contributing / Как контрибьютить

[English](#english) | [Русский](#русский)

---

## English

Thank you for your interest in contributing to Claude Code Config!

### How to Contribute

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature`
3. **Make changes** following the guidelines below
4. **Test**: run `bash tests/test_all.sh` before submitting
5. **Commit**: use [Conventional Commits](https://www.conventionalcommits.org/) format
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation only
   - `refactor:` — code change that neither fixes nor adds
   - `test:` — adding or updating tests
6. **Open a Pull Request** against `main`

### Code Style

- **Shell scripts**: POSIX-compatible bash, `set -e`, quote all variables
- **Python hooks**: Python 3.8+, type hints, no external dependencies
- **Markdown**: ATX headings (`#`), fenced code blocks, max 100 chars/line
- **Line endings**: LF only (enforced by `.gitattributes`)

### What We Welcome

- New hooks (deterministic guards for Claude behavior)
- New skills (domain knowledge with CSO-optimized descriptions)
- Translations and localization
- Bug reports with reproduction steps
- Performance improvements (token economy)

### What We Don't Accept

- Changes that break backward compatibility without discussion
- Features that increase CLAUDE.md beyond 60 lines (token budget)
- Dependencies on external packages in hooks (must be stdlib-only)
- Removal of Evidence Policy markers or security guards

### Pull Request Checklist

- [ ] Tests pass (`bash tests/test_all.sh`)
- [ ] No secrets or PII in committed files
- [ ] CHANGELOG.md updated (if user-facing change)
- [ ] Skill descriptions follow CSO format ("USE when...", not summary)

---

## Русский

Спасибо за интерес к проекту Claude Code Config!

### Как внести вклад

1. **Форкни** репозиторий
2. **Создай ветку**: `git checkout -b feature/твоя-фича`
3. **Внеси изменения** по правилам ниже
4. **Протестируй**: запусти `bash tests/test_all.sh` перед отправкой
5. **Коммит**: формат [Conventional Commits](https://www.conventionalcommits.org/)
   - `feat:` — новая фича
   - `fix:` — исправление бага
   - `docs:` — только документация
   - `refactor:` — рефакторинг без изменения поведения
   - `test:` — добавление/обновление тестов
6. **Открой Pull Request** в `main`

### Стиль кода

- **Shell-скрипты**: POSIX-совместимый bash, `set -e`, все переменные в кавычках
- **Python-хуки**: Python 3.8+, type hints, без внешних зависимостей
- **Markdown**: ATX-заголовки (`#`), fenced code blocks, макс. 100 символов/строка
- **Переносы строк**: только LF (контролируется `.gitattributes`)

### Что мы приветствуем

- Новые hooks (детерминированные стражи поведения Claude)
- Новые skills (доменные знания с CSO-оптимизированными описаниями)
- Переводы и локализация
- Баг-репорты с шагами воспроизведения
- Улучшения токен-экономии

### Что мы не принимаем

- Изменения, ломающие обратную совместимость без обсуждения
- Фичи, увеличивающие CLAUDE.md свыше 60 строк (бюджет токенов)
- Внешние зависимости в хуках (только stdlib)
- Удаление маркеров Evidence Policy или security guards

### Чеклист Pull Request

- [ ] Тесты проходят (`bash tests/test_all.sh`)
- [ ] Нет секретов и PII в коммите
- [ ] CHANGELOG.md обновлён (если user-facing изменение)
- [ ] Описания skills в CSO-формате ("USE when...", не пересказ)
