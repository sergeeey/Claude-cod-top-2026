# 08 — DDD and Semantic Boundary Analysis

Домен проекта: «Evidence-aware Goal Operating Layer» — управление достоверностью работы
LLM-агента (evidence gates, память, research-методология). Универсальных сущностей типа
`User/Order` нет; перегруженные термины есть.

## Ubiquitous Language glossary (ключевые термины и их согласованность)

| Термин | Значение | Согласован во всех модулях? |
|---|---|---|
| hook | исполняемый python-скрипт на событие Claude Code | ДА, но «hook» в счётчиках включает и НЕ-хуки (utils.py — библиотека): test_structure явно исключает utils/severity_calibrator из подсчёта — договорённость существует, но выражена только внутри теста |
| guard / gate | hook, который предупреждает (nudge) vs условие принятия решения | ЧАСТИЧНО: в integrity.md зафиксировано, что PostToolUse-хуки физически не могут блокировать — «gate» местами означает soft nudge (задокументированное ограничение F-03) |
| **memory** | ПЕРЕГРУЖЕН: (1) project memory `.claude/memory/`, (2) global `~/.claude/memory/`, (3) agent-memory, (4) auto-memory ассистента | **НЕТ** — 4 смысла; memory-protocol.md вводит canonical/legacy dual-path именно из-за этого («audit hallucination» кейс задокументирован) |
| rule | markdown-политика | ЧАСТИЧНО: dual-scope (repo vs ~/.claude) — свежая canonical/stub развязка (HEAD-коммиты) |
| skill / agent | прокладываемые способности | ДА |
| experiment / null_result / pearl | артефакты Falsification Ladder | ДА (словарь FL последователен) |
| evidence marker | [VERIFIED]/[INFERRED]/… | ДА — evidence-markers.md объявлен canonical reference |

## Candidate Bounded Contexts (6) и Context Map

```
[Hook Runtime Platform]  ← core: utils(protocol), settings.json, hook_state
   ↑ conformist (все контексты используют её протокол)
[Integrity/Evidence Guards]   [Security Guards]        [Memory/Learning]
 evidence_guard, validation_    input_guard, mcp/web_    learning_*, pattern_extractor,
 theater_guard, commit_test_    response_guard,           post_commit_memory, session_start
 gate, iteration_guard          severity_calibrator          │ shared kernel: .claude/memory/*
[Knowledge/Vault Pipeline]    [Research Ops (FL)]           │ (сейчас — БЕЗ владельца; цель:
 auto_capture, knowledge_       estimand_guard, promotion_   published language через memory-API)
 librarian, vector_store,       gate_guard, experiment_
 doc_bridge*, expert_registry*  insight, claim_entropy_tracker
[Packaging/Docs]  README, plugin.json, marketplace.json×2, docs/, test_structure gate
* env-зависимая подгруппа (Obsidian/MarkItDown) — anti-corruption слой к внешней среде отсутствует
```

Типы отношений: Runtime Platform ↔ остальные = **customer–supplier с conformist-клиентами**;
Memory ↔ Guards/Learning = **shared kernel** (самая рискованная связь — см. HS-03);
Packaging ↔ все = **published language нарушен** (копии литералов вместо генерации).

## Data ownership matrix

| Store | Писатели (сейчас) | Читатели | Владелец (предлагаемый) | Транзакционность |
|---|---|---|---|---|
| .claude/memory/activeContext.md | 7 хуков | 6 хуков | Memory/Learning context, единый writer-API | file_lock есть у части путей — НЕ гарантирован |
| .claude/memory/patterns.md | 3 | 6 | Memory/Learning | то же |
| ~/.claude/logs/hook_triggers.jsonl | 1 (utils.log_hook_trigger) | 1 (input_guard) | Runtime Platform | append-only — OK |
| ~/.claude/state/* | 9 файлов | те же | Runtime Platform (facade) | атомарные json-write есть в utils |
| experiments/, null_results/, pearl_registry/ | research-хуки + человек | research-хуки, skills | Research Ops | человек в контуре — eventual |
| plugin.json / marketplace.json×2 | человек | marketplace, README-читатели | Packaging | инвариант не проверяется для root-копии |

## Выводы по границам (§13 ТЗ)

1. Транзакционные границы: единственная настоящая — конкурентная запись в activeContext.md;
   инварианты («агенты не пишут в память напрямую, пишет оркестратор» — context-loading.md)
   ДЕКЛАРИРОВАНЫ, но кодом не принуждаются. <risk>Декларативный инвариант без enforcement — то,
   что Shopify (C1) решали Wedge'ем.</risk>
2. Новые микросервисы/отдельные плагины из bounded contexts НЕ создаются (правило §13):
   все 6 контекстов остаются modular-monolith-границами внутри одного deployment unit.
3. Семантическая перегрузка «memory» — реальный источник ошибок (задокументированный
   «audit hallucination» кейс в memory-protocol.md) → glossary + один canonical path выше
   любых структурных рефакторингов по соотношению эффект/риск.
