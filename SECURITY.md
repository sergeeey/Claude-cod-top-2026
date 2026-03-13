# Security Policy / Политика безопасности

[English](#english) | [Русский](#русский)

---

## English

### Reporting a Vulnerability

If you discover a security vulnerability in this project, **please do not open a public issue**.

Instead, report it privately:

1. **Email**: Open a [private security advisory](https://github.com/sergeeey/Claude-cod-top-2026/security/advisories/new) on GitHub
2. **Or**: Contact maintainer **sergeeey** directly via GitHub

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact (what an attacker could achieve)
- Suggested fix (if you have one)

### Response Timeline

- **Acknowledgment**: within 48 hours
- **Assessment**: within 7 days
- **Fix**: critical issues within 14 days, others in next release

### Scope

This project is a configuration framework for Claude Code. Security-relevant areas include:

| Area | Risk | Example |
|------|------|---------|
| **PII Redaction hooks** | Data leakage | Bypass of masking in `redact.py` |
| **install.sh** | Code execution | Injection via crafted file paths |
| **settings.json** | Hook bypass | Disabling security hooks silently |
| **MCP profiles** | Data exfiltration | Malicious MCP server config |
| **Symlink mode** | Privilege escalation | Symlink following outside repo |

### Security Design Principles

This project follows these security principles by design:

- **No external dependencies** in hooks (stdlib-only Python)
- **PII never in logs** — redaction hook strips IIN, BIN, phone, email
- **Parameterized queries only** — SQL injection prevention in rules
- **Secrets in env vars only** — never hardcoded, never committed
- **Deny-by-default** — 17 deny patterns in settings.json

---

## Русский

### Сообщение об уязвимости

Если вы обнаружили уязвимость в этом проекте, **не открывайте публичный issue**.

Вместо этого сообщите приватно:

1. **GitHub**: откройте [приватное security advisory](https://github.com/sergeeey/Claude-cod-top-2026/security/advisories/new)
2. **Или**: свяжитесь с мейнтейнером **sergeeey** через GitHub

### Что включить в отчёт

- Описание уязвимости
- Шаги воспроизведения
- Потенциальное воздействие (что может сделать атакующий)
- Предлагаемое исправление (если есть)

### Сроки реагирования

- **Подтверждение получения**: в течение 48 часов
- **Оценка**: в течение 7 дней
- **Исправление**: критичные — 14 дней, остальные — в следующем релизе

### Область действия

Проект — конфигурационный фреймворк для Claude Code. Области, критичные для безопасности:

| Область | Риск | Пример |
|---------|------|--------|
| **PII Redaction хуки** | Утечка данных | Обход маскирования в `redact.py` |
| **install.sh** | Выполнение кода | Инъекция через crafted file paths |
| **settings.json** | Обход хуков | Тихое отключение security hooks |
| **MCP-профили** | Эксфильтрация данных | Вредоносный MCP-сервер в конфиге |
| **Symlink mode** | Эскалация привилегий | Symlink за пределы репо |

### Принципы безопасности проекта

- **Нет внешних зависимостей** в хуках (только stdlib Python)
- **PII никогда в логах** — redaction hook маскирует ИИН, БИН, телефон, email
- **Только параметризованные запросы** — защита от SQL injection в rules
- **Секреты только в env vars** — никогда в коде, никогда в коммитах
- **Deny-by-default** — 17 deny-паттернов в settings.json
