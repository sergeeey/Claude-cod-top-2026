# Coding Style Rules

## Backend (Python)
- Python 3.11+, type hints всегда
- ruff format (double quotes, 100 chars), structlog вместо print()
- Commits: feat/fix/docs/refactor/test
- PII (ИИН, БИН, счета) → никогда в логах plain text
- Secrets → только env vars, никогда в коде
- SQL → только параметризованные запросы
- Входные данные → Pydantic validation перед обработкой

## Frontend (React/TS)
- React + TypeScript (строгий, никаких `any`)
- Zustand для стейт-менеджмента, Tailwind для стилей
- Компоненты только функциональные, именование PascalCase

## Комментарии
- `# ПОЧЕМУ:` перед нетривиальными решениями
- При ошибках: "Ошибка была в X потому что Y, исправил через Z"
- При выборе: "Выбрал A вместо B потому что для нашего случая важнее X"
