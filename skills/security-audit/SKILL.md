---
name: security-audit
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]
  Security audit для финансовых приложений KZ. ARRFR compliance, IIN дедупликация,
  fraud detection patterns, микрофинансовый домен.
  Triggers: аудит, уязвимость, ARRFR, фрод, fraud, IIN, безопасность, compliance, PCI.
---

# Security Audit Skill

## Домен
Микрофинансовые организации Казахстана, ARRFR compliance, fraud detection.

## Чеклист безопасности (перед production deploy)

### 1. PII Protection
- [ ] ИИН (IIN) — 12 цифр, формат YYMMDDGXXXXX — НИКОГДА в логах plain text
- [ ] БИН (BIN) — 12 цифр, юрлица — маскировать в выводе
- [ ] Банковские реквизиты — только last 4 digits в UI
- [ ] Email/телефон — маскировать в логах (ivan@*****.kz, +7 7** *** **12)

### 2. Authentication & Authorization
- [ ] JWT токены: refresh rotation, short-lived access (15 мин)
- [ ] Rate limiting на auth endpoints (5 попыток / 15 мин)
- [ ] IP whitelisting для admin endpoints
- [ ] 2FA для операций выше порога (configurable)

### 3. Data Layer
- [ ] SQL: ТОЛЬКО параметризованные запросы (SQLAlchemy ORM или text() с bindparams)
- [ ] NoSQL: входные данные — Pydantic validation ПЕРЕД записью
- [ ] Encryption at rest для PII полей (AES-256)
- [ ] Audit log для всех CRUD операций с PII

### 4. ARRFR Compliance (Казахстан)
- [ ] Хранение данных — только на территории KZ (или approved cloud regions)
- [ ] Срок хранения PII — согласно закону о персональных данных РК
- [ ] Согласие на обработку — tracked в БД с timestamp
- [ ] Право на удаление — реализован endpoint для data erasure

### 5. Fraud Detection Patterns
- **Velocity check:** > 3 заявки с одного IP за час → флаг
- **IIN дедупликация:** один IIN = один клиент, cross-check по всем продуктам
- **Device fingerprint:** коллизия fingerprint + разные IIN → высокий риск
- **Geo-anomaly:** заявка из региона, отличного от регистрации IIN → medium risk

## Criminal Code KZ (релевантные статьи)
- Ст. 190 — Мошенничество (fraud)
- Ст. 210 — Незаконное получение кредита
- Ст. 213 — Легализация доходов (AML)

## Инструменты
- `reviewer` агент — code review перед коммитом
- `redact.py` hook — автоочистка PII перед внешними MCP
- `ruff` — статический анализ Python кода
