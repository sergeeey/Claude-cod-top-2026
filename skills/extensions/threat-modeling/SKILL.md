---
name: threat-modeling
sub_type: guide
version: "1.0"
source: "wshobson/agents (adapted)"
description: >
  Структурированный threat modeling по методологиям STRIDE, PASTA, и Attack Trees.
  Идентифицирует угрозы ДО написания кода или перед security review.
  Используй перед разработкой auth/payment/API систем, при изменении security architecture,
  при добавлении внешних интеграций, или при compliance требованиях (SOC2, HIPAA, PCI-DSS).
  Триггеры: /threat-modeling, "threat model", "stride analysis", "attack vectors",
  "security threats", "threat assessment", "моделирование угроз", "анализ угроз", "attack surface".
tokens: ~350
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : threat-modeling
TL;DR  : STRIDE + PASTA + Attack Trees — систематическая идентификация угроз до/во время разработки
Вызов  : /threat-modeling, threat model, stride, attack vectors, анализ угроз
НЕ для : Code review на уязвимости (→ /sec-auditor); production incident (→ incident response)
-->

# Threat Modeling — Systematic Security Analysis

## Зачем ПЕРЕД кодом

Security bugs дешевле исправить на этапе дизайна чем после деплоя.
Threat modeling — это **структурированный вопрос:** "Что может пойти не так?"

**Три метода:**
- **STRIDE** — по типам угроз (быстро, systematic)
- **PASTA** — по business risk (глубже, требует больше времени)
- **Attack Trees** — по конкретным целям атаки (детально, для critical paths)

---

## STRIDE Analysis

STRIDE = Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation of Privilege.

### Шаг 1 — Определи Scope

```markdown
## Система: [Name]
## Границы: [что in-scope, что out-of-scope]
## Assets: [что защищаем — данные, функции, репутация]
## Actors: [кто использует — legitimate users, attackers, third-party systems]
```

### Шаг 2 — Data Flow Diagram (упрощённый)

```
[Browser] → HTTPS → [API Gateway] → [App Server] → [Database]
                                 ↘ [Cache (Redis)]
                                 ↘ [External API]
```

Для каждого **стрелки** (data flow) и **прямоугольника** (process/store) — применяй STRIDE.

### Шаг 3 — STRIDE Matrix

| Угроза | Описание | Пример | Мера защиты |
|--------|----------|--------|-------------|
| **S**poofing | Притворяться кем-то другим | Поддельный JWT, CSRF | AuthN, MFA, HTTPS |
| **T**ampering | Изменение данных | SQL injection, Man-in-Middle | Input validation, HTTPS, integrity checks |
| **R**epudiation | Отрицание совершённых действий | "Я не делал этот transfer" | Audit logs, digital signatures |
| **I**nformation Disclosure | Утечка данных | Directory traversal, verbose errors | Access control, error handling, encryption |
| **D**enial of Service | Недоступность | Rate limit bypass, memory exhaustion | Rate limiting, circuit breakers, autoscaling |
| **E**levation of Privilege | Получение лишних прав | IDOR, privilege escalation | AuthZ, RBAC, least privilege |

### Шаг 4 — Findings Table

| ID | Компонент | STRIDE Category | Угроза | Severity | Мера | Status |
|----|-----------|-----------------|--------|----------|------|--------|
| T001 | API/auth | Spoofing | Слабые JWT секреты | HIGH | Rotate keys, use RS256 | TODO |
| T002 | DB queries | Tampering | SQL injection | CRITICAL | Parameterized queries | DONE |

---

## PASTA (Process for Attack Simulation and Threat Analysis)

Для систем с высоким business risk (payments, medical, financial):

```
Шаг 1: Define Business Objectives
  → Что бизнес потеряет при атаке? (revenue, reputation, compliance)

Шаг 2: Define Technical Scope
  → Какие компоненты, APIs, data stores in-scope?

Шаг 3: Application Decomposition
  → DFD, trust boundaries, entry points

Шаг 4: Threat Analysis
  → Threat actors (insider, external, nation-state), их motivation, capability

Шаг 5: Vulnerability Analysis
  → Существующие CVE, misconfigurations, design flaws

Шаг 6: Attack Modeling
  → Attack trees для top-3 threat scenarios

Шаг 7: Risk/Impact Analysis
  → Probability × Impact = Risk Score → Prioritized remediation
```

---

## Attack Trees

Для критических paths (login, payment, admin access):

```
GOAL: Получить доступ к admin panel
├── Bypass Authentication
│   ├── Brute force password [MITIGATED: rate limit]
│   ├── Exploit JWT vulnerability [OPEN: verify alg validation]
│   └── Session fixation attack [OPEN: check session regeneration]
├── Privilege Escalation  
│   ├── IDOR in user API [MITIGATED: ownership check]
│   └── Role manipulation via API [OPEN: verify server-side check]
└── Social Engineering
    └── Phish admin credentials [PARTIAL: MFA required]
```

**Формат ноды:**
- `[MITIGATED: описание]` — защита есть
- `[OPEN: что проверить]` — нужна проверка
- `[ACCEPTED: обоснование]` — risk accepted

---

## Integration с Разработкой

### Когда запускать
- Перед дизайном новой auth системы
- При добавлении внешних API/webhooks
- Перед compliance review (SOC2, PCI-DSS, HIPAA)
- При изменении trust boundaries

### Артефакты
```
docs/security/threat-model-[component]-[date].md
  ├── Scope
  ├── DFD
  ├── STRIDE Matrix
  ├── Findings Table (severity ordered)
  └── Remediation Plan
```

### Severity Levels
| Level | Критерий | Action |
|-------|----------|--------|
| CRITICAL | Прямой доступ к данным / RCE | Блокирует релиз |
| HIGH | Privilege escalation / data leak | Fix перед merge |
| MEDIUM | Limited impact / requires auth | Fix в следующем спринте |
| LOW | Defense in depth / hardening | Backlog |

---

## Связанные скилы

- `sec-auditor` — code-level аудит (после threat model → конкретные проверки)
- `security-guard` — финансовый security checklist
- `protect-mcp` — policy enforcement для MCP tool calls
- `falsification-ladder` — систематическое доказательство что защита работает
