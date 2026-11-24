---
id: api-compat-contract
catalog: 14
title: Совместимость публичного API
family: engineering
triggers: [api, совместимость, контракт, contract test, openapi, breaking change, semver, sdk, обратная совместимость]
phrases: [совместимость api, contract tests, breaking change]
risk_tier: Yellow
budget_turns: 50
skills: [intended-vs-implemented]
agents: [explorer, tester, reviewer]
verifier: reviewer
statuses: [COMPLETE, PARTIAL, BLOCKED]
baseline_first: false
gap: нет навыка под контрактные тесты API; работает intended-vs-implemented и общие агенты
---
## Задание
Восстанови фактический контракт API из кода и тестов, сверь с документацией и ожиданиями клиентов, найди несовместимости и закрой их контрактными тестами.

## Done when
- Фактический контракт восстановлен и сопоставлен с документацией, расхождения перечислены.
- Основные сценарии клиентов покрыты контрактными тестами со стороны потребителя.
- Каждая несовместимость исправлена или оформлена как согласованное изменение версии.
- Опубликован отчёт об изменениях API.

## Evidence
Таблица «задокументировано / фактически», контрактные тесты, отчёт.

## Ловушки
Документация описывает намерение, клиенты зависят от фактического поведения, включая недокументированное.
