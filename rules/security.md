# Security Rules

## Финансовая специфика (KZ)
- PII (ИИН, БИН, счета) → никогда в логах/выводе plain text
- Secrets → только env vars, НИКОГДА в коде или коммитах
- SQL → ТОЛЬКО параметризованные запросы, без string concatenation
- Входные данные → Pydantic validation ДО обработки

## PII Policy
- При работе с данными пользователей → приоритет локальному инференсу (Ollama)
- PII не должны покидать контур. Если Ollama недоступен → маскируй перед облаком
- Redaction hook автоматически очищает PII перед внешними MCP-серверами

## Перед коммитом в production
- Запустить `reviewer` агент для code review
- Проверить: нет ли hardcoded secrets, SQL injection, XSS vectors
- Для финансового кода: reviewer + ручной security checklist обязательны
