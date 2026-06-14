---
name: protect-mcp
sub_type: guide
version: "1.0"
source: "wshobson/agents (adapted)"
description: >
  Добавляет криптографическое управление вызовами инструментов Claude Code через Cedar policies
  и Ed25519-подписанные receipts. Блокирует нарушающие policy вызовы ДО выполнения.
  Генерирует tamper-evident audit trail с hash-chaining. Используй когда нужен контроль доступа
  к MCP-серверам, audit trail для regulated industries, или policy enforcement для опасных команд.
  Триггеры: /protect-mcp, "cedar policy", "audit trail", "signed receipts", "mcp governance",
  "блокировать инструменты", "audit mcp", "protect tool calls".
tokens: ~300
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : protect-mcp
TL;DR  : Cedar policy enforcement + Ed25519 signed receipts для MCP tool calls
Вызов  : /protect-mcp, cedar policy, audit trail, mcp governance
НЕ для : Общий security review (→ /sec-auditor); тест кода на уязвимости (→ /security-guard)
-->

# Protect-MCP — Policy Enforcement + Signed Receipts

## Зачем

Claude Code session logs — mutable, unsigned, operator-bound. Для regulated industries нужны
tamper-evident доказательства которые третьи стороны могут независимо верифицировать.

**Что делает:**
- **PreToolUse hook**: Cedar policy оценивает каждый вызов инструмента ДО выполнения. Deny → блокировка.
- **PostToolUse hook**: Ed25519-подписанный receipt с hash tool_name + input/output + policy digest + timestamp.
- **Hash-chain**: Каждый receipt ссылается на предыдущий → вставка/удаление/модификация детектируются.
- **Offline verify**: `npx @veritasacta/verify receipt.json` без сервера или аккаунта.

**Стандарты:** Ed25519 (RFC 8032), JCS canonicalization (RFC 8785), Cedar authorization.

---

## Шаг 1 — Установка

```bash
# Установить плагин
claude plugin install wshobson/agents/protect-mcp

# Запустить сервер enforcement
npx protect-mcp@latest serve --enforce
```

---

## Шаг 2 — Создай Cedar Policy

Создай `./protect.cedar` рядом с проектом:

```cedar
// Запрет опасных bash-команд
forbid(
  principal,
  action == Action::"bash",
  resource
) when {
  resource.command like "*rm -rf*" ||
  resource.command like "*git push --force*" ||
  resource.command like "*DROP TABLE*"
};

// Разрешить только read-only операции в production
permit(
  principal,
  action in [Action::"read", Action::"glob", Action::"grep"],
  resource == Environment::"production"
);
```

**Cedar logic:**
- `permit` — явное разрешение
- `forbid` — явный запрет (приоритет над permit)
- `when { ... }` — условие на основе контекста
- По умолчанию: всё **запрещено** если нет явного permit

---

## Шаг 3 — Подключи Hooks

В `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "npx protect-mcp@latest evaluate --policy ./protect.cedar"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "npx protect-mcp@latest sign --output ./receipts/"
          }
        ]
      }
    ]
  }
}
```

---

## Шаг 4 — Верификация Receipts

```bash
# Верифицировать конкретный receipt
npx @veritasacta/verify ./receipts/receipt-001.json

# Верифицировать всю цепочку
npx @veritasacta/verify ./receipts/ --chain

# Экспорт audit log для compliance
npx protect-mcp@latest export --format csv > audit.csv
```

**Receipt содержит:**
- `tool_name` + `input_hash` + `output_hash`
- `policy_digest` (SHA-256 от protect.cedar)
- `timestamp` (ISO 8601)
- `prev_receipt_hash` (hash-chain link)
- `signature` (Ed25519)

---

## Типовые Policy Паттерны

### Запретить все destructive операции
```cedar
forbid(principal, action == Action::"bash", resource)
when { resource.command like "*--force*" || resource.command like "*-rf*" };
```

### Whitelist только safe команды
```cedar
forbid(principal, action == Action::"bash", resource);
permit(principal, action == Action::"bash", resource)
when { resource.command like "git status*" || resource.command like "pytest*" };
```

### Audit-only (log без блокировки)
```cedar
permit(principal, action, resource);
// Все вызовы пройдут, но будут подписаны
```

---

## Связанные скилы

- `sec-auditor` — аудит кода на уязвимости (без policy enforcement)
- `security-guard` — финансовый security checklist
- `threat-modeling` — STRIDE analysis перед настройкой policies
