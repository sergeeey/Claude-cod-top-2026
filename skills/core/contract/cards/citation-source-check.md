---
id: citation-source-check
title: Проверка цитат и источников
family: science-audit
triggers: [цитата, ссылка, источник, DOI, arXiv, подтверждает, reference, citation]
phrases: [проверь цитату, проверь ссылки, подтверждает ли статья, существует ли статья, verify the citation]
risk_tier: Green
budget_turns: 25
skills: [citation-management, claim-decomposer]
agents: [verifier, source-librarian]
verifier: verifier
statuses: [SUPPORTED, CONTRADICTED, NOT_FOUND, INSUFFICIENT]
baseline_first: false
---
## Задание
Для каждой цитаты: подтверди, что источник существует и это тот самый (авторы, название, год), открой полный текст, найди конкретное место и реши, подтверждает ли оно утверждение.

## Done when
- Личность источника проверена независимо (DOI или arXiv ID, авторы).
- Для каждой цитаты запись: утверждение, источник, место в тексте, фрагмент, вердикт.
- NOT_FOUND не превращается в CONTRADICTED; INSUFFICIENT отделён от SUPPORTED.
- Контроль: заведомо существующий и заведомо выдуманный источник дали ожидаемые ответы.

## Evidence
Таблица вердиктов, найденные фрагменты, команды поиска.

## Ловушки
Число, которого нет в тексте (например, граница, которую статья не называет), выдаётся за её вывод. Ошибка в имени автора находится на проверке личности, до чтения текста.
